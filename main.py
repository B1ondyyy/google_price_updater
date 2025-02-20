import subprocess
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from pydantic import BaseModel
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
import threading

# Функция для запуска Uvicorn сервера
def run_uvicorn():
    command = ["uvicorn", "try_main:app", "--reload"]
    subprocess.run(command)

# Запуск сервера FastAPI в фоновом режиме
if __name__ == "__main__":
    # Запуск сервера в отдельном потоке
    server_thread = threading.Thread(target=run_uvicorn)
    server_thread.daemon = True  # Это позволяет завершить поток при завершении главной программы
    server_thread.start()

app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL для получения данных о заявках на продажу на рынке USDT/RUB
url = "https://garantex.org/api/v2/depth?market=usdtrub"

# Модель для возвращаемых данных
class PriceResponse(BaseModel):
    timestamp: str
    price_usdt_rub: float
    price_with_commission_usdt_rub: float

# Google Sheets setup
SERVICE_ACCOUNT_FILE = 'tmp/testtable-451412-bd646fcb945f.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1NOIBvsLTnh_p550GYqel2Twc8s3B-5mvWi5-NMbkMhk'  # Ваш ID таблицы
SHEET_NAME = 'Москва'  # Имя листа

# Функция для подключения к Google Sheets API
def get_google_sheets_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

# Функция для записи данных в Google Sheets
def write_to_google_sheets(price_with_commission):
    try:
        service = get_google_sheets_service()

        # # Округляем цену до одной цифры после запятой
        rounded_price = round(price_with_commission, 1)

        # Подготовка данных для записи
        values = [[rounded_price]]
        body = {
            'values': values
        }

        # Запись данных в ячейку B2
        result = service.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!F2",  # Указываем ячейку, например, F2
            valueInputOption="RAW",
            body=body
        ).execute()

        print(f"Data successfully written to sheet: {result}")

    except HttpError as err:
        print(f"Error occurred: {err}")

# Функция для автоматического обновления цены
def auto_update_price():
    while True:
        # Отправляем запрос на получение цены
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get('asks'):
                price = float(data['asks'][0]['price'])  # Получаем цену продажи USDT в рублях
                commission = 0.007  # Комиссия на сайте (0.7%)
                price_with_commission = price * (1 + commission)

                # Записываем данные в Google Sheets
                write_to_google_sheets(round(price_with_commission, 2))

        # Ждем 10 секунд перед следующим обновлением
        time.sleep(10)

# Запуск обновления данных в фоновом режиме
update_thread = threading.Thread(target=auto_update_price)
update_thread.daemon = True  # Это позволяет завершить поток при завершении главной программы
update_thread.start()

# Эндпоинт для получения данных о цене
@app.get("/price", response_model=PriceResponse)
async def get_price():
    # Отправка GET-запроса к API Garantex
    response = requests.get(url)

    # Проверка успешности запроса
    if response.status_code == 200:
        data = response.json()
        if data.get('asks'):
            price = float(data['asks'][0]['price'])  # Получаем цену продажи USDT в рублях
            commission = 0.007  # Комиссия на сайте (0.7%)
            price_with_commission = price * (1 + commission)

            # Формируем результат для ответа
            result = PriceResponse(
                timestamp=datetime.now().isoformat(),
                price_usdt_rub=price,
                price_with_commission_usdt_rub=round(price_with_commission, 2)
            )
            return result
        else:
            return {"error": "Нет доступных заявок на продажу."}
    else:
        return {"error": f"Ошибка при получении данных: {response.status_code}"}