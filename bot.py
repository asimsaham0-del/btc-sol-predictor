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

# الاتصال بمنصة التداول باستخدام CCXT لجلب بيانات حقيقية وقوية
exchange = ccxt.binance({
    'enableRateLimit': True,
})

def get_market_data(symbol_input):
    try:
        # تنسيق الرمز بالشكل الصحيح (مثال: BTC/USDT)
        formatted_symbol = symbol_input.upper()
        if "/" not in formatted_symbol:
            if formatted_symbol.endswith("USDT"):
                formatted_symbol = formatted_symbol[:-4] + "/USDT"
            else:
                formatted_symbol = formatted_symbol + "/USDT"

        # جلب آخر شمعة والبيانات الحية
        ticker = exchange.fetch_ticker(formatted_symbol)
        ohlcv = exchange.fetch_ohlcv(formatted_symbol, timeframe='1h', limit=24) # آخر 24 ساعة
        
        closes = [candle[4] for candle in ohlcv]
        highs = [candle[2] for candle in ohlcv]
        lows = [candle[3] for candle in ohlcv]

        data = {
            "symbol": formatted_symbol,
            "price": ticker['last'],
            "high_24h": max(highs),
            "low_24h": min(lows),
            "change_24h": ticker['percentage'],
            "recent_closes": closes[-5:] # آخر 5 أسعار إغلاق للساعة الأخيرة
        }
        return data
    except Exception as e:
        logger.error(f"خطأ في سحب بيانات السوق عبر CCXT: {e}")
        return None

def generate_strong_analysis(data):
    if not GEMINI_API_KEY:
        return "خطأ: مفتاح Gemini غير مضبوط."
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"أنت خبير محترف في التحليل الفني وأسواق العملات الرقمية.\n"
            f"لديك البيانات الحقيقية التالية لعملة {data['symbol']} من منصة التداول:\n"
            f"- السعر الحالي: {data['price']} USDT\n"
            f"- أعلى سعر في 24 ساعة: {data['high_24h']} USDT\n"
            f"- أدنى سعر في 24 ساعة: {data['low_24h']} USDT\n"
            f"- نسبة التغير خلال 24 ساعة: {data['change_24h']}%\n"
            f"- أسعار الإغلاق الأخيرة (آخر 5 ساعات): {data['recent_closes']}\n\n"
            f"قدم تحليلاً فنياً احترافياً وقوياً يشمل:\n"
            f"1. الاتجاه المسيطر (صاعد، هابط، أو جانبي).\n"
            f"2. مستويات الدعم والمقاومة القريبة الحالية.\n"
            f"3. توصية تداول دقيقة واضحة (دخول، هدف واضح، ووقف خسارة صارم)."
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"خطأ في توليد التحليل من Gemini: {e}")
        return "تعذر إتمام التحليل الفني حالياً."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 أهلاً بك في بوت التحليل الفني الاحترافي (مدعوم ببيانات السوق الحقيقية).\n\n"
        "أمر الاستخدام:\n"
        "/analyze BTC\n"
        "/analyze SOL\n"
        "/analyze ETH"
    )

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = "BTC"
    if context.args:
        symbol = context.args[0].upper()

    await update.message.reply_text(f"🔍 جاري الاتصال بمنصات التداول وسحب بيانات {symbol}...")

    market_data = get_market_data(symbol)
    if not market_data:
        await update.message.reply_text("❌ تعذر جلب بيانات العملة. تأكد من كتابة الرمز بشكل صحيح (مثال: BTC, ETH, SOL).")
        return

    analysis = generate_strong_analysis(market_data)

    message = (
        f"📊 **تقرير التحليل الفني المتقدم: {market_data['symbol']}**\n\n"
        f"💵 السعر الفعلي: `${market_data['price']:,.2f}`\n"
        f"📈 التغير (24h): `{market_data['change_24h']:.2f}%`\n"
        f"🔺 أعلى سعر (24h): `${market_data['high_24h']:,.2f}`\n"
        f"🔻 أدنى سعر (24h): `${market_data['low_24h']:,.2f}`\n\n"
        f"--- **رؤية الخبير الذكي** ---\n"
        f"{analysis}"
    )
    await update.message.reply_text(message)

def main():
    if not TELEGRAM_BOT_TOKEN:
        return

    threading.Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("analyze", analyze_command))

    logger.info("البوت يعمل الآن بنظام سحب البيانات الحقيقي عبر CCXT...")
    app.run_polling(poll_interval=3.0, drop_pending_updates=True)

if __name__ == "__main__":
    main()
