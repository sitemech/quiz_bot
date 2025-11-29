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
    """
    Сохраняет множество подписчиков CHAT_IDS в файл JSON.
    """
    try:
        with open(SUBSCRIBERS_FILE, 'w') as f:
            json.dump(list(CHAT_IDS), f)
        logging.info(f"Сохранено {len(CHAT_IDS)} подписчиков")
    except Exception as e:
        logging.error(f"Ошибка сохранения подписчиков: {e}")

def load_subscribers():
    """
    Загружает список подписчиков из файла JSON в множество CHAT_IDS.
    Если файл отсутствует или возникает ошибка — создает пустое множество.
    """
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
    """
    Возвращает текущую дату (date) либо дату из DEBUG_DATE для отладки.
    """
    return DEBUG_DATE.date() if DEBUG_DATE else datetime.today().date()

def parse_date(date_str):
    """
    Парсит дату из строки формата "14 июня, пятница" и возвращает datetime-объект.
    """
    date_part, weekday = date_str.split(", ")
    day, month_name = date_part.split(" ")
    day = int(day)
    month = months[month_name.lower()]
    date_obj = datetime.strptime(f"{day:02d}-{month:02d}-2025", "%d-%m-%Y")
    return date_obj

def fetch_quiz_schedule():
    """
    Запрашивает страницу с расписанием квизов и парсит ее.
    Возвращает список кортежей (дата (datetime), название, место, время).
    """
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
    """
    Возвращает список квизов, запланированных на сегодня и завтра.
    """
    today = get_today()
    tomorrow = today + timedelta(days=1)
    quizzes = fetch_quiz_schedule()
    return [q for q in quizzes if q[0].date() in [today, tomorrow]]

def get_next_quiz():
    """
    Находит и возвращает ближайший квиз от текущей даты, если он есть.
    """
    today = get_today()
    quizzes = fetch_quiz_schedule()
    future_quizzes = sorted([q for q in quizzes if q[0].date() >= today], key=lambda x: x[0])
    return future_quizzes[0] if future_quizzes else None

def format_date_label(date):
    """
    Формирует строку с пометкой даты:
    "Сегодня", "Завтра" или дата в формате "dd.mm.yyyy".
    """
    today = get_today()
    if date.date() == today:
        return "Сегодня"
    elif date.date() == today + timedelta(days=1):
        return "Завтра"
    else:
        return date.strftime("%d.%m.%Y")

def send_daily_notification():
    """
    Рассылает подписчикам уведомления с ближайшими квизами на сегодня и завтра,
    исключая квизы для новичков. Если подходящих квизов нет — информирует об этом.
    """
    if NOTIFICATIONS_ENABLED and CHAT_IDS:
        upcoming_quizzes = get_today_and_tomorrow_quizzes()

        filtered_quizzes = [q for q in upcoming_quizzes if "[новички]" not in q[1].lower()]

        if filtered_quizzes:
            lines = []
            for q in filtered_quizzes:
                day_label = format_date_label(q[0])
                lines.append(f"{q[1]} ({day_label} — {q[0].strftime('%d.%m.%Y')})\nМесто: {q[2]}\nВремя: {q[3]}")
            message = "Ближайшие квизы:\n" + "\n\n".join(lines)
        else:
            message = "Сегодня и завтра подходящих квизов нет. Я уведомлю вас за сутки."

        for chat_id in CHAT_IDS:
            try:
                bot.send_message(chat_id, message)
                logging.info(f"Отправлено уведомление в чат {chat_id}")
            except Exception as e:
                logging.error(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")

@bot.message_handler(commands=['start', 'subscribe'])
def subscribe(message):
    """
    Обрабатывает команду подписки, добавляет пользователя в подписчики,
    сохраняет список, и отправляет информацию о следующем квизе.
    """
    CHAT_IDS.add(message.chat.id)
    save_subscribers()
    logging.info(f"Пользователь {message.chat.id} подписан")
    next_quiz = get_next_quiz()
    if next_quiz:
        day_label = format_date_label(next_quiz[0])
        bot.send_message(message.chat.id,
                         f"Следующий квиз: {next_quiz[1]} ({day_label} — {next_quiz[0].strftime('%d.%m.%Y')})\nМесто: {next_quiz[2]}\nВремя: {next_quiz[3]}")
    else:
        bot.send_message(message.chat.id, "Сегодня и завтра квизов пока нет, но я уведомлю вас за сутки.")

@bot.message_handler(commands=['pause'])
def pause_notifications(message):
    """
    Отключает отправку уведомлений по команде пользователя.
    """
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = False
    logging.info(f"Пользователь {message.chat.id} приостановил уведомления")
    bot.send_message(message.chat.id, "Уведомления приостановлены.")

@bot.message_handler(commands=['resume'])
def resume_notifications(message):
    """
    Включает отправку уведомлений по команде пользователя.
    """
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = True
    logging.info(f"Пользователь {message.chat.id} возобновил уведомления")
    bot.send_message(message.chat.id, "Уведомления возобновлены.")

schedule.every(10).seconds.do(send_daily_notification)

def run_bot():
    """
    Запускает бесконечный цикл обработки сообщений Telegram-бота.
    """
    logging.info("Запуск Telegram-бота")
    bot.infinity_polling()

def run_scheduler():
    """
    Запускает планировщик заданий для отправки уведомлений с периодом в 1 секунду.
    """
    logging.info("Запуск планировщика уведомлений")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    load_subscribers()
    bot_thread = threading.Thread(target=run_bot)
    scheduler_thread = threading.Thread(target=run_scheduler)

    bot_thread.start()
    scheduler_thread.start()
