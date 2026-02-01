import os
import logging
import requests
import base64
import asyncio
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
HF_TOKEN = os.getenv('HF_TOKEN')

if not TELEGRAM_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
    exit(1)
if not HF_TOKEN:
    logger.error("❌ HF_TOKEN не установлен!")
    exit(1)

# ПРАВИЛЬНЫЙ ЭНДПОИНТ + ЗАГОЛОВОК ДЛЯ НОВОГО РОУТЕРА
API_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen2-VL-7B-Instruct"
HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json",
    "X-HF-Router": "v2"  # 🔑 КРИТИЧЕСКИ ВАЖНЫЙ ЗАГОЛОВОК ДЛЯ 2026 ГОДА
}

SYSTEM_PROMPT = """Ты опытный школьный репетитор для учеников 11 класса. 
Реши задачу по шагам с подробными объяснениями. Выдели финальный ответ словом "Ответ:".
Пиши на русском языке. Если на фото нет учебной задачи — ответь только "ОШИБКА"."""

user_contexts = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Привет! Я — бесплатный бот-репетитор для 11 класса.\n\n"
        "Отправь мне фото задачи, и я решу её по шагам!\n"
        "Жду твоё фото! 📱"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = await update.message.reply_text("⏳ Анализирую задачу... (30–60 секунд)")

    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')

        payload = {
            "inputs": {
                "image": base64_image,
                "text": SYSTEM_PROMPT + "\n\nРеши задачу на изображении."
            },
            "parameters": {
                "max_new_tokens": 2048,
                "temperature": 0.3
            }
        }

        for attempt in range(3):
            try:
                response = requests.post(
                    API_URL,
                    headers=HEADERS,
                    json=payload,
                    timeout=60
                )
                
                # Отладка: если ответ не JSON — логируем тело
                try:
                    result = response.json()
                except Exception:
                    logger.warning(f"Не-JSON ответ ({response.status_code}): {response.text[:200]}")
                    if attempt < 2:
                        await asyncio.sleep(15)
                        continue
                    raise Exception(f"Сервер вернул не-JSON: {response.status_code}")
                
                if response.status_code == 200:
                    break
                elif response.status_code == 503 and "estimated_time" in str(result):
                    wait_time = result.get("estimated_time", 30)
                    await msg.edit_text(f"🔄 Модель запускается... Подождите ~{int(wait_time)} секунд")
                    await asyncio.sleep(max(10, wait_time))
                    continue
                else:
                    error_detail = result.get("error", "Unknown error")
                    raise Exception(f"HTTP {response.status_code}: {error_detail}")
                    
            except requests.Timeout:
                if attempt == 2:
                    raise
                await asyncio.sleep(10)

        solution = result[0].get('generated_text', '').strip() if isinstance(result, list) else result.get('generated_text', '').strip()

        if not solution or "ОШИБКА" in solution.upper()[:50]:
            await msg.edit_text("❌ На фото не обнаружена учебная задача.\nПопробуйте чёткое фото из учебника.")
            return

        user_contexts[user_id] = {'image_bytes': photo_bytes, 'solution': solution}
        await msg.delete()

        if len(solution) > 4000:
            for i in range(0, len(solution), 4000):
                await update.message.reply_text(solution[i:i+4000])
        else:
            await update.message.reply_text(solution)

        await update.message.reply_text("❓ Есть вопросы? Напиши их текстом!")

    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}", exc_info=True)
        await msg.edit_text(
            "❌ Не удалось решить задачу.\n"
            "Попробуйте отправить фото ещё раз через 1–2 минуты."
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_contexts:
        await update.message.reply_text("📸 Сначала отправь фото задачи!")
        return

    msg = await update.message.reply_text("⏳ Думаю над твоим вопросом...")

    try:
        context_data = user_contexts[user_id]
        base64_image = base64.b64encode(context_data['image_bytes']).decode('utf-8')

        followup_prompt = f"""Ты репетитор. Вот решение:

{context_data['solution']}

Вопрос: {update.message.text}

Ответь кратко на русском."""

        payload = {
            "inputs": {
                "image": base64_image,
                "text": followup_prompt
            },
            "parameters": {"max_new_tokens": 1024}
        }

        response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=40)
        result = response.json()
        answer = result[0].get('generated_text', '').strip() if isinstance(result, list) else result.get('generated_text', '').strip()

        await msg.delete()
        await update.message.reply_text(answer if answer else "❌ Не понял вопрос. Попробуй иначе.")

    except Exception as e:
        logger.error(f"Ошибка текста: {e}", exc_info=True)
        await msg.edit_text("❌ Ошибка ответа. Попробуй переформулировать.")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("🚀 Бот запущен! Модель: Qwen2-VL-7B (HF Router v2)")
    application.run_polling()

if __name__ == '__main__':
    main()