import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from PIL import Image
import io
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация API ключей
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Проверка ключей
if not TELEGRAM_TOKEN:
    logger.error("❌ Не установлен TELEGRAM_BOT_TOKEN в .env")
    exit(1)
if not GEMINI_API_KEY or not GEMINI_API_KEY.startswith("AIzaSy"):
    logger.error("❌ Неверный GEMINI_API_KEY в .env")
    exit(1)

# Инициализация Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    # Тестовый запрос (для версии 0.7.2 используем правильный синтаксис)
    test_resp = model.generate_content("Тест")
    if not test_resp.candidates or not test_resp.candidates[0].content.parts:
        raise Exception("Пустой ответ от API")
    logger.info("✅ Gemini API подключён (версия google-generativeai: 0.7.2)")
except Exception as e:
    logger.error(f"❌ Ошибка Gemini: {e}")
    exit(1)

SYSTEM_PROMPT = """Ты опытный школьный репетитор для учеников 11 класса. 
Твоя задача - помогать решать задачи по всем школьным предметам.

ВАЖНО:
1. Давай ПОЛНОЕ пошаговое решение
2. Пиши простым текстом без форматирования
3. Нумеруй шаги (Шаг 1, Шаг 2...)
4. В конце выдели финальный ответ словом "Ответ:"
5. Пиши на русском языке

Если на изображении НЕТ учебной задачи - ответь только "ОШИБКА"."""

user_contexts = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Отправь фото задачи — решу по шагам!\n"
        "Поддерживаю все предметы 11 класса."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("⏳ Анализирую задачу... (10-20 сек)")
    
    try:
        # Получаем фото
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        image = Image.open(io.BytesIO(photo_bytes))
        
        # Запрос к Gemini (для версии 0.7.2)
        response = model.generate_content(
            [SYSTEM_PROMPT, image],
            generation_config=genai.types.GenerationConfig(max_output_tokens=2048),
            safety_settings={
                "HARASSMENT": "BLOCK_NONE",
                "HATE": "BLOCK_NONE",
                "SEXUAL": "BLOCK_NONE",
                "DANGEROUS": "BLOCK_NONE"
            }
        )
        
        # === КРИТИЧЕСКИ ВАЖНО ДЛЯ ВЕРСИИ 0.7.2 ===
        if not response.candidates or not response.candidates[0].content.parts:
            await update.message.reply_text("❌ Не удалось распознать задачу. Отправьте чёткое фото.")
            return
        
        solution = response.candidates[0].content.parts[0].text.strip()
        
        # Проверка на ошибку
        if "ОШИБКА" in solution.upper()[:50]:
            await update.message.reply_text("❌ На фото не обнаружена учебная задача.")
            return
        
        # Сохраняем контекст
        user_contexts[user_id] = {'image': image, 'solution': solution}
        
        # Отправка ответа
        if len(solution) > 4000:
            for i in range(0, len(solution), 4000):
                await update.message.reply_text(solution[i:i+4000])
        else:
            await update.message.reply_text(solution)
            
        await update.message.reply_text("❓ Есть вопросы? Напиши их текстом!")
        
    except Exception as e:
        logger.error(f"Ошибка фото: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка обработки. Попробуйте другое фото.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_contexts:
        await update.message.reply_text("📸 Сначала отправь фото задачи!")
        return
    
    await update.message.reply_text("⏳ Обрабатываю вопрос...")
    
    try:
        context_data = user_contexts[user_id]
        followup_prompt = f"""Ты репетитор. Вот предыдущее решение:

{context_data['solution']}

Ученик спрашивает: {update.message.text}

Ответь кратко и по делу на русском языке."""
        
        response = model.generate_content(
            [followup_prompt, context_data['image']],
            generation_config=genai.types.GenerationConfig(max_output_tokens=1024)
        )
        
        if not response.candidates or not response.candidates[0].content.parts:
            await update.message.reply_text("❌ Не понял вопрос. Повторите иначе.")
            return
            
        answer = response.candidates[0].content.parts[0].text.strip()
        await update.message.reply_text(answer)
        
    except Exception as e:
        logger.error(f"Ошибка текста: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка ответа. Попробуйте переформулировать.")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("🚀 Бот запущен! Версии: PTB=21.0.1, Gemini=0.7.2")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()