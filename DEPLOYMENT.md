# Инструкция по развертыванию NestQuiz

## Подготовка сервера

### 1. Обновление системы

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Установка Python и pip

```bash
sudo apt install python3 python3-pip -y
```

### 3. Установка зависимостей проекта

```bash
cd /path/to/NestQuiz
pip3 install -r requirements.txt
```

## Настройка бота

### 1. Создание конфигурации

Создайте файл `config.py`:

```python
import os

TOKEN = os.getenv("BOT_TOKEN", "ваш_токен_здесь")
```

### 2. Настройка переменных окружения (рекомендуется)

```bash
export BOT_TOKEN="ваш_токен_здесь"
```

Или добавьте в `~/.bashrc`:
```bash
echo 'export BOT_TOKEN="ваш_токен_здесь"' >> ~/.bashrc
source ~/.bashrc
```

## Запуск

### Вариант 1: Запуск в фоне (screen)

```bash
# Установка screen (если не установлен)
sudo apt install screen -y

# Создание сессии
screen -S nestquiz

# Запуск бота
cd /path/to/NestQuiz
python3 main2.py

# Отсоединение: Ctrl+A, затем D
# Подключение: screen -r nestquiz
```

### Вариант 2: Systemd сервис (рекомендуется)

1. Создайте файл `/etc/systemd/system/nestquiz.service`:

```ini
[Unit]
Description=NestQuiz Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/NestQuiz
Environment="BOT_TOKEN=ваш_токен_здесь"
ExecStart=/usr/bin/python3 /home/ubuntu/NestQuiz/main2.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

2. Замените пути на актуальные:
   - `WorkingDirectory` - путь к проекту
   - `ExecStart` - полный путь к main2.py
   - `BOT_TOKEN` - ваш токен

3. Запуск сервиса:

```bash
# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable nestquiz

# Запуск сервиса
sudo systemctl start nestquiz

# Проверка статуса
sudo systemctl status nestquiz

# Просмотр логов
sudo journalctl -u nestquiz -f
```

### Вариант 3: Запуск в фоне (nohup)

```bash
cd /path/to/NestQuiz
nohup python3 main2.py > bot.log 2>&1 &
```

Проверка:
```bash
ps aux | grep main2.py
tail -f bot.log
```

## Мониторинг

### Просмотр логов

**Systemd:**
```bash
sudo journalctl -u nestquiz -f
sudo journalctl -u nestquiz --since "1 hour ago"
```

**Screen:**
```bash
screen -r nestquiz
```

**Nohup:**
```bash
tail -f bot.log
```

### Проверка работы бота

1. Отправьте команду `/start` боту в Telegram
2. Проверьте логи на наличие ошибок
3. Убедитесь, что файл `subscribers.json` создается

### Перезапуск

**Systemd:**
```bash
sudo systemctl restart nestquiz
```

**Screen:**
```bash
screen -r nestquiz
# Ctrl+C для остановки
python3 main2.py  # для запуска
```

**Nohup:**
```bash
pkill -f main2.py
nohup python3 main2.py > bot.log 2>&1 &
```

## Обновление

### Обновление кода

```bash
cd /path/to/NestQuiz
git pull  # если используете git
# или загрузите новые файлы

# Перезапуск
sudo systemctl restart nestquiz
```

### Обновление зависимостей

```bash
pip3 install -r requirements.txt --upgrade
sudo systemctl restart nestquiz
```

## Устранение проблем

### Бот не отвечает

1. Проверьте статус:
```bash
sudo systemctl status nestquiz
```

2. Проверьте логи:
```bash
sudo journalctl -u nestquiz -n 50
```

3. Проверьте токен в `config.py`

4. Проверьте доступность интернета:
```bash
ping api.telegram.org
```

### Ошибки парсинга

1. Проверьте доступность сайта:
```bash
curl https://ufa.quizplease.ru/schedule
```

2. Проверьте логи на ошибки парсинга

3. Возможно, изменилась структура HTML сайта

### Проблемы с правами доступа

```bash
# Убедитесь, что у пользователя есть права на файлы
chmod 644 config.py
chmod 644 main2.py
chmod 666 subscribers.json  # для записи
```

## Безопасность

### Рекомендации

1. **Не храните токен в коде:**
   - Используйте переменные окружения
   - Или файл `.env` (не коммитьте!)

2. **Ограничьте доступ к файлам:**
```bash
chmod 600 config.py  # только владелец
```

3. **Firewall:**
```bash
# Бот не требует входящих портов
# Но можно ограничить исходящие соединения
```

4. **Регулярные обновления:**
```bash
sudo apt update && sudo apt upgrade -y
```

## Резервное копирование

### Важные файлы для бэкапа

- `subscribers.json` - список подписчиков
- `config.py` - конфигурация (если не используете env)
- `main2.py` - основной код

### Автоматический бэкап (cron)

Создайте скрипт `/home/ubuntu/backup_nestquiz.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/home/ubuntu/backups/nestquiz"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
cp /path/to/NestQuiz/subscribers.json $BACKUP_DIR/subscribers_$DATE.json
# Хранить только последние 7 дней
find $BACKUP_DIR -name "subscribers_*.json" -mtime +7 -delete
```

Добавьте в crontab:
```bash
crontab -e
# Добавьте строку:
0 2 * * * /home/ubuntu/backup_nestquiz.sh
```

## Производительность

### Мониторинг ресурсов

```bash
# Использование памяти
ps aux | grep main2.py

# Использование CPU
top -p $(pgrep -f main2.py)
```

### Оптимизация

- Бот использует минимальные ресурсы
- При большом количестве подписчиков рассмотрите:
  - Кэширование расписания
  - Асинхронные запросы
  - База данных вместо JSON

---

**Версия:** 1.0  
**Дата:** 2025-11-29

