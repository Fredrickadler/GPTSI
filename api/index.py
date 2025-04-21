import os
import logging
from fastapi import FastAPI, Request, HTTPException
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from telegram.ext.dispatcher import run_async
import openai
import asyncio

# تنظیمات لاگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# بارگذاری توکن‌ها از متغیرهای محیطی
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("توکن تلگرام یا کلید OpenAI تنظیم نشده‌اند!")

openai.api_key = OPENAI_API_KEY

app = FastAPI()
bot = Bot(token=TELEGRAM_TOKEN)

# ساخت دیسپچر برای مدیریت آپدیت‌ها
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

# تابع برای ارسال درخواست به OpenAI
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

# هندلر پیام‌های متنی
@run_async
def handle_message(update, context):
    user_text = update.message.text
    chat_id = update.message.chat_id

    logger.info(f"پیام از کاربر: {user_text}")

    # ارسال پیام در حال پردازش
    bot.send_chat_action(chat_id=chat_id, action="typing")

    # اجرای تابع OpenAI به صورت async
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    answer = loop.run_until_complete(ask_openai(user_text))

    bot.send_message(chat_id=chat_id, text=answer)

# اضافه کردن هندلرها به دیسپچر
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

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
