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

# Флаг режима отладки
DEBUG = False  # True — уведомления каждые 10 секунд, False — каждый день в 12:00

# Для подмены текущей даты (используется в отладке)
DEBUG_DATE = None  # Например: datetime(2025, 6, 12) либо None

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

URL = "https://ufa.quizplease.ru/schedule?QpGameSearch%5BcityId%5D=6&QpGameSearch%5Bdates%5D=&QpGameSearch%5Bformat%5D%5B%5D=all&QpGameSearch%5Btype%5D%5B%5D=1"

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

def format_date_label(date_obj):
    today = get_today()
    if date_obj.date() == today:
        return "🔥 Сегодня"
    elif date_obj.date() == today + timedelta(days=1):
        return "⚡ Завтра"
    else:
        return date_obj.strftime('%d.%m.%Y')

def parse_date(date_str):
    date_part, _weekday = date_str.split(", ")
    day, month_name = date_part.split(" ")
    day = int(day)
    month = months[month_name.lower()]
    date_str_formatted = f"{day:02d}-{month:02d}-2025"
    date_obj = datetime.strptime(date_str_formatted, "%d-%m-%Y")
    return date_obj

def fetch_quiz_schedule():
    logging.info("Запрос расписания квизов")
    response = requests.get(URL)
    soup = BeautifulSoup(response.text, 'html.parser')
    quizzes = []

    for quiz in soup.find_all('div', class_='schedule-block available'):
        date_text = quiz.find('div', class_='h3 h3-green h3-mb10 block-date-with-language-game game-active').text.strip()
        date = parse_date(date_text)

        name = quiz.find('div', class_='h2 h2-game-card h2-left').text.strip()

        place_block = quiz.find('div', class_='techtext techtext-halfwhite')
        place_text = place_block.text.strip().replace("Где это?", "").replace("\n", " ").strip()

        parts = place_text.split(",")
        if len(parts) >= 2:
            venue_name = parts[0].strip()
            address = ",".join(parts[1:]).strip()
        else:
            venue_name = place_text
            address = ""

        elements = quiz.find_all('div', class_='schedule-info')
        time_ = elements[1].text.strip() if len(elements) > 1 else ""

        desc_block = quiz.find('div', class_='techtext techtext-mb30')
        description = desc_block.text.strip() if desc_block else ""

        quizzes.append((date, name, venue_name, address, time_, description))

    logging.info(f"Найдено квизов: {len(quizzes)}")
    return quizzes

def get_today_and_tomorrow_quizzes():
    logging.info("Получение квизов на сегодня и завтра")
    today = get_today()
    tomorrow = today + timedelta(days=1)
    quizzes = fetch_quiz_schedule()
    return [q for q in quizzes if q[0].date() in [today, tomorrow]]

def get_next_quiz():
    logging.info("Поиск ближайшего квиза")
    today = get_today()
    quizzes = fetch_quiz_schedule()
    future_quizzes = sorted([q for q in quizzes if q[0].date() >= today], key=lambda x: x[0])
    return future_quizzes[0] if future_quizzes else None

def send_daily_notification():
    logging.info("Проверка необходимости отправки уведомлений")
    if NOTIFICATIONS_ENABLED and CHAT_IDS:
        upcoming_quizzes = get_today_and_tomorrow_quizzes()
        filtered_quizzes = [q for q in upcoming_quizzes if "[новички]" not in q[1].lower()]

        if filtered_quizzes:
            lines = []
            for q in filtered_quizzes:
                day_label = format_date_label(q[0])
                lines.append(
                    f"🎲 {q[1]} ({day_label} — {q[0].strftime('%d.%m.%Y')})\n"
                    f"⏰ Время: {q[4]}\n"
                    f"📍 Место: {q[2]}, {q[3]}\n"
                )
            game_description = filtered_quizzes[0][5] if filtered_quizzes[0][5] else ""
            if game_description:
                lines.append(f"📝 Описание игры:\n{game_description}")
            message = "📅 Ближайшие квизы:\n\n" + "\n\n".join(lines)
        else:
            message = "Сегодня и завтра подходящих квизов нет. Я уведомлю вас за сутки."

        for chat_id in CHAT_IDS:
            try:
                bot.send_message(chat_id, message)
                logging.info(f"Отправлено уведомление в чат {chat_id}")
            except Exception as e:
                logging.error(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")
    else:
        logging.info("Уведомления отключены или нет подписчиков")

@bot.message_handler(commands=['start', 'subscribe'])
def subscribe(message):
    CHAT_IDS.add(message.chat.id)
    save_subscribers()
    logging.info(f"Пользователь {message.chat.id} подписан")
    next_quiz = get_next_quiz()
    if next_quiz:
        day_label = format_date_label(next_quiz[0])
        bot.send_message(message.chat.id,
                         f"🎲 Следующий квиз: {next_quiz[1]} ({day_label} — {next_quiz[0].strftime('%d.%m.%Y')})\n"
                         f"⏰ Время: {next_quiz[4]}\n"
                         f"📍 Место: {next_quiz[2]}, {next_quiz[3]}\n")
    else:
        bot.send_message(message.chat.id, "Сегодня и завтра квизов пока нет, но я уведомлю вас за сутки.")

@bot.message_handler(commands=['pause'])
def pause_notifications(message):
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = False
    logging.info(f"Пользователь {message.chat.id} приостановил уведомления")
    bot.send_message(message.chat.id, "Уведомления приостановлены.")

@bot.message_handler(commands=['resume'])
def resume_notifications(message):
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = True
    logging.info(f"Пользователь {message.chat.id} возобновил уведомления")
    bot.send_message(message.chat.id, "Уведомления возобновлены.")

def scheduler_debug():
    while True:
        send_daily_notification()
        time.sleep(10)

def scheduler_production():
    schedule.every().day.at("07:00").do(send_daily_notification)
    while True:
        schedule.run_pending()
        time.sleep(1)

def main():
    load_subscribers()
    if DEBUG:
        logging.info("Запуск в режиме отладки (уведомления каждые 10 секунд)")
        threading.Thread(target=scheduler_debug, daemon=True).start()
    else:
        logging.info("Запуск в режиме продакшн (ежедневно в 12:00)")
        threading.Thread(target=scheduler_production, daemon=True).start()

    logging.info("Запуск бота")
    bot.infinity_polling()

if __name__ == '__main__':
    main()
