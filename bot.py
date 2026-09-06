import os
import logging
import requests
from flask import Flask
from threading import Thread
from openai import OpenAI

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN غير موجود")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY غير موجود")


client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# العملات المدعومة
# ============================================================

SUPPORTED_COINS = {
    "BTC": "BTCUSDT",
    "SOL": "SOLUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "XRP": "XRPUSDT",
    "DOGE": "DOGEUSDT",
    "ADA": "ADAUSDT",
    "AVAX": "AVAXUSDT",
    "TRX": "TRXUSDT",
    "LINK": "LINKUSDT"
}


# ============================================================
# جلب السعر من Binance
# ============================================================

def get_price(symbol):

    symbol = symbol.upper()

    pair = SUPPORTED_COINS.get(symbol)

    if not pair:
        return None

    try:

        url = "https://api.binance.com/api/v3/ticker/24hr"

        response = requests.get(
            url,
            params={"symbol": pair},
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        return {
            "symbol": symbol,
            "price": float(data["lastPrice"]),
            "change": float(data["priceChangePercent"]),
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
            "volume": float(data["volume"])
        }

    except Exception as e:

        logger.error(f"خطأ في جلب السعر: {e}")

        return None


# ============================================================
# جلب الشموع
# ============================================================

def get_klines(symbol, interval="1h", limit=100):

    symbol = symbol.upper()

    pair = SUPPORTED_COINS.get(symbol)

    if not pair:
        return None

    try:

        url = "https://api.binance.com/api/v3/klines"

        response = requests.get(
            url,
            params={
                "symbol": pair,
                "interval": interval,
                "limit": limit
            },
            timeout=15
        )

        response.raise_for_status()

        return response.json()

    except Exception as e:

        logger.error(f"خطأ في جلب الشموع: {e}")

        return None


# ============================================================
# حساب RSI
# ============================================================

def calculate_rsi(closes, period=14):

    if len(closes) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, len(closes)):

        change = closes[i] - closes[i - 1]

        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):

        avg_gain = (
            (avg_gain * (period - 1)) + gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1)) + losses[i]
        ) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ============================================================
# تحليل بيانات السوق
# ============================================================

def market_data(symbol):

    price_data = get_price(symbol)

    if not price_data:
        return None

    kline_1h = get_klines(symbol, "1h", 100)
    kline_4h = get_klines(symbol, "4h", 100)
    kline_1d = get_klines(symbol, "1d", 100)

    if not kline_1h or not kline_4h or not kline_1d:
        return None

    closes_1h = [float(x[4]) for x in kline_1h]
    closes_4h = [float(x[4]) for x in kline_4h]
    closes_1d = [float(x[4]) for x in kline_1d]

    volumes_1h = [float(x[5]) for x in kline_1h]

    rsi_1h = calculate_rsi(closes_1h)
    rsi_4h = calculate_rsi(closes_4h)
    rsi_1d = calculate_rsi(closes_1d)

    support_1h = min(closes_1h[-20:])
    resistance_1h = max(closes_1h[-20:])

    support_4h = min(closes_4h[-20:])
    resistance_4h = max(closes_4h[-20:])

    average_volume = sum(volumes_1h[-20:]) / 20
    current_volume = volumes_1h[-1]

    return {
        "symbol": symbol,
        "price": price_data["price"],
        "change": price_data["change"],
        "high": price_data["high"],
        "low": price_data["low"],
        "volume": price_data["volume"],
        "rsi_1h": rsi_1h,
        "rsi_4h": rsi_4h,
        "rsi_1d": rsi_1d,
        "support_1h": support_1h,
        "resistance_1h": resistance_1h,
        "support_4h": support_4h,
        "resistance_4h": resistance_4h,
        "average_volume": average_volume,
        "current_volume": current_volume
    }


# ============================================================
# OpenAI
# ============================================================

def ask_ai(prompt):

    try:

        response = client.responses.create(

            model="gpt-5",

            instructions=(
                "أنت محلل فني للعملات الرقمية. "
                "حلل البيانات المعطاة فقط. "
                "لا تدّعي ضمان الربح. "
                "لا تخترع أسعاراً أو بيانات غير موجودة. "
                "أجب باللغة العربية وبطريقة واضحة ومباشرة."
            ),

            input=prompt
        )

        return response.output_text

    except Exception as e:

        logger.error(f"OpenAI Error: {e}")

        return "❌ حدث خطأ أثناء الاتصال بالذكاء الاصطناعي."


