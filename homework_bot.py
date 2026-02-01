import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from PIL import Image
import io
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация API ключей из .env
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# === ПРОВЕРКА КЛЮЧЕЙ ПЕРЕД ЗАПУСКОМ ===
if not TELEGRAM_TOKEN:
    logger.error("❌ Не установлен TELEGRAM_BOT_TOKEN в .env файле")
    exit(1)

if not GEMINI_API_KEY:
    logger.error("❌ Не установлен GEMINI_API_KEY в .env файле")
    exit(1)

if not GEMINI_API_KEY.startswith("AIzaSy"):
    logger.error("❌ Неверный формат GEMINI_API_KEY (должен начинаться с 'AIzaSy')")
    exit(1)

# Инициализация Gemini с проверкой подключения
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    # Тестовый запрос для проверки подключения
    test_resp = model.generate_content("Привет, это тестовое сообщение")
    logger.info("✅ Gemini API подключён успешно (модель: gemini-1.5-flash)")
except Exception as e:
    logger.error(f"❌ Ошибка подключения к Gemini API: {e}")
    logger.error("Проверьте: 1) Ключ в .env 2) Generative Language API включён в Google Cloud Console")
    exit(1)

# Системный промпт для решения задач
SYSTEM_PROMPT = """Ты опытный школьный репетитор для учеников 11 класса. 
Твоя задача - помогать решать задачи по всем школьным предметам: математика (алгебра, геометрия), 
физика, химия, русский язык, литература, биология, история, обществознание, английский язык.

ВАЖНО:
1. Давай ПОЛНОЕ пошаговое решение с подробными объяснениями каждого шага
2. Пиши простым текстом, без специального форматирования
3. Нумеруй шаги (Шаг 1, Шаг 2 и т.д.)
4. В конце обязательно выдели финальный ответ жирным шрифтом или словом "Ответ:"
5. Пиши на русском языке

Если на изображении НЕТ учебной задачи или изображение невозможно распознать - ответь только словом "ОШИБКА"."""

# Хранилище контекста последней задачи для каждого пользователя
user_contexts = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "📸 Привет! Я — бот-репетитор для 11 класса.\n\n"
        "Отправь мне фото задачи, и я:\n"
        "✅ Решу её по шагам\n"
        "✅ Объясню каждое действие\n"
        "✅ Выделю финальный ответ\n\n"
        "Жду твоё фото! 📱"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий с задачами"""
    user_id = update.effective_user.id
    
    await update.message.reply_text("⏳ Анализирую задачу... (10-15 секунд)")
    
    try:
        # Получаем фото (самое большое разрешение)
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Конвертируем в PIL Image
        image = Image.open(io.BytesIO(photo_bytes))
        
        # Отправляем в Gemini
        try:
            response = model.generate_content(
                [SYSTEM_PROMPT, image],
                generation_config={"max_output_tokens": 2048},
                safety_settings={
                    "HARASSMENT": "BLOCK_NONE",
                    "HATE": "BLOCK_NONE",
                    "SEXUAL": "BLOCK_NONE",
                    "DANGEROUS": "BLOCK_NONE"
                }
            )
            
            # Проверка валидности ответа
            if not hasattr(response, 'text') or not response.text.strip():
                await update.message.reply_text(
                    "❌ Не удалось распознать задачу. Возможные причины:\n"
                    "• Фото слишком размытое\n"
                    "• Задача написана от руки неразборчиво\n"
                    "• На фото нет учебного задания\n\n"
                    "Попробуйте сфотографировать чётче!"
                )
                return
            
            solution = response.text.strip()
            
        except Exception as gemini_error:
            logger.error(f"Gemini API ошибка: {gemini_error}")
            await update.message.reply_text(
                "❌ Ошибка ИИ-сервиса. Попробуйте отправить фото ещё раз через 10 секунд."
            )
            return
        
        # Проверяем на ошибку распознавания
        if "ОШИБКА" in solution.upper()[:50]:
            await update.message.reply_text(
                "❌ На фото не обнаружена учебная задача.\n"
                "Пожалуйста, отправьте чёткое фото задачи из учебника или тетради."
            )
            return
        
        # Сохраняем контекст для уточняющих вопросов
        user_contexts[user_id] = {
            'image': image,
            'solution': solution
        }
        
        # Отправляем решение (разбиваем на части если длинное)
        if len(solution) > 4000:
            parts = [solution[i:i+4000] for i in range(0, len(solution), 4000)]
            for i, part in enumerate(parts, 1):
                await update.message.reply_text(f"Часть {i}/{len(parts)}:\n\n{part}")
        else:
            await update.message.reply_text(solution)
        
        # Добавляем подсказку для уточняющих вопросов
        await update.message.reply_text(
            "❓ Есть вопросы по решению? Напиши их текстом — я объясню любой шаг подробнее!"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Техническая ошибка. Попробуйте отправить фото ещё раз.\n"
            "Если ошибка повторится — напишите разработчику."
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (уточняющие вопросы)"""
    user_id = update.effective_user.id
    user_question = update.message.text
    
    # Игнорируем команды
    if user_question.startswith('/'):
        return
    
    # Проверяем, есть ли контекст последней задачи
    if user_id not in user_contexts:
        await update.message.reply_text(
            "📸 Сначала отправь фото задачи, а потом задавай вопросы по её решению!"
        )
        return
    
    await update.message.reply_text("⏳ Думаю над твоим вопросом...")
    
    try:
        # Получаем сохранённый контекст
        context_data = user_contexts[user_id]
        image = context_data['image']
        previous_solution = context_data['solution']
        
        # Формируем промпт с контекстом
        followup_prompt = f"""Ты опытный школьный репетитор для учеников 11 класса.

Вот задача и её решение:

{previous_solution}

---

Ученик задал уточняющий вопрос: {user_question}

Ответь на вопрос подробно, но кратко. Если нужно, объясни конкретный шаг решения более детально.
Пиши на русском языке."""

        # Отправляем запрос
        response = model.generate_content(
            [followup_prompt, image],
            generation_config={"max_output_tokens": 1024}
        )
        
        if not hasattr(response, 'text') or not response.text.strip():
            await update.message.reply_text("❌ Не удалось обработать вопрос. Попробуй сформулировать иначе.")
            return
        
        answer = response.text.strip()
        
        await update.message.reply_text(answer)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке уточняющего вопроса: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ошибка при обработке вопроса. Попробуй задать его ещё раз."
        )


def main():
    """Запуск бота"""
    # Создание приложения
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Запуск бота
    logger.info("🚀 Бот запущен и готов помогать с домашкой!")
    logger.info(f"Ваш бот: https://t.me/{application.bot.username}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    # Проверка зависимостей
    required_packages = ['google-generativeai', 'python-telegram-bot', 'pillow', 'python-dotenv']
    logger.info("✅ Все проверки пройдены. Запускаем бота...")
    main()