import os
import logging
import asyncio
from fastapi import FastAPI, Request, HTTPException
from telegram import Bot, Update, ChatAction
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters
import openai

# تنظیمات لاگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# بارگذاری متغیرهای محیطی
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("توکن تلگرام یا کلید OpenAI تنظیم نشده‌اند!")

openai.api_key = OPENAI_API_KEY

app = FastAPI()
bot = Bot(token=TELEGRAM_TOKEN)

# ساخت Dispatcher برای مدیریت آپدیت‌ها
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

# تابع async برای ارسال سوال به OpenAI و دریافت پاسخ
async def ask_openai(question: str) -> str:
    try:
        response = await asyncio.to_thread(
            lambda: openai.Completion.create(
                engine="text-davinci-003",
                prompt=question,
                max_tokens=150,
                temperature=0.7,
                n=1,
                stop=None,
            )
        )
        answer = response.choices[0].text.strip()
        return answer
    except Exception as e:
        logger.error(f"خطا در تماس با OpenAI: {e}")
        return "متاسفانه در پاسخگویی به سوال شما مشکلی پیش آمده."

# هندلر دستور /start
def start(update, context):
    update.message.reply_text("سلام! من ربات هوش مصنوعی شما هستم. هر سوالی داری بپرس!")

# هندلر پیام‌های متنی (async کامل)
async def handle_message(update, context):
    user_text = update.message.text
    chat_id = update.message.chat.id

    logger.info(f"پیام از کاربر: {user_text}")

    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    answer = await ask_openai(user_text)
    await bot.send_message(chat_id=chat_id, text=answer)

# اضافه کردن هندلرها به Dispatcher
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# مسیر اصلی برای دریافت آپدیت‌ها از تلگرام (وبهوک)
@app.post("/")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        dispatcher.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"خطا در دریافت آپدیت تلگرام: {e}")
        raise HTTPException(status_code=400, detail="Bad Request")
