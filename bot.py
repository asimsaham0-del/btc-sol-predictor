import os
import time
import logging
import threading
from typing import Optional

import requests
from flask import Flask
from openai import OpenAI

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)


# =========================================================
# SETTINGS
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN غير موجود في Render")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY غير موجود في Render")


client = OpenAI(api_key=OPENAI_API_KEY)

BINANCE_BASE = "https://api.binance.com"

# العملات المدعومة
COINS = {
    "BTC": "BTCUSDT",
    "SOL": "SOLUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "XRP": "XRPUSDT",
    "DOGE": "DOGEUSDT",
    "ADA": "ADAUSDT",
    "AVAX": "AVAXUSDT",
    "TRX": "TRXUSDT",
    "LINK": "LINKUSDT",
}


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# =========================================================
# CACHE / PROTECTION
# =========================================================

cache = {}
cache_lock = threading.Lock()

# أقل مدة بين طلبات Binance
MIN_REQUEST_INTERVAL = 2.0

last_binance_request = 0.0

# إذا حصل 429 نوقف الطلبات مؤقتاً
binance_cooldown_until = 0.0


def wait_before_request():
    global last_binance_request

    with cache_lock:
        now = time.time()

        wait = MIN_REQUEST_INTERVAL - (now - last_binance_request)

        if wait > 0:
            time.sleep(wait)

        last_binance_request = time.time()


def cache_get(key):
    with cache_lock:
        item = cache.get(key)

        if not item:
            return None

        value, expires = item

        if time.time() < expires:
            return value

        del cache[key]

        return None


def cache_set(key, value, ttl):
    with cache_lock:
        cache[key] = (
            value,
            time.time() + ttl
        )


# =========================================================
# BINANCE REQUEST
# =========================================================

def binance_get(endpoint, params=None, cache_key=None, cache_ttl=15):

    global binance_cooldown_until

    # أولاً نحاول من الـ Cache
    if cache_key:
        cached = cache_get(cache_key)

        if cached is not None:
            return cached

    # إذا Binance وضعنا في فترة توقف
    if time.time() < binance_cooldown_until:
        logger.warning("Binance cooldown active")
        return None

    try:

        wait_before_request()

        url = BINANCE_BASE + endpoint

        response = requests.get(
            url,
            params=params,
            timeout=10,
            headers={
                "User-Agent": "CryptoAnalysisBot/1.0"
            }
        )

        # Rate limit
        if response.status_code == 429:

            logger.error(
                "Binance 429 RATE LIMIT - stopping requests temporarily"
            )

            # توقف 2 دقائق
            binance_cooldown_until = time.time() + 120

            return None

        # Forbidden
        if response.status_code in (418, 403):

            logger.error(
                f"Binance access error: HTTP {response.status_code}"
            )

            # لا نعيد الطلب بسرعة
            binance_cooldown_until = time.time() + 300

            return None

        response.raise_for_status()

        data = response.json()

        if cache_key:
            cache_set(
                cache_key,
                data,
                cache_ttl
            )

        return data

    except requests.exceptions.RequestException as e:

        logger.error(
            f"BINANCE REQUEST ERROR: {type(e).__name__}: {e}"
        )

        return None

    except Exception as e:

        logger.error(
            f"BINANCE UNKNOWN ERROR: {type(e).__name__}: {e}"
        )

        return None


# =========================================================
# PRICE
# =========================================================

def get_price(symbol):

    pair = COINS.get(symbol.upper())

    if not pair:
        return None

    data = binance_get(
        "/api/v3/ticker/price",
        params={
            "symbol": pair
        },
        cache_key=f"price_{pair}",
        cache_ttl=15
    )

    if not data:
        return None

    try:
        return float(data["price"])

    except Exception:
        return None


# =========================================================
# 24H DATA
# =========================================================

def get_24h(symbol):

    pair = COINS.get(symbol.upper())

    if not pair:
        return None

    data = binance_get(
        "/api/v3/ticker/24hr",
        params={
            "symbol": pair
        },
        cache_key=f"24h_{pair}",
        cache_ttl=30
    )

    if not data:
        return None

    try:

        return {
            "price": float(data["lastPrice"]),
            "change": float(data["priceChangePercent"]),
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
            "volume": float(data["volume"]),
        }

    except Exception as e:

        logger.error(
            f"24H PARSE ERROR [{symbol}]: {e}"
        )

        return None


# =========================================================
# KLINES
# =========================================================

def get_klines(symbol, interval, limit=100):

    pair = COINS.get(symbol.upper())

    if not pair:
        return None

    data = binance_get(
        "/api/v3/klines",
        params={
            "symbol": pair,
            "interval": interval,
            "limit": limit
        },
        cache_key=f"klines_{pair}_{interval}_{limit}",
        cache_ttl=60
    )

    if not data:
        return None

    try:

        candles = []

        for c in data:

            candles.append({
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })

        return candles

    except Exception as e:

        logger.error(
            f"KLINES PARSE ERROR [{symbol} {interval}]: {e}"
        )

        return None


