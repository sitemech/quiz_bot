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
**Примечание:** На сервере используется Python 3.8.20. Убедитесь, что версии библиотек в `requirements.txt` совместимы с этой версией Python. Например, `pyTelegramBotAPI==4.26.0` требует Python 3.9+, что может вызвать проблемы.

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

### Запуск через Supervisor (рекомендуется)

1.  Установите Supervisor (если не установлен):
    ```bash
    sudo apt install supervisor -y
    ```
2.  Создайте файл конфигурации для вашего бота, например, `/etc/supervisor/conf.d/quiz_bot.conf`:
    ```ini
    [program:quiz_bot]
    directory=/home/ubuntu/quiz_bot
    command=/home/ubuntu/quiz_bot/quiz_bot_env/bin/python main.py
    autostart=true
    autorestart=true
    stderr_logfile=/var/log/quiz_bot.err.log
    stdout_logfile=/var/log/quiz_bot.out.log
    user=ubuntu
    environment=PATH="/home/ubuntu/quiz_bot/quiz_bot_env/bin"
    ```
    **Важно:** Убедитесь, что пути (`directory`, `command`, `environment`) и имя файла запуска (`main.py`) соответствуют вашему проекту.

3.  Перезагрузите Supervisor, чтобы применить изменения:
    ```bash
    sudo supervisorctl reread
    sudo supervisorctl update
    ```
4.  Запустите или перезапустите сервис:
    ```bash
    sudo supervisorctl restart quiz_bot
    ```

## Мониторинг

### Просмотр логов

**Supervisor:**
```bash
sudo cat /var/log/quiz_bot.out.log -f
sudo cat /var/log/quiz_bot.err.log -f
```

### Проверка работы бота

1. Отправьте команду `/start` боту в Telegram
2. Проверьте логи на наличие ошибок
3. Убедитесь, что файл `subscribers.json` создается

### Перезапуск

**Supervisor:**
```bash
sudo supervisorctl restart quiz_bot
```

## Обновление

### Обновление кода

1.  Подключитесь к серверу по SSH.
2.  Перейдите в директорию проекта:
    ```bash
    cd /home/ubuntu/quiz_bot # Замените на актуальный путь
    ```
3.  Выполните `git pull` для получения последних изменений (если используете Git):
    ```bash
    git pull
    ```
    Если текущая ветка не отслеживает удаленную, сначала установите отслеживание:
    ```bash
    git branch --set-upstream-to=origin/main main # Предполагается, что основная ветка называется main
    git pull
    ```
    или загрузите новые файлы вручную.
4.  Обновите зависимости (если необходимо):
    ```bash
    source quiz_bot_env/bin/activate # Активируйте виртуальное окружение
    pip3 install -r requirements.txt --upgrade
    ```
5.  Перезапустите сервис через Supervisor:
    ```bash
    sudo supervisorctl restart quiz_bot
    ```

## Устранение проблем

### Бот не отвечает

1. Проверьте статус Supervisor:
   ```bash
   sudo supervisorctl status
   ```
2. Проверьте логи Supervisor:
   ```bash
   sudo cat /var/log/quiz_bot.out.log
   sudo cat /var/log/quiz_bot.err.log
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
chmod 644 main.py
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
- `main.py` - основной код

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
ps aux | grep main.py

# Использование CPU
top -p $(pgrep -f main.py)
```

### Оптимизация

- Бот использует минимальные ресурсы
- При большом количестве подписчиков рассмотрите:
  - Кэширование расписания
  - Асинхронные запросы
  - База данных вместо JSON

---

**Версия:** 1.1 (Обновлено)
**Дата:** 2025-11-29

