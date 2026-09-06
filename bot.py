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

# جلب السعر عبر مصدر عالمي موثوق وبدون قيود على خوادم Render
def get_crypto_price(symbol="BTC"):
    try:
        # توحيد الرمز (مثال: تحويل BTCUSDT أو btc إلى كود عملة نظيف)
        clean_symbol = symbol.upper().replace("USDT", "").replace("USD", "")
        
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={get_coingecko_id(clean_symbol)}&vs_currencies=usd&include_24hr_change=true"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        coin_id = get_coingecko_id(clean_symbol)
        if coin_id in data:
            price = float(data[coin_id]["usd"])
            change = float(data[coin_id].get("usd_24h_change", 0.0))
            return {
                "symbol": clean_symbol + "USDT",
                "price": price,
                "change": change
            }
        return None
    except Exception as e:
        logger.error(f"خطأ في جلب السعر: {e}")
        return None

def get_coingecko_id(symbol):
    mapping = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binancecoin",
        "XRP": "ripple",
        "ADA": "cardano"
    }
    return mapping.get(symbol, symbol.lower())

def generate_analysis(data):
    if not GEMINI_API_KEY:
        return "خطأ: مفتاح Gemini غير مضبوط."
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"تحليل فني سريع لعملة {data['symbol']}:\n"
            f"- السعر الحالي: {data['price']} USD\n"
            f"- التغير خلال 24 ساعة: {data['change']:.2f}%\n\n"
            f"أعطني تحليلاً مختصراً جداً يوضح الاتجاه الحالي، مناطق الدعم، ونصيحة التداول."
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"خطأ Gemini: {e}")
        return "تعذر إكمال التحليل الفني."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك! البوت يعمل الآن بكفاءة عالية.\nجرب إرسال:\n/analyze BTC\nأو\n/analyze SOL"
    )

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = "BTC"
    if context.args:
        symbol = context.args[0].upper()

    await update.message.reply_text(f"⏳ جاري جلب السعر وتحليل {symbol}...")
    
    market_data = get_crypto_price(symbol)
    if not market_data:
        await update.message.reply_text("عذراً، لم أتمكن من العثور على هذه العملة. جرب رموز مثل: BTC, ETH, SOL")
        return

    analysis_result = generate_analysis(market_data)
    
    message = (
        f"📊 تحليل {market_data['symbol']}\n\n"
        f"💵 السعر: ${market_data['price']:,.2f}\n"
        f"📈 التغير (24h): {market_data['change']:.2f}%\n\n"
        f"--- رأي الذكاء الاصطناعي ---\n"
        f"{analysis_result}"
    )
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
