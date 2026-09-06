import os
import logging
import requests
from flask import Flask
from threading import Thread

from dotenv import load_dotenv
from openai import OpenAI

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ============================================================
# إعدادات النظام
# ============================================================

load_dotenv()

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
# إعدادات العملات
# ============================================================

COINS = {
    "BTC": "bitcoin",
    "SOL": "solana",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "TRX": "tron",
    "LINK": "chainlink"
}

# ============================================================
# جلب السعر الحقيقي
# ============================================================

def get_price(symbol):

    symbol = symbol.upper()

    coin_id = COINS.get(symbol)

    if not coin_id:
        return None

    try:

        url = "https://api.coingecko.com/api/v3/simple/price"

        params = {
            "ids": coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true"
        }

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        price = data[coin_id]["usd"]
        change = data[coin_id].get("usd_24h_change", 0)

        return {
            "price": price,
            "change": change
        }

    except Exception as e:

        logger.error(f"خطأ في جلب السعر: {e}")

        return None


# ============================================================
# الذكاء الاصطناعي
# ============================================================

def ask_ai(prompt):

    try:

        response = client.responses.create(

            model="gpt-5.6",

            instructions=(
                "أنت محلل محترف للعملات الرقمية. "
                "تحدث باللغة العربية. "
                "لا تدّعي معرفة المستقبل ولا تضمن الأرباح. "
                "اعتمد فقط على البيانات التي يتم إعطاؤها لك. "
                "قدم التحليل بشكل واضح ومختصر."
            ),

            input=prompt
        )

        return response.output_text

    except Exception as e:

        logger.error(f"OpenAI Error: {e}")

        return "❌ تعذر الاتصال بالذكاء الاصطناعي حالياً."


# ============================================================
# /start
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "🚀 أهلاً بك في بوت التحليل والتوقعات الذكي.\n\n"

        "🤖 يعمل البوت بواسطة الذكاء الاصطناعي.\n"
        "📊 يجلب الأسعار الحالية للعملات.\n"
        "📈 يحلل الاتجاه والدعم والمقاومة.\n"
        "🎯 يعطي منطقة دخول وهدف ووقف خسارة.\n\n"

        "الأوامر الرئيسية:\n\n"

        "/price BTC\n"
        "/analyze BTC\n"
        "/signal\n"
        "/target BTC\n"
        "/stop BTC\n"
        "/balance\n\n"

        "مثال:\n"
        "/analyze SOL"

    )


# ============================================================
# /status
# ============================================================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "🟢 حالة البوت: متصل\n"
        "🤖 الذكاء الاصطناعي: متصل\n"
        "📡 بيانات السوق: متاحة\n"
        "☁️ الخادم: يعمل\n"
        "📊 وضع التداول: تحليل فقط"

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
            f"❌ لم أتمكن من الحصول على سعر {symbol}."
        )

        return

    await update.message.reply_text(

        f"💵 {symbol}\n\n"
        f"السعر الحالي: ${data['price']:,.8f}\n"
        f"تغير 24 ساعة: {data['change']:.2f}%"

    )


# ============================================================
# /balance
# ============================================================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "💰 المحفظة الافتراضية\n\n"
        "USDT: $10.00\n"
        "BTC: 0.00\n"
        "SOL: 0.00\n\n"
        "⚠️ هذه محفظة افتراضية للتجربة فقط."

    )


# ============================================================
# /signal
# ============================================================

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📡 جاري تحليل السوق..."
    )

    btc = get_price("BTC")
    sol = get_price("SOL")

    if not btc or not sol:

        await update.message.reply_text(
            "❌ تعذر الحصول على بيانات السوق."
        )

        return

    prompt = f"""

حلل سوق العملات الرقمية الآن.

BTC:
السعر: ${btc['price']}
تغير 24 ساعة: {btc['change']:.2f}%

SOL:
السعر: ${sol['price']}
تغير 24 ساعة: {sol['change']:.2f}%

أريد:

1. الاتجاه العام.
2. هل السوق يميل للصعود أم الهبوط؟
3. العملة الأفضل للمضاربة بين BTC و SOL.
4. منطقة الدخول المحتملة.
5. الهدف الأول.
6. وقف الخسارة.
7. درجة الثقة من 100.

لا تضمن الربح.

"""

    result = ask_ai(prompt)

    await update.message.reply_text(

        "📊 الإشارة الحالية\n\n"
        + result

    )


