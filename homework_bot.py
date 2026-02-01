import os
import logging
import requests
import base64
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import io

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# ИСПОЛЬЗУЕМ ДОСТУПНУЮ МОДЕЛЬ ИЗ ВАШЕГО СПИСКА
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-001:generateContent?key={GEMINI_API_KEY}"

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    logger.error("❌ Не установлены переменные окружения")
    exit(1)

SYSTEM_PROMPT = """Ты опытный школьный репетитор для учеников 11 класса. 
Реши задачу по шагам с подробными объяснениями. Выдели финальный ответ словом "Ответ:".
Пиши на русском языке. Если на фото нет задачи — ответь "ОШИБКА"."""

user_contexts = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Отправь фото задачи — решу по шагам!")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("⏳ Анализирую задачу... (8-15 сек)")
    
    try:
        # Получаем фото
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        
        # Формируем запрос к gemini-2.0-flash-001
        payload = {
            "contents": [{
                "parts": [
                    {"text": SYSTEM_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }],
            "generation_config": {
                "max_output_tokens": 2048,
                "temperature": 0.2
            },
            "safety_settings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }
        
        # Отправляем запрос
        response = requests.post(GEMINI_API_URL, json=payload, timeout=30)
        
        if response.status_code != 200:
            error_detail = response.json().get('error', {}).get('message', 'Unknown error')
            logger.error(f"Gemini API error {response.status_code}: {error_detail}")
            await update.message.reply_text("❌ Ошибка ИИ. Попробуйте позже.")
            return
        
        data = response.json()
        solution = data['candidates'][0]['content']['parts'][0]['text'].strip()
        
        if "ОШИБКА" in solution.upper()[:50]:
            await update.message.reply_text("❌ На фото не обнаружена учебная задача.")
            return
        
        user_contexts[user_id] = {'image_bytes': photo_bytes, 'solution': solution}
        
        # Отправляем решение
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
        base64_image = base64.b64encode(context_data['image_bytes']).decode('utf-8')
        
        followup_prompt = f"""Ты репетитор. Вот решение задачи:

{context_data['solution']}

Ученик спрашивает: {update.message.text}

Ответь кратко на русском языке."""
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": followup_prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }],
            "generation_config": {"max_output_tokens": 1024}
        }
        
        response = requests.post(GEMINI_API_URL, json=payload, timeout=20)
        if response.status_code != 200:
            raise Exception(f"API error {response.status_code}")
        
        data = response.json()
        answer = data['candidates'][0]['content']['parts'][0]['text'].strip()
        await update.message.reply_text(answer)
        
    except Exception as e:
        logger.error(f"Ошибка текста: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка ответа. Попробуйте переформулировать.")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("🚀 Бот запущен! Модель: gemini-2.0-flash-001")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()