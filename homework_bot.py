import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from PIL import Image
import io

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация API ключей (нужно установить переменные окружения)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Инициализация Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Системный промпт для решения задач
SYSTEM_PROMPT = """Ты опытный школьный репетитор для учеников 11 класса. 
Твоя задача - помогать решать задачи по всем школьным предметам: математика (алгебра, геометрия), 
физика, химия, русский язык, литература, биология, история, обществознание, английский язык.

ВАЖНО:
1. Давай ПОЛНОЕ пошаговое решение с подробными объяснениями каждого шага
2. Пиши простым текстом, без специального форматирования
3. Нумеруй шаги (Шаг 1, Шаг 2 и т.д.)
4. В конце обязательно выдели финальный ответ
5. Пиши на русском языке

Если на изображении НЕТ учебной задачи или изображение невозможно распознать - ответь только словом "ОШИБКА"."""

# Хранилище контекста последней задачи для каждого пользователя
user_contexts = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text("Отправь фото задачи, и я решу её пошагово!")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий с задачами"""
    user_id = update.effective_user.id
    
    try:
        # Получаем фото (самое большое разрешение)
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Конвертируем в PIL Image
        image = Image.open(io.BytesIO(photo_bytes))
        
        # Отправляем в Gemini
        response = model.generate_content([SYSTEM_PROMPT, image])
        solution = response.text.strip()
        
        # Проверяем на ошибку распознавания
        if solution == "ОШИБКА" or "ОШИБКА" in solution[:20]:
            await update.message.reply_text("Ошибка, повторите загрузку")
            return
        
        # Сохраняем контекст последней задачи для возможности уточняющих вопросов
        user_contexts[user_id] = {
            'image': image,
            'solution': solution
        }
        
        # Отправляем решение
        await update.message.reply_text(solution)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}")
        await update.message.reply_text("Ошибка, повторите загрузку")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (уточняющие вопросы)"""
    user_id = update.effective_user.id
    user_question = update.message.text
    
    # Проверяем, есть ли контекст последней задачи
    if user_id not in user_contexts:
        await update.message.reply_text("Сначала отправь фото задачи")
        return
    
    try:
        # Получаем сохранённый контекст
        context_data = user_contexts[user_id]
        image = context_data['image']
        previous_solution = context_data['solution']
        
        # Формируем промпт с контекстом
        followup_prompt = f"""Ты опытный школьный репетитор для учеников 11 класса.

Вот задача с изображения и её решение, которое ты дал ранее:

{previous_solution}

---

Ученик задал уточняющий вопрос: {user_question}

Ответь на его вопрос подробно, но кратко. Если нужно, объясни конкретный шаг решения более детально."""

        # Отправляем запрос с изображением и контекстом
        response = model.generate_content([followup_prompt, image])
        answer = response.text.strip()
        
        await update.message.reply_text(answer)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке уточняющего вопроса: {e}")
        await update.message.reply_text("Ошибка, повторите загрузку")


def main():
    """Запуск бота"""
    # Проверка наличия токенов
    if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
        logger.error("Не установлены переменные окружения TELEGRAM_BOT_TOKEN и GEMINI_API_KEY")
        return
    
    # Создание приложения
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Запуск бота
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
