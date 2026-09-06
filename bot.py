import os
import logging
import json
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import google.generativeai as genai

# إعداد التسجيل (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تحميل متغيرات البيئة
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# تهيئة Gemini AI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-2.5-flash')
else:
    ai_model = None

DATA_FILE = "user_data.json"

# وظائف إدارة ملف JSON البسيط
def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
            "balance": {"USDT": 1000.0, "BTC": 0.0},
            "orders": [],
            "settings": {"target_profit": 5.0, "stop_loss": 2.0}
        }
        save_data(default_data)
        return default_data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف البيانات: {e}")
        return {"balance": {"USDT": 1000.0, "BTC": 0.0}, "orders": [], "settings": {"target_profit": 5.0, "stop_loss": 2.0}}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"خطأ في حفظ البيانات: {e}")

# جلب أسعار العملات من CoinGecko
def get_crypto_price(symbol="bitcoin"):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        data = response.json()
        if symbol.lower() in data:
            return data[symbol.lower()]["usd"]
        return None
    except Exception as e:
        logger.error(f"خطأ في جلب السعر: {e}")
        return None

# الأوامر الرئيسية
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "مرحبًا بك في بوت تحليل وتتبع العملات الرقمية! 🚀\n\n"
        "هذا البوت يساعدك على متابعة أسعار السوق، الحصول على تحليلات بالذكاء الاصطناعي، "
        "وتسجيل صفقات تجريبية آمنة.\n\n"
        "اكتب /help لعرض قائمة الأوامر المتاحة."
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 **قائمة الأوامر المتاحة:**\n\n"
        "🔹 /start - تشغيل البوت وعرض الترحيب\n"
        "🔹 /help - عرض قائمة الأوامر\n"
        "🔹 /status - حالة البوت وإعداداته\n"
        "🔹 /price <اسم_العملة> - عرض السعر الحالي (مثال: /price bitcoin)\n"
        "🔹 /signal <اسم_العملة> - تحليل السوق بـ AI (مثال: /signal bitcoin)\n"
        "🔹 /balance - عرض الرصيد التجريبي الحالي\n"
        "🔹 /buy <العملة> <الكمية> - تسجيل أمر شراء تجريبي\n"
        "🔹 /sell <العملة> <الكمية> - تسجيل أمر بيع تجريبي\n"
        "🔹 /target <النسبة_المئوية> - تحديد هدف الربح\n"
        "🔹 /stop <النسبة_المئوية> - تحديد وقف الخسارة\n"
        "🔹 /settings - عرض الإعدادات الحالية"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ai_status = "🟢 مفعل" if ai_model else "🔴 غير مفعل (يرجى إضافة GEMINI_API_KEY)"
    status_text = (
        "⚙️ **حالة النظام:**\n\n"
        f"• البوت: 🟢 يعمل بنجاح\n"
        f"• محرك الذكاء الاصطناعي: {ai_status}\n"
        f"• وضع التداول: 🧪 تجريبي (Demo Mode)"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0] if context.args else "bitcoin"
    price = get_crypto_price(symbol)
    if price:
        await update.message.reply_text(f"💰 السعر الحالي لـ **{symbol.capitalize()}** هو: **${price:,.2f}** USDT", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ تعذر جلب السعر لـ '{symbol}'. تأكد من اسم العملة بالإنجليزية (مثل: bitcoin, ethereum, binancecoin).")

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0] if context.args else "bitcoin"
    await update.message.reply_text(f"⏳ جاري تحليل سوق {symbol.capitalize()} بواسطة الذكاء الاصطناعي...")
    
    price = get_crypto_price(symbol)
    if not price:
        await update.message.reply_text("❌ تعذر الحصول على بيانات السعر للتحليل.")
        return

    if not ai_model:
        await update.message.reply_text(
            f"📊 **تحليل أساسي (بدون AI):**\n السعر الحالي لـ {symbol}: ${price:,.2f}\n"
            "💡 لإعادة التحليل المتقدم بالذكاء الاصطناعي، يرجى ضبط `GEMINI_API_KEY`."
        )
        return

    try:
        prompt = (
            f"أنت خبير في تحليل سوق العملات الرقمية. السعر الحالي لعملة {symbol} هو ${price} USDT. "
            f"قم بتقديم تحليل موجز للسوق وأعطِ إشارة تداول واحدة واضحة فقط من بين: (شراء / بيع / انتظار) "
            f"مع ذكر السبب في نقطتين باختصار شديد باللغة العربية."
        )
        response = ai_model.generate_content(prompt)
        await update.message.reply_text(f"🤖 **تحليل الذكاء الاصطناعي لـ {symbol.capitalize()}:**\n\n{response.text}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"خطأ في تحليل AI: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء الاتصال بمحرك الذكاء الاصطناعي.")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    bal = data.get("balance", {})
    msg = "💼 **محفظة التداول التجريبية:**\n\n"
    for coin, amount in bal.items():
        msg += f"• {coin}: {amount:,.4f}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ الاستخدام الصحيح: `/buy <اسم_العملة> <الكمية>`\nمثال: `/buy bitcoin 0.01`", parse_mode="Markdown")
        return

    symbol = context.args[0].lower()
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ الكمية يجب أن تكون رقمًا.")
        return

    price = get_crypto_price(symbol)
    if not price:
      def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("خطأ: لم يتم ضبط TELEGRAM_BOT_TOKEN")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # تسجيل الأوامر
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
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
t:,.2f} USDT",
        parse_mode="Markdown"
    )

