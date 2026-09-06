import os
import logging
import threading
from flask import Flask
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import google.generativeai as genai

# إعداد خادم وهمي لإبقاء Render يعمل
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# إعداد التسجيل (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! بوت التحليل الفني جاهز للعمل.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("الأوامر المتاحة:\n/price - عرض السعر\n/signal - إشارة التداول")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت يعمل بنجاح!")

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري جلب الأسعار...")

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري تحليل السوق...")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("الرصيد الحالي: 1000 USDT")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم تسجيل أمر الشراء.")

async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم تسجيل أمر البيع.")

async def target_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("الأهداف المحققة...")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إيقاف التنبيهات.")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("الإعدادات الحالية...")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("خطأ: لم يتم ضبط TELEGRAM_BOT_TOKEN")
        return

    # تشغيل الخادم الوهمي في المسار الخلفي
    threading.Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("sell", sell_command))
    app.add_handler(CommandHandler("target", target_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("settings", settings_command))

    logger.info("تم تشغيل البوت باستمرار (Polling Mode)...")
    app.run_polling(poll_interval=3.0, drop_pending_updates=True)

if __name__ == "__main__":
    main()