# ============================================================
# /start
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "🚀 أهلاً بك في بوت التحليل والتداول الذكي.\n\n"

        "📊 بيانات السوق: Binance\n"
        "🤖 الذكاء الاصطناعي: OpenAI\n"
        "📈 تحليل فني: RSI + دعم + مقاومة + حجم\n\n"

        "الأوامر:\n\n"

        "/price BTC\n"
        "/analyze BTC\n"
        "/signal\n"
        "/balance\n"
        "/target BTC\n"
        "/stop BTC\n"
        "/buy BTC\n"
        "/sell BTC\n"
        "/status\n"
        "/settings\n"
        "/help"

    )


# ============================================================
# /status
# ============================================================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "🟢 حالة البوت\n\n"
        "Telegram: متصل\n"
        "OpenAI: مفعّل\n"
        "Binance Market Data: مفعّل\n"
        "وضع التداول: تحليل فقط\n"
        "تنفيذ الصفقات الحقيقية: متوقف"

    )


# ============================================================
# /price
# ============================================================

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):

    symbol = "BTC"

    if context.args:
        symbol = context.args[0].upper()

    data = get_price(symbol)

    if not data:

        await update.message.reply_text(
            f"❌ تعذر جلب سعر {symbol} من Binance."
        )

        return

    await update.message.reply_text(

        f"💵 {symbol}/USDT\n\n"
        f"السعر: ${data['price']:,.8f}\n"
        f"تغير 24 ساعة: {data['change']:.2f}%\n"
        f"أعلى سعر: ${data['high']:,.8f}\n"
        f"أدنى سعر: ${data['low']:,.8f}"

    )


# ============================================================
# /balance
# ============================================================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "💰 المحفظة الافتراضية\n\n"
        "USDT: $10.00\n"
        "BTC: 0\n"
        "SOL: 0\n\n"
        "⚠️ هذه محفظة تجريبية فقط."

    )


# ============================================================
# /analyze
# ============================================================

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):

    symbol = "BTC"

    if context.args:
        symbol = context.args[0].upper()

    if symbol not in SUPPORTED_COINS:

        await update.message.reply_text(
            "❌ العملة غير مدعومة."
        )

        return

    await update.message.reply_text(
        f"⏳ جاري تحليل {symbol} على 1H و4H و1D..."
    )

    data = market_data(symbol)

    if not data:

        await update.message.reply_text(
            "❌ تعذر الحصول على بيانات السوق."
        )

        return

    prompt = f"""

حلل العملة {symbol} تحليلاً فنياً.

بيانات السوق الحالية:

السعر:
${data['price']}

تغير 24 ساعة:
{data['change']:.2f}%

أعلى 24 ساعة:
${data['high']}

أدنى 24 ساعة:
${data['low']}

RSI - ساعة:
{data['rsi_1h']:.2f}

RSI - 4 ساعات:
{data['rsi_4h']:.2f}

RSI - يوم:
{data['rsi_1d']:.2f}

دعم 1H:
${data['support_1h']}

مقاومة 1H:
${data['resistance_1h']}

دعم 4H:
${data['support_4h']}

مقاومة 4H:
${data['resistance_4h']}

حجم التداول الحالي:
{data['current_volume']}

متوسط حجم التداول:
{data['average_volume']}

أريد منك:

1. الاتجاه العام.
2. حالة RSI.
3. أهم الدعم.
4. أهم المقاومة.
5. هل الدخول الآن مناسب أم الانتظار؟
6. منطقة دخول محتملة.
7. الهدف الأول.
8. الهدف الثاني.
9. وقف الخسارة.
10. نسبة المخاطرة.
11. درجة قوة الإشارة من 100.

وفي النهاية اكتب بوضوح:

🟢 دخول محتمل
أو
🟡 انتظار
أو
🔴 خروج/تجنب

لا تضمن الربح.

"""

    result = ask_ai(prompt)

    await update.message.reply_text(

        f"📊 التحليل الفني: {symbol}\n\n"
        f"السعر الحالي: ${data['price']:,.8f}\n\n"
        f"{result}"

    )


# ============================================================
# /signal
# ============================================================

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📡 أقوم بمقارنة BTC و SOL..."
    )

    btc = market_data("BTC")
    sol = market_data("SOL")

    if not btc or not sol:

        await update.message.reply_text(
            "❌ تعذر الحصول على بيانات السوق."
        )

        return

    prompt = f"""

قارن بين BTC و SOL للمضاربة قصيرة المدى.

BTC:

السعر:
${btc['price']}

تغير 24 ساعة:
{btc['change']:.2f}%

RSI 1H:
{btc['rsi_1h']:.2f}

RSI 4H:
{btc['rsi_4h']:.2f}

RSI 1D:
{btc['rsi_1d']:.2f}

الدعم:
${btc['support_1h']}

المقاومة:
${btc['resistance_1h']}


SOL:

السعر:
${sol['price']}

تغير 24 ساعة:
{sol['change']:.2f}%

RSI 1H:
{sol['rsi_1h']:.2f}

RSI 4H:
{sol['rsi_4h']:.2f}

RSI 1D:
{sol['rsi_1d']:.2f}

الدعم:
${sol['support_1h']}

المقاومة:
${sol['resistance_1h']}

حدد:

1. أيهما أقوى حالياً؟
2. أيهما أفضل للمضاربة؟
3. منطقة الدخول.
4. الهدف.
5. وقف الخسارة.
6. درجة قوة الإشارة.

إذا كانت الظروف غير مناسبة قل "انتظار".

"""

    result = ask_ai(prompt)

    await update.message.reply_text(
        "📊 إشارة السوق\n\n" + result
    )


