import requests
import telebot
import schedule
import time
import logging
import threading
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Токен бота
TOKEN = '7636938358:AAG6JZehslEU2hMKyVDYSS94CTNd4OHsM6c'
CHAT_IDS = set()
NOTIFICATIONS_ENABLED = True
bot = telebot.TeleBot(TOKEN, threaded=False)

SUBSCRIBERS_FILE = 'subscribers.json'

# Для подмены текущей даты (используется в отладке)
DEBUG_DATE = None  # Например: datetime(2025, 6, 12)

months = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12
}

URL = "https://ufa.quizplease.ru/schedule?QpGameSearch%5BcityId%5D=6&QpGameSearch%5Bdates%5D=&QpGameSearch%5Bstatus%5D%5B%5D=all&QpGameSearch%5Bformat%5D%5B%5D=all&QpGameSearch%5Btype%5D%5B%5D=1&QpGameSearch%5Bbars%5D%5B%5D=all"

def save_subscribers():
    try:
        with open(SUBSCRIBERS_FILE, 'w') as f:
            json.dump(list(CHAT_IDS), f)
        logging.info(f"Сохранено {len(CHAT_IDS)} подписчиков")
    except Exception as e:
        logging.error(f"Ошибка сохранения подписчиков: {e}")

def load_subscribers():
    global CHAT_IDS
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, 'r') as f:
                CHAT_IDS = set(json.load(f))
            logging.info(f"Загружено {len(CHAT_IDS)} подписчиков")
        except Exception as e:
            logging.error(f"Ошибка загрузки подписчиков: {e}")
            CHAT_IDS = set()
    else:
        CHAT_IDS = set()

def get_today():
    return DEBUG_DATE.date() if DEBUG_DATE else datetime.today().date()

def parse_date(date_str):
    date_part, weekday = date_str.split(", ")
    day, month_name = date_part.split(" ")
    day = int(day)
    month = months[month_name.lower()]
    date_obj = datetime.strptime(f"{day:02d}-{month:02d}-2025", "%d-%m-%Y")
    return date_obj

def fetch_quiz_schedule():
    logging.info("Запрос расписания квизов")
    response = requests.get(URL)
    soup = BeautifulSoup(response.text, 'html.parser')
    quizzes = []

    for quiz in soup.find_all('div', class_='schedule-block available'):
        date_text = quiz.find('div', class_='h3 h3-green h3-mb10 block-date-with-language-game game-active').text.strip()
        name = quiz.find('div', class_='h2 h2-game-card h2-left').text.strip()
        place = (quiz.find('div', class_='techtext techtext-halfwhite').text.strip()
                .replace("Где это?", "")
                .replace("\n", ""))
        elements = quiz.find_all('div', class_='schedule-info')
        time_ = elements[1].text.strip()
        date = parse_date(date_text)
        quizzes.append((date, name, place, time_))

    logging.info(f"Найдено квизов: {len(quizzes)}")
    return quizzes

def get_today_and_tomorrow_quizzes():
    today = get_today()
    tomorrow = today + timedelta(days=1)
    quizzes = fetch_quiz_schedule()
    return [q for q in quizzes if q[0].date() in [today, tomorrow]]

def get_next_quiz():
    today = get_toda_
