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
from config import TOKEN

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
telebot.logger.setLevel(logging.INFO)

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

URL = "https://ufa.quizplease.ru/schedule?statuses[]=0&statuses[]=1&statuses[]=2&statuses[]=3&game_types[]=1&game_types[]=2&game_types[]=6&game_types[]=8"
REQUEST_HEADERS = {
    # Using a browser-like UA helps the site avoid showing a bot/captcha page
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SCHEDULE_CITY_ID = 3  # Уфа в API Quiz, плиз!
API_BASE_URL = "https://api.quizplease.com/"

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


def log_message(message, label="msg"):
    """Логируем входящее сообщение/команду для отладки."""
    try:
        user = message.from_user
        logging.info(f"{label} from {user.id} (@{user.username}): {message.text}")
    except Exception:
        logging.info(f"{label}: {message}")

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
    today = get_today()
    year = today.year
    # If the parsed month already прошел в текущем году, относим дату к следующему году
    if month < today.month or (month == today.month and day < today.day):
        year += 1
    return datetime(year, month, day)

def parse_api_game_datetime(date_str: str) -> datetime:
    """
    API отдаёт дату в формате 'DD.MM.YYYY HH:MM' (например '18.03.2026 19:30').
    Иногда время может отсутствовать — тогда пробуем 'DD.MM.YYYY'.
    """
    date_str = (date_str or "").strip()
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Не удалось распарсить дату игры из API: {date_str!r}")

def html_to_text(value: str) -> str:
    """Аккуратно превращает HTML/текст в читаемый plain text."""
    if not value:
        return ""
    return BeautifulSoup(value, "html.parser").get_text("\n").strip()

def fetch_quiz_schedule():
    logging.info("Запрос расписания квизов")
    quizzes = []

    # Новая версия сайта рендерит расписание на клиенте (Nuxt), поэтому парсинг HTML ломается.
    # Берём данные напрямую из публичного API, который использует сайт.
    api_url = f"{API_BASE_URL}api/games/schedule/{SCHEDULE_CITY_ID}"
    params = {
        "per_page": 50,
        "order": "date",
        "meta[]": ["places_ids", "dates"],
        "statuses[]": ["0", "1", "2", "3", "5"],
        "game_types[]": ["1", "2", "6", "8"],
    }

    try:
        response = requests.get(api_url, headers=REQUEST_HEADERS, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        games = (payload.get("data") or {}).get("data") or []

        for game in games:
            date = parse_api_game_datetime(game.get("date"))
            name = (game.get("title") or "").strip()

            place = game.get("place") or {}
            venue_name = (place.get("title") or "").strip()
            address = (place.get("address") or place.get("address_ru") or "").strip()

            time_ = date.strftime("%H:%M")
            description = html_to_text(game.get("description") or "")

            quizzes.append((date, name, venue_name, address, time_, description))

        logging.info(f"Найдено квизов (API): {len(quizzes)}")
        return quizzes
    except Exception as e:
        logging.warning(f"API-парсинг расписания не удался, пробую HTML: {e}")

    # Fallback на старую HTML-верстку (на случай временных проблем с API)
    response = requests.get(URL, headers=REQUEST_HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    columns = soup.find_all("div", class_="schedule-column")
    if not columns:
        logging.warning("Не удалось найти блоки с расписанием в HTML (верстка/защита от ботов)")
        return []

    for quiz in columns:
        date_node = quiz.find("div", class_=lambda x: x and "block-date-with-language-game" in x)
        name_node = quiz.find("div", class_="h2 h2-game-card h2-left")
        place_block = quiz.find("div", class_="techtext techtext-halfwhite")

        if not (date_node and name_node and place_block):
            continue

        date_text = date_node.text.strip()
        date = parse_date(date_text)
        name = name_node.text.strip()

        place_text = place_block.text.strip().replace("Где это?", "").replace("\n", " ").strip()
        parts = place_text.split(",")
        if len(parts) >= 2:
            venue_name = parts[0].strip()
            address = ",".join(parts[1:]).strip()
        else:
            venue_name = place_text
            address = ""

        elements = quiz.find_all("div", class_="schedule-info")
        time_ = elements[1].text.strip() if len(elements) > 1 else ""

        desc_block = quiz.find("div", class_="techtext techtext-mb30")
        description = desc_block.text.strip() if desc_block else ""

        quizzes.append((date, name, venue_name, address, time_, description))

    logging.info(f"Найдено квизов (HTML fallback): {len(quizzes)}")
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

def format_upcoming_quizzes_message():
    """Формирует сообщение о ближайших квизах на сегодня и завтра с описаниями."""
    upcoming_quizzes = get_today_and_tomorrow_quizzes()
    filtered_quizzes = [q for q in upcoming_quizzes if "[новички]" not in q[1].lower()]

    if filtered_quizzes:
        lines = []
        for q in filtered_quizzes:
            day_label = format_date_label(q[0])
            quiz_info = (
                f"🎲 {q[1]} ({day_label} — {q[0].strftime('%d.%m.%Y')})\n"
                f"⏰ Время: {q[4]}\n"
                f"📍 Место: {q[2]}, {q[3]}\n"
            )
            # Добавляем описание для каждого квиза, если оно есть
            if q[5]:  # q[5] - это описание
                quiz_info += f"📝 Описание игры:\n{q[5]}\n"
            lines.append(quiz_info)
        return "📅 Ближайшие квизы:\n\n" + "\n\n".join(lines)
    else:
        return "Сегодня и завтра подходящих квизов нет. Я уведомлю вас за сутки."

def send_daily_notification():
    logging.info("Проверка необходимости отправки уведомлений")
    if NOTIFICATIONS_ENABLED and CHAT_IDS:
        message = format_upcoming_quizzes_message()

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
    log_message(message, label="/start|/subscribe")
    CHAT_IDS.add(message.chat.id)
    save_subscribers()
    logging.info(f"Пользователь {message.chat.id} подписан")
    bot.send_message(message.chat.id, "Подписка оформлена. Ищу ближайшие квизы...")
    try:
        message_text = format_upcoming_quizzes_message()
        bot.send_message(message.chat.id, message_text)
    except Exception as e:
        logging.error(f"Ошибка при получении ближайших квизов: {e}")
        bot.send_message(message.chat.id, "Не удалось получить расписание. Попробуйте позже или команду /next.")

@bot.message_handler(commands=['pause'])
def pause_notifications(message):
    log_message(message, label="/pause")
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = False
    logging.info(f"Пользователь {message.chat.id} приостановил уведомления")
    bot.send_message(message.chat.id, "Уведомления приостановлены.")

@bot.message_handler(commands=['resume'])
def resume_notifications(message):
    log_message(message, label="/resume")
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = True
    logging.info(f"Пользователь {message.chat.id} возобновил уведомления")
    bot.send_message(message.chat.id, "Уведомления возобновлены.")

@bot.message_handler(commands=['next'])
def send_next_quiz(message):
    log_message(message, label="/next")
    bot.send_message(message.chat.id, "Проверяю расписание...")
    try:
        next_quiz = get_next_quiz()
        if next_quiz:
            day_label = format_date_label(next_quiz[0])
            bot.send_message(message.chat.id,
                             f"🎲 Следующий квиз: {next_quiz[1]} ({day_label} — {next_quiz[0].strftime('%d.%m.%Y')})\n"
                             f"⏰ Время: {next_quiz[4]}\n"
                             f"📍 Место: {next_quiz[2]}, {next_quiz[3]}\n")
        else:
            bot.send_message(message.chat.id, "Ближайших квизов в расписании нет.")
    except Exception as e:
        logging.error(f"Ошибка при обработке /next: {e}")
        bot.send_message(message.chat.id, "Не удалось получить расписание. Попробуйте позже.")


@bot.message_handler(func=lambda m: True, content_types=['text'])
def catch_all(message):
    log_message(message, label="text")
    bot.send_message(message.chat.id, "Команда не распознана. Используйте /next, /start, /pause или /resume.")

def scheduler_debug():
    while True:
        send_daily_notification()
        time.sleep(10)

def scheduler_production():
    schedule.every().day.at("05:00").do(send_daily_notification)
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
    logging.info("Переходим в режим polling...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30, skip_pending=True, allowed_updates=telebot.util.update_types)
    except Exception as e:
        logging.exception(f"Polling упал с ошибкой: {e}")
        raise

if __name__ == '__main__':
    main()
