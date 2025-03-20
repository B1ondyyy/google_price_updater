import subprocess
import threading
import time
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Функция для запуска Uvicorn сервера
def run_uvicorn():
    command = ["uvicorn", "try_main:app", "--reload"]
    subprocess.run(command)

# Запуск сервера FastAPI в фоновом режиме
if __name__ == "__main__":
    server_thread = threading.Thread(target=run_uvicorn)
    server_thread.daemon = True
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

# URL для парсинга цены USDT/RUB
url = "https://cryptotyumen.ru/"

# Модель для API-ответа
class PriceResponse(BaseModel):
    timestamp: str
    price_usdt_rub: float

# Google Sheets setup
SERVICE_ACCOUNT_FILE = 'tmp/asic-price-cc8ecc41768a.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1IVc5OpcfjA4-k9h9c7_0MJWhsPhU-IdAM1iZPi8iTJM'  # ID таблицы
SHEET_NAME = 'New'  # Имя листа

# Функция подключения к Google Sheets API
def get_google_sheets_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

# Функция для записи данных в Google Sheets
def write_to_google_sheets(price):
    try:
        service = get_google_sheets_service()

        # Округляем цену до двух знаков после запятой
        rounded_price = round(price, 2)

        values = [[rounded_price]]
        body = {'values': values}

        # Запись в ячейку I2
        result = service.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!I2",
            valueInputOption="RAW",
            body=body
        ).execute()

        print(f"Цена успешно обновлена: {result}")

    except HttpError as err:
        print(f"Ошибка Google Sheets: {err}")

# Функция парсинга цены с CryptoTyumen
def get_usdt_price():
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Находим элемент с ценой
            price_input = soup.find("input", {"name": "sum1"})
            if price_input and price_input.has_attr("value"):
                return float(price_input["value"])
            else:
                print("Ошибка: не удалось найти цену на сайте.")
                return None
        else:
            print(f"Ошибка запроса: {response.status_code}")
            return None
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return None

# Функция для автоматического обновления цены
def auto_update_price():
    while True:
        price = get_usdt_price()
        if price:
            write_to_google_sheets(price)
        time.sleep(600)

# Запуск обновления данных в фоновом режиме
update_thread = threading.Thread(target=auto_update_price)
update_thread.daemon = True
update_thread.start()

# Эндпоинт API для получения текущей цены
@app.get("/price", response_model=PriceResponse)
async def get_price():
    price = get_usdt_price()
    if price:
        return PriceResponse(timestamp=datetime.now().isoformat(), price_usdt_rub=price)
    else:
        return {"error": "Не удалось получить цену."}
