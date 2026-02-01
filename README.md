# Бот-помощник для решения школьных задач (11 класс)

Telegram бот, который решает школьные задачи по фотографии с использованием Google Gemini AI.

## Возможности

- Решает задачи по всем предметам 11 класса
- Даёт пошаговые решения
- Позволяет задавать уточняющие вопросы
- Бесплатный (до 1500 запросов в день)

## Установка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Получение токенов

#### Telegram Bot Token:
1. Открой Telegram и найди бота [@BotFather](https://t.me/BotFather)
2. Отправь команду `/newbot`
3. Следуй инструкциям (придумай имя и username для бота)
4. Скопируй полученный токен

#### Google Gemini API Key:
1. Перейди на [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Войди через Google аккаунт
3. Нажми "Create API Key"
4. Скопируй ключ

### 3. Настройка переменных окружения

Создай файл `.env` в корневой папке проекта:

```bash
cp .env.example .env
```

Открой `.env` и вставь свои токены:

```
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
GEMINI_API_KEY=AIzaSyD...
```

### 4. Запуск бота

#### Linux/MacOS:
```bash
export $(cat .env | xargs)
python homework_bot.py
```

#### Windows (PowerShell):
```powershell
Get-Content .env | ForEach-Object {
    $name, $value = $_.split('=')
    Set-Item -Path "env:$name" -Value $value
}
python homework_bot.py
```

#### Альтернативный способ (любая ОС):
Установи пакет `python-dotenv`:
```bash
pip install python-dotenv
```

Добавь в начало `homework_bot.py` (после импортов):
```python
from dotenv import load_dotenv
load_dotenv()
```

Затем просто:
```bash
python homework_bot.py
```

## Использование

1. Найди своего бота в Telegram по username, который задал при создании
2. Нажми `/start`
3. Отправь фото задачи
4. Получи пошаговое решение
5. Можешь задать уточняющий вопрос текстом

## Структура проекта

```
.
├── homework_bot.py      # Основной код бота
├── requirements.txt     # Зависимости Python
├── .env.example         # Шаблон для переменных окружения
├── .env                 # Твои токены (создаётся вручную, не коммитится)
└── README.md           # Эта инструкция
```

## Лимиты

- Google Gemini Free tier: 1500 запросов в день
- Этого хватит на ~100-150 задач с уточнениями в день

## Возможные проблемы и решения

### Ошибка "No module named 'telegram'"
```bash
pip install --upgrade python-telegram-bot
```

### Ошибка "Invalid token"
Проверь, что правильно скопировал токен от @BotFather в .env файл

### Ошибка "GEMINI_API_KEY not found"
Проверь, что создал .env файл и экспортировал переменные окружения

### Бот не отвечает
Убедись, что:
- Бот запущен (скрипт работает)
- Переменные окружения установлены
- Интернет работает

## Деплой на сервер (опционально)

Для постоянной работы бота можно развернуть на:
- VPS (DigitalOcean, Hetzner, и т.д.)
- Heroku
- Railway
- PythonAnywhere

## Поддержка

При возникновении проблем проверь логи в консоли - бот выводит подробную информацию об ошибках.
