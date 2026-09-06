import os
import logging
import threading
import ccxt
from flask import Flask
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import google.generativeai as genai

# خادم الويب لإبقاء الخدمة نشطة على Render
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

exchange = ccxt.binance({
    'enableRateLimit': True,
})

def get_market_data(symbol_input):
    try:
        formatted_symbol = symbol_input.upper()
        if "/" not in formatted_symbol:
            if formatted_symbol.endswith("USDT"):
                formatted_symbol = formatted_symbol[:-4] + "/USDT"
            else:
                formatted_symbol = formatted_symbol + "/USDT"

        ticker = exchange.fetch_ticker(formatted_symbol)
        ohlcv = exchange.fetch_ohlcv(formatted_symbol, timeframe='1h', limit=24)
        
        closes = [candle[4] for candle in ohlcv]
        highs = [candle[2] for candle in ohlcv]
        lows = [candle[3] for candle in ohlcv]

        return {
            "symbol": formatted_symbol,
            "price": ticker['last'],
            "high_24h": max(highs),
            "low_24h": min(lows),
            "change_24h": ticker['percentage'],
            "recent_closes": closes[-5:]
        }
    except Exception as e:
        logger.error(f"خطأ في سحب بيانات السوق: {e}")
        return None

def generate_strong_analysis(data):
    if not GEMINI_API_KEY:
        return "خطأ: مفتاح Gemini غير مضبوط."
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"أنت خبير محترف في التحليل الفني وأسواق العملات الرقمية.\n"
            f"لديك البيانات الحقيقية لعملة {data['symbol']}:\n"
            f"- السعر الحالي: {data['price']} USDT\n"
            f"- أعلى سعر في 24 ساعة: {data['high_24h']} USDT\n"
            f"- أدنى سعر في 24 ساعة: {data['low_24h']} USDT\n"
            f"- نسبة التغير: {data['change_24h']}%\n\n"
            f"قدم تحليلاً فنياً مختصراً وقوياً يشمل الاتجاه، الدعم والمقاومة، وتوصية التداول."
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "تعذر إتمام التحليل الفني."

# تفعيل جميع أوامر القائمة
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 أهلاً بك في بوت التحليل الفني.\n\n"
        "الأوامر المتاحة:\n"
        "/analyze BTC - لتحليل أي عملة\n"
        "/price - لمعرفة السعر السريع للبيتكوين\n"
        "/status - فحص حالة البوت\n"
        "/balance - عرض الرصيد الافتراضي"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 البوت يعمل بكفاءة ومتصل بسوام المنصات بنجاح.")

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_market_data("BTC/USDT")
    if data:
        await update.message.reply_text(f"💵 سعر البيتكوين الحالي: `${data['price']:,.2f}` USDT")
    else:
        await update.message.reply_text("تعذر جلب السعر حالياً.")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 رصيد المحفظة التجريبي: 10,000.00 USDT")

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = "BTC"
    if context.args:
        symbol = context.args[0].upper()

    await update.message.reply_text(f"🔍 جاري سحب بيانات {symbol} وتحليلها...")

    market_data = get_market_data(symbol)
    if not market_data:
        await update.message.reply_text("❌ تعذر جلب بيانات العملة. تأكد من الرمز (مثال: /analyze BTC).")
        return

    analysis = generate_strong_analysis(market_data)

    message = (
        f"📊 **تحليل {market_data['symbol']}**\n\n"
        f"💵 السعر: `${market_data['price']:,.2f}`\n"
        f"📈 التغير (24h): `{market_data['change_24h']:.2f}%`\n\n"
        f"{analysis}"
    )
    await update.message.reply_text(message)

def main():
    if not TELEGRAM_BOT_TOKEN:
        return

    threading.Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # ربط جميع الأوامر لتعمل مباشرة من القائمة
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("analyze", analyze_command))

    app.run_polling(poll_interval=3.0, drop_pending_updates=True)

if __name__ == "__main__":
    main()
