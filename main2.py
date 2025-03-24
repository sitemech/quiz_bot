import requests
import telebot
import schedule
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

TOKEN = '7636938358:AAG6JZehslEU2hMKyVDYSS94CTNd4OHsM6c'
CHAT_IDS = set()
NOTIFICATIONS_ENABLED = True
bot = telebot.TeleBot(TOKEN, threaded=False)
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


def parse_date(date_str):
    date_part, weekday = date_str.split(", ")
    day, month_name = date_part.split(" ")
    day = int(day)
    month = months[month_name.lower()]
    date_str = f"{day:02d}-{month:02d}-2025"
    date_obj = datetime.strptime(date_str, "%d-%m-%Y")
    return date_obj


def fetch_quiz_schedule():
    response = requests.get(URL)
    soup = BeautifulSoup(response.text, 'html.parser')
    quizzes = []

    for quiz in soup.find_all('div', class_='schedule-block available'):
        date_text = quiz.find('div', class_='h3 h3-green h3-mb10 block-date-with-language-game game-active').text.strip()
        name = quiz.find('div', class_='h2 h2-game-card h2-left').text.strip()
        place = (quiz.find('div', class_='techtext techtext-halfwhite').text.strip()
                .replace("Где это?", "")
                .replace("\n",""))
        elements = quiz.find_all('div', class_='schedule-info')
        time = elements[1].text.strip()
        date = parse_date(date_text)
        quizzes.append((date, name, place, time))

    return quizzes


def get_today_and_tomorrow_quizzes():
    today = datetime.today().date()
    tomorrow = today + timedelta(days=1)
    quizzes = fetch_quiz_schedule()
    return [q for q in quizzes if q[0].date() in [today, tomorrow]]


def get_next_quiz():
    today = datetime.today().date()
    quizzes = fetch_quiz_schedule()
    future_quizzes = sorted([q for q in quizzes if q[0].date() >= today], key=lambda x: x[0])
    return future_quizzes[0] if future_quizzes else None


def send_daily_notification():
    if NOTIFICATIONS_ENABLED:
        upcoming_quizzes = get_today_and_tomorrow_quizzes()
        if upcoming_quizzes:
            message = "Ближайшие квизы:\n" + "\n".join(
                [f"{q[1]} ({q[0].strftime('%d.%m.%Y')})\nМесто: {q[2]}\nВремя: {q[3]}" for q in upcoming_quizzes])
        else:
            message = "Сегодня и завтра квизов нет."
        for chat_id in CHAT_IDS:
            bot.send_message(chat_id, message)


@bot.message_handler(commands=['start', 'subscribe'])
def subscribe(message):
    CHAT_IDS.add(message.chat.id)
    next_quiz = get_next_quiz()
    if next_quiz:
        bot.send_message(message.chat.id,
                         f"Следующий квиз: {next_quiz[1]} ({next_quiz[0].strftime('%d.%m.%Y')})\nМесто: {next_quiz[2]}\nВремя: {next_quiz[3]}")
    else:
        bot.send_message(message.chat.id, "Расписание квизов пока пусто.")


@bot.message_handler(commands=['pause'])
def pause_notifications(message):
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = False
    bot.send_message(message.chat.id, "Уведомления приостановлены.")


@bot.message_handler(commands=['resume'])
def resume_notifications(message):
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = True
    bot.send_message(message.chat.id, "Уведомления возобновлены.")


schedule.every().day.at("10:00").do(send_daily_notification)

while True:
    bot.polling(none_stop=True, interval=1)
    schedule.run_pending()
    time.sleep(1)
