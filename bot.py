import os
import logging
import threading
import requests
from flask import Flask
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import google.generativeai as genai

flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

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

def get_crypto_price(symbol="BTCUSDT"):
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
        response = requests.get(url, timeout=10)
        data = response.json()
        return {
            "symbol": symbol,
            "price": float(data["lastPrice"]),
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
            "change": float(data["priceChangePercent"])
        }
    except Exception as e:
        logger.error(f"خطأ السعر: {e}")
        return None

def generate_analysis(data):
    if not GEMINI_API_KEY:
        return "خطأ: مفتاح GEMINI_API_KEY غير مضاف في Render."
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"تحليل فني لعملة {data['symbol']}:\n"
            f"السعر: {data['price']} USDT\n"
            f"أعلى سعر: {data['high']}\n"
            f"أدنى سعر: {data['low']}\n"
            f"التغير: {data['change']}%\n\n"
            f"قدم تحليلاً مختصراً جداً بدون رموز معقدة: الاتجاه، الدعم والمقاومة، والتوصية."
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"خطأ Gemini: {e}")
        return "تعذر إكمال التحليل الفني."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك! البوت جاهز.\nارسل الآن:\n/analyze BTC\nأو\n/analyze SOL"
    )

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = "BTCUSDT"
    if context.args:
        user_symbol = context.args[0].upper()
        symbol = user_symbol if user_symbol.endswith("USDT") else f"{user_symbol}USDT"

    await update.message.reply_text(f"⏳ جاري تحليل {symbol}...")
    
    market_data = get_crypto_price(symbol)
    if not market_data:
        await update.message.reply_text("تعذر جلب البيانات من Binance. تأكد من رمز العملة.")
        return

    analysis_result = generate_analysis(market_data)
    
    message = (
        f"📊 تحليل {symbol}\n\n"
        f"💵 السعر الحالي: {market_data['price']} USDT\n"
        f"📈 التغير (24h): {market_data['change']}%\n\n"
        f"--- رأي الذكاء الاصطناعي ---\n"
        f"{analysis_result}"
    )
    # إرسال النص بدون parse_mode لتفادي مشاكل التنسيق
    await update.message.reply_text(message)

def main():
    if not TELEGRAM_BOT_TOKEN:
        return

    threading.Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("analyze", analyze_command))

    app.run_polling(poll_interval=3.0, drop_pending_updates=True)

if __name__ == "__main__":
    main()