# ============================================================
# /buy
# ============================================================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):

    symbol = "BTC"

    if context.args:
        symbol = context.args[0].upper()

    await update.message.reply_text(

        f"🟢 طلب شراء {symbol}\n\n"
        "⚠️ هذا الأمر لا ينفذ شراءً حقيقياً.\n"
        "للحصول على قرار الدخول استخدم:\n\n"
        f"/analyze {symbol}"

    )


# ============================================================
# /sell
# ============================================================

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):

    symbol = "BTC"

    if context.args:
        symbol = context.args[0].upper()

    await update.message.reply_text(

        f"🔴 طلب بيع {symbol}\n\n"
        "⚠️ هذا الأمر لا ينفذ بيعاً حقيقياً.\n"
        "للحصول على تحليل الخروج استخدم:\n\n"
        f"/analyze {symbol}"

    )


# ============================================================
# /target
# ============================================================

async def target(update: Update, context: ContextTypes.DEFAULT_TYPE):

    symbol = "BTC"

    if context.args:
        symbol = context.args[0].upper()

    data = market_data(symbol)

    if not data:

        await update.message.reply_text(
            "❌ تعذر الحصول على بيانات السوق."
        )

        return

    prompt = f"""

العملة: {symbol}

السعر الحالي:
${data['price']}

المقاومة 1H:
${data['resistance_1h']}

المقاومة 4H:
${data['resistance_4h']}

حدد هدفين محتملين للمضاربة قصيرة المدى.

اذكر السعر ونسبة الارتفاع التقريبية.

لا تضمن الربح.

"""

    result = ask_ai(prompt)

    await update.message.reply_text(
        f"🎯 أهداف {symbol}\n\n{result}"
    )


# ============================================================
# /stop
# ============================================================

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    symbol = "BTC"

    if context.args:
        symbol = context.args[0].upper()

    data = market_data(symbol)

    if not data:

        await update.message.reply_text(
            "❌ تعذر الحصول على بيانات السوق."
        )

        return

    prompt = f"""

العملة: {symbol}

السعر الحالي:
${data['price']}

الدعم 1H:
${data['support_1h']}

الدعم 4H:
${data['support_4h']}

حدد وقف خسارة منطقي للمضاربة.

اذكر المستوى وسبب اختياره.

لا تضمن النتيجة.

"""

    result = ask_ai(prompt)

    await update.message.reply_text(
        f"🛡️ وقف الخسارة: {symbol}\n\n{result}"
    )


# ============================================================
# /settings
# ============================================================

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "⚙️ إعدادات البوت\n\n"
        "🤖 AI: OpenAI\n"
        "📡 Market Data: Binance\n"
        "📊 Timeframes: 1H / 4H / 1D\n"
        "📈 RSI: مفعّل\n"
        "📊 Volume: مفعّل\n"
        "🛡️ Stop Loss: تحليل آلي\n"
        "💰 تنفيذ الصفقات: متوقف"

    )


# ============================================================
# /help
# ============================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "📋 أوامر البوت\n\n"

        "/start\n"
        "/status\n"
        "/price BTC\n"
        "/balance\n"
        "/signal\n"
        "/analyze BTC\n"
        "/analyze SOL\n"
        "/buy BTC\n"
        "/sell BTC\n"
        "/target BTC\n"
        "/stop BTC\n"
        "/settings\n"
        "/help"

    )


# ============================================================
# Web Server - Render
# ============================================================

def run_web_server():

    port = int(os.environ.get("PORT", 10000))

    web_app = Flask(__name__)

    @web_app.route("/")
    def index():
        return "AI Crypto Bot is running."

    web_app.run(
        host="0.0.0.0",
        port=port
    )


# ============================================================
# Main
# ============================================================

def main():

    app = ApplicationBuilder().token(
        TELEGRAM_BOT_TOKEN
    ).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("target", target))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("help", help_command))

    logger.info("AI Crypto Bot started successfully.")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":

    Thread(
        target=run_web_server,
        daemon=True
    ).start()

    main()