# =========================================================
# RSI
# =========================================================

def calculate_rsi(closes, period=14):

    if len(closes) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, len(closes)):

        difference = closes[i] - closes[i - 1]

        if difference >= 0:
            gains.append(difference)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(difference))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):

        avg_gain = (
            (avg_gain * (period - 1))
            + gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1))
            + losses[i]
        ) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# =========================================================
# MARKET ANALYSIS DATA
# =========================================================

def analyze_market(symbol):

    result = {
        "symbol": symbol,
        "price": None,
        "change_24h": None,
        "high_24h": None,
        "low_24h": None,
        "volume": None,
        "timeframes": {}
    }

    data_24h = get_24h(symbol)

    if data_24h:

        result["price"] = data_24h["price"]
        result["change_24h"] = data_24h["change"]
        result["high_24h"] = data_24h["high"]
        result["low_24h"] = data_24h["low"]
        result["volume"] = data_24h["volume"]

    # الفواصل الزمنية
    for interval in ["1h", "4h", "1d"]:

        candles = get_klines(
            symbol,
            interval,
            100
        )

        if not candles:
            continue

        closes = [
            c["close"]
            for c in candles
        ]

        highs = [
            c["high"]
            for c in candles
        ]

        lows = [
            c["low"]
            for c in candles
        ]

        volumes = [
            c["volume"]
            for c in candles
        ]

        rsi = calculate_rsi(closes)

        support = min(lows[-30:])
        resistance = max(highs[-30:])

        avg_volume = sum(volumes[-20:]) / 20

        current_volume = volumes[-1]

        volume_ratio = (
            current_volume / avg_volume
            if avg_volume > 0
            else 1
        )

        # الاتجاه البسيط
        old_price = closes[-20]
        current_price = closes[-1]

        if current_price > old_price:
            trend = "صاعد"
        elif current_price < old_price:
            trend = "هابط"
        else:
            trend = "جانبي"

        result["timeframes"][interval] = {
            "price": current_price,
            "rsi": round(rsi, 2) if rsi is not None else None,
            "support": support,
            "resistance": resistance,
            "trend": trend,
            "volume_ratio": round(volume_ratio, 2)
        }

    return result


# =========================================================
# FORMAT MARKET DATA
# =========================================================

def market_text(data):

    if not data:
        return "لا توجد بيانات."

    text = []

    symbol = data["symbol"]

    text.append(f"العملة: {symbol}")

    if data["price"] is not None:
        text.append(
            f"السعر الحالي: {data['price']}"
        )

    if data["change_24h"] is not None:
        text.append(
            f"تغير 24 ساعة: {data['change_24h']:.2f}%"
        )

    for tf, info in data["timeframes"].items():

        text.append(
            f"\n{tf}:"
        )

        text.append(
            f"الاتجاه: {info['trend']}"
        )

        if info["rsi"] is not None:
            text.append(
                f"RSI: {info['rsi']}"
            )

        text.append(
            f"الدعم: {info['support']}"
        )

        text.append(
            f"المقاومة: {info['resistance']}"
        )

        text.append(
            f"حجم التداول مقارنة بالمتوسط: "
            f"{info['volume_ratio']}x"
        )

    return "\n".join(text)


# =========================================================
# OPENAI ANALYSIS
# =========================================================

def ai_analysis(symbol, data):

    raw_data = market_text(data)

    prompt = f"""
أنت محلل للعملات الرقمية.

حلل {symbol} اعتماداً فقط على البيانات التالية:

{raw_data}

أريد تحليلاً واضحاً وقصيراً باللغة العربية.

رتب النتيجة بهذا الشكل:

📊 {symbol}

💰 السعر الحالي:
...

📈 الاتجاه:
صاعد / هابط / جانبي

🎯 السيناريو المتوقع:
...

🟢 منطقة دخول محتملة:
...

🎯 الهدف الأول:
...

🎯 الهدف الثاني:
...

🛑 وقف الخسارة / نقطة إبطال التحليل:
...

📊 RSI:
...

🧱 الدعم:
...

🚧 المقاومة:
...

🔥 قوة الإشارة:
من 100

⚠️ المخاطر:
...

ثم أعطني القرار النهائي:
شراء محتمل / انتظار / بيع محتمل

مهم جداً:
- لا تضمن الربح.
- لا تدّعي معرفة المستقبل.
- إذا كانت البيانات غير واضحة، قل "انتظار".
- لا تنفذ أي صفقة.
"""

    try:

        response = client.responses.create(
            model="gpt-5",
            instructions=(
                "أنت محلل مالي للبيانات الرقمية. "
                "لا تنفذ صفقات ولا تقدم ضمانات ربح."
            ),
            input=prompt
        )

        return response.output_text

    except Exception as e:

        logger.error(
            f"OPENAI ERROR: {type(e).__name__}: {e}"
        )

        return (
            "❌ حدث خطأ أثناء تحليل الذكاء الاصطناعي."
        )