# ============================================================
# /analyze
# ============================================================

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):

    symbol = "BTC"

    if context.args:
        symbol = context.args[0].upper()

    if symbol not in COINS:

        await update.message.reply_text(
            "❌ العملة غير مدعومة حالياً."
        )

        return

    await update.message.reply_text(

        f"⏳ جاري تحليل {symbol}..."

    )

    data = get_price(symbol)

    if not data:

        await update.message.reply_text(
            "❌ تعذر الحصول على بيانات العملة."
        )

        return

    prompt = f"""

قم بتحليل العملة {symbol} بناءً على البيانات التالية:

السعر الحالي:
${data['price']}

تغير آخر 24 ساعة:
{data['change']:.2f}%

أريد تقريراً واضحاً يتضمن:

📈 الاتجاه العام

🟢 الدعم

🔴 المقاومة

🎯 منطقة الدخول المحتملة

💰 الهدف الأول

💰 الهدف الثاني

🛑 وقف الخسارة

📊 نسبة الثقة

⚠️ أهم خطر يجب الانتباه له

وفي النهاية أعطني واحدة فقط:

شراء محتمل
أو
انتظار
أو
بيع محتمل

لا تضمن الربح.

"""

    result = ask_ai(prompt)

    await update.message.reply_text(

        f"📊 تقرير التحليل الفني: {symbol}\n\n"
        f"السعر الحالي: ${data['price']:,.8f}\n"
        f"تغير 24 ساعة: {data['change']:.2f}%\n\n"
        f"{result}"

    )


# ============================================================
# /buy
# ============================================================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "🟢 وضع الشراء\n\n"
        "هذا الأمر لا ينفذ صفقة حقيقية.\n"
        "استخدم /analyze BTC أو /analyze SOL\n"
        "لتحديد ما إذا كان الدخول مناسباً."

    )


# ============================================================
# /sell
# ============================================================

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "🔴 وضع البيع\n\n"
        "هذا الأمر لا ينفذ صفقة حقيقية.\n"
        "سيتم استخدام الذكاء الاصطناعي لتحديد ما إذا كان الخروج مناسباً."

    )


# ============================================================
# /target
# ============================================================

async def target(update: Update, context: ContextTypes.DEFAULT_TYPE):

    symbol = "BTC"

    if context.args:
        symbol = context.args[0].upper()

    data = get_price(symbol)

    if not data:

        await update.message.reply_text(
            "❌ تعذر الحصول على السعر."
        )

        return

    prompt = f"""

العملة: {symbol}

السعر الحالي:
${data['price']}

أعطني مستويات أهداف محتملة للمضاربة قصيرة المدى.

اذكر:

🎯 الهدف الأول
🎯 الهدف الثاني
🎯 الهدف الثالث

مع توضيح أن هذه مستويات تقديرية وليست ضماناً.

"""

    result = ask_ai(prompt)

    await update.message.reply_text(

        f"🎯 أهداف {symbol}\n\n"
        + result

    )


# ============================================================
# /stop
# ============================================================

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    symbol = "BTC"

    if context.args:
        symbol = context.args[0].upper()

    data = get_price(symbol)

    if not data:

        await update.message.reply_text(
            "❌ تعذر الحصول على السعر."
        )

        return

    prompt = f"""

العملة: {symbol}

السعر الحالي:
${data['price']}

حدد وقف خسارة منطقي للمضاربة قصيرة المدى.

اذكر:

🛑 مستوى وقف الخسارة
📉 نسبة المسافة من السعر الحالي
⚠️ سبب اختيار المستوى

لا تضمن النتيجة.

"""

    result = ask_ai(prompt)

    await update.message.reply_text(

        f"🛡️ وقف الخسارة المقترح لـ {symbol}\n\n"
        + result

    )


# ============================================================
# /settings
# ============================================================

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "⚙️ إعدادات البوت\n\n"
        "🤖 الذكاء الاصطناعي: OpenAI\n"
        "📡 مصدر الأسعار: CoinGecko\n"
        "📊 الوضع: تحليل وتوقع\n"
        "💰 تنفيذ الصفقات: متوقف\n"
        "🌐 الخادم: Render\n"
        "🗣️ اللغة: العربية"

    )


# ============================================================
# /help
# ============================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "📋 أوامر البوت\n\n"

        "/start - تشغيل البوت\n"
        "/status - حالة النظام\n"
        "/price BTC - السعر الحالي\n"
        "/balance - المحفظة الافتراضية\n"
        "/signal - إشارة السوق\n"
        "/analyze BTC - تحليل BTC\n"
        "/analyze SOL - تحليل SOL\n"
        "/buy - وضع الشراء\n"
        "/sell - وضع البيع\n"
        "/target BTC - الأهداف\n"
        "/stop BTC - وقف الخسارة\n"
        "/settings - الإعدادات\n"
        "/help - المساعدة"

    )


# ============================================================
# تشغيل البوت
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


def main():

    app = ApplicationBuilder().token(
        TELEGRAM_BOT_TOKEN
    ).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("target", target))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("analyze", analyze))

    logger.info("AI Crypto Bot is starting...")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":

    Thread(
        target=run_web_server,
        daemon=True
    ).start()

    main()