async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ الاستخدام الصحيح: `/sell <اسم_العملة> <الكمية>`\nمثال: `/sell bitcoin 0.01`", parse_mode="Markdown")
        return

    symbol = context.args[0].lower()
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ الكمية يجب أن تكون رقمًا.")
        return

    coin_key = symbol.upper()
    data = load_data()

    if data["balance"].get(coin_key, 0) < amount:
        await update.message.reply_text(f"❌ لا تملك كمية كافية من {coin_key} للبيع.")
        return

    price = get_crypto_price(symbol)
    if not price:
        await update.message.reply_text("❌ تعذر معرفة السعر لإتمام الصفقة.")
        return

    total_return = price * amount
    data["balance"][coin_key] -= amount
    data["balance"]["USDT"] = data["balance"].get("USDT", 0.0) + total_return
    data["orders"].append({"type": "SELL", "symbol": symbol, "amount": amount, "price": price})
    save_data(data)

    await update.message.reply_text(
        f"✅ **تم تسجيل أمر بيع تجريبي بنجاح!**\n\n"
        f"• العملة: {symbol.capitalize()}\n"
        f"• الكمية: {amount}\n"
        f"• بسعر: ${price:,.2f}\n"
        f"• الإجمالي المستلم: ${total_return:,.2f} USDT",
        parse_mode="Markdown"
    )

async def target_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ يرجى تحديد النسبة. مثال: `/target 5` (أي 5%)", parse_mode="Markdown")
        return
    try:
        val = float(context.args[0])
        data = load_data()
        data["settings"]["target_profit"] = val
        save_data(data)
        await update.message.reply_text(f"🎯 تم تحديث هدف الربح التجريبي إلى: **{val}%**", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ يرجى تحديد النسبة. مثال: `/stop 2` (أي 2%)", parse_mode="Markdown")
        return
    try:
        val = float(context.args[0])
        data = load_data()
        data["settings"]["stop_loss"] = val
        save_data(data)
        await update.message.reply_text(f"🛑 تم تحديث وقف الخسارة التجريبي إلى: **{val}%**", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح.")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    st = data.get("settings", {})
    msg = (
        "⚙️ **إعدادات التداول الحالية:**\n\n"
        f"• target Profit (هدف الربح): **{st.get('target_profit', 0)}%**\n"
        f"• Stop Loss (وقف الخسارة): **{st.get('stop_loss', 0)}%**\n"
        f"• نمط التداول: **تجريبي فقط def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("خطأ: لم يتم ضبط TELEGRAM_BOT_TOKEN")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # تسجيل الأوامر
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
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