# =========================================================
# TELEGRAM COMMANDS
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
🤖 أهلاً بك في بوت تحليل العملات

الأوامر:

/price BTC
/price SOL

/analyze BTC
/analyze SOL

/signal

/help

⚠️ البوت للتحليل والتوقع فقط.
لا يقوم بتنفيذ عمليات شراء أو بيع.
"""

    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
📌 أوامر البوت:

💰 السعر:
/price BTC
/price SOL

📊 التحليل:
/analyze BTC
/analyze SOL

🔥 مقارنة BTC و SOL:
/signal

يمكنك أيضاً استخدام:
ETH
BNB
XRP
DOGE
ADA
AVAX
TRX
LINK
"""

    await update.message.reply_text(text)


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "اكتب العملة مثلاً:\n/price BTC"
        )

        return

    symbol = context.args[0].upper()

    if symbol not in COINS:

        await update.message.reply_text(
            "❌ هذه العملة غير مدعومة."
        )

        return

    price = get_price(symbol)

    if price is None:

        await update.message.reply_text(
            "⚠️ تعذر جلب السعر حالياً.\n"
            "تم إيقاف الطلبات مؤقتاً إذا كان هناك ضغط على المصدر."
        )

        return

    await update.message.reply_text(
        f"💰 {symbol}\n\n"
        f"السعر الحالي:\n"
        f"{price:,.8f}"
    )


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "اكتب العملة مثلاً:\n/analyze BTC"
        )

        return

    symbol = context.args[0].upper()

    if symbol not in COINS:

        await update.message.reply_text(
            "❌ العملة غير مدعومة."
        )

        return

    await update.message.reply_text(
        f"🔎 جاري تحليل {symbol}...\n"
        f"انتظر قليلاً."
    )

    data = analyze_market(symbol)

    if not data["timeframes"]:

        await update.message.reply_text(
            "❌ لم أستطع الحصول على بيانات السوق حالياً."
        )

        return

    result = ai_analysis(
        symbol,
        data
    )

    await update.message.reply_text(
        result
    )


async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🔎 جاري مقارنة BTC و SOL..."
    )

    btc = analyze_market("BTC")

    sol = analyze_market("SOL")

    if not btc["timeframes"] or not sol["timeframes"]:

        await update.message.reply_text(
            "❌ تعذر الحصول على بيانات المقارنة حالياً."
        )

        return

    btc_text = market_text(btc)
    sol_text = market_text(sol)

    prompt = f"""
قارن بين BTC و SOL بناءً على البيانات التالية:

BTC:
{btc_text}

SOL:
{sol_text}

أعطني نتيجة مختصرة بالعربية:

🥇 الأقوى حالياً:
...

📈 الاتجاه:
...

🎯 الأفضل للمضاربة القصيرة:
...

🛑 مستوى الخطر:
...

🔥 قوة الإشارة من 100:
...

ثم:
شراء محتمل / انتظار

لا تضمن الربح ولا تنفذ أي صفقة.
"""

    try:

        response = client.responses.create(
            model="gpt-5",
            instructions=(
                "حلل السوق بحذر ولا تضمن النتائج."
            ),
            input=prompt
        )

        await update.message.reply_text(
            response.output_text
        )

    except Exception as e:

        logger.error(
            f"SIGNAL OPENAI ERROR: "
            f"{type(e).__name__}: {e}"
        )

        await update.message.reply_text(
            "❌ حدث خطأ أثناء إنشاء المقارنة."
        )


# =========================================================
# BUY / SELL
# =========================================================

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "ℹ️ هذا البوت لا ينفذ عمليات شراء حقيقية.\n"
        "وظيفته تحليل السوق وإعطاء سيناريو محتمل فقط."
    )


async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "ℹ️ هذا البوت لا ينفذ عمليات بيع حقيقية.\n"
        "وظيفته تحليل السوق وإعطاء سيناريو محتمل فقط."
    )


# =========================================================
# RENDER WEB SERVER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():

    return "Crypto AI Bot is running."


@app.route("/health")
def health():

    return {
        "status": "ok",
        "bot": "running"
    }


def run_web():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================================================
# MAIN
# =========================================================

def main():

    logger.info(
        "Starting Crypto AI Telegram Bot..."
    )

    web_thread = threading.Thread(
        target=run_web,
        daemon=True
    )

    web_thread.start()

    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "price",
            price_command
        )
    )

    application.add_handler(
        CommandHandler(
            "analyze",
            analyze_command
        )
    )

    application.add_handler(
        CommandHandler(
            "signal",
            signal_command
        )
    )

    application.add_handler(
        CommandHandler(
            "buy",
            buy_command
        )
    )

    application.add_handler(
        CommandHandler(
            "sell",
            sell_command
        )
    )

    logger.info(
        "Telegram bot is running."
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
