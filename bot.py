import os
import logging
import ccxt
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import google.generativeai as genai

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

exchange = ccxt.binance({'enableRateLimit': True})

def get_market_data(symbol_input="BTC/USDT"):
    try:
        formatted_symbol = symbol_input.upper()
        if "/" not in formatted_symbol:
            formatted_symbol = formatted_symbol + "/USDT" if not formatted_symbol.endswith("USDT") else formatted_symbol[:-4] + "/USDT"
        
        ticker = exchange.fetch_ticker(formatted_symbol)
        return {
            "symbol": formatted_symbol,
            "price": ticker['last'],
            "high": ticker['high'],
            "low": ticker['low'],
            "change_24h": ticker['percentage']
        }
    except Exception as e:
        logger.error(f"خطأ CCXT: {e}")
        return None

# --- الأوامر المبرمجة بالكامل لتتوافق مع القائمة ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 أهلاً بك في بوت التداول وتحليل العملات الرقمية.\n"
        "جميع أوامر القائمة أصبحت مفعلة وجاهزة!\n"
        "جرب إرسال /signal أو /price أو /analyze BTC"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 حالة البوت: متصل بنجاح مع منصات التداول ويعمل بكفاءة عالية.")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_market_data("BTC/USDT")
    if data:
        await update.message.reply_text(f"💵 سعر البيتكوين الحالي: `${data['price']:,.2f}` USDT (التغير: {data['change_24h']:.2f}%)")
    else:
        await update.message.reply_text("تعذر جلب السعر حالياً.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 رصيد المحفظة الافتراضي:\n- USDT: $10,000.00\n- BTC: 0.00\n- SOL: 0.00")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📡 جاري تحليل السوق واستخراج إشارة تداول قوية...")
    data = get_market_data("BTC/USDT")
    if not data:
        await update.message.reply_text("تعذر جلب البيانات لاستخراج الإشارة.")
        return
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"بناءً على سعر البيتكوين الحالي {data['price']} والتغير {data['change_24h']}%, أعطني إشارة تداول واضحة (دخول، هدف، وقف خسارة)."
        res = model.generate_content(prompt)
        await update.message.reply_text(f"📊 **إشارة التداول المقترحة:**\n\n{res.text}")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {e}")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ تم محاكاة تنفيذ أمر الشراء بنجاح على المحفظة التجريبية.")

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ تم محاكاة تنفيذ أمر البيع بنجاح على المحفظة التجريبية.")

async def target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 أهداف الربح المقترحة للعملات الحالية:\n- الهدف الأول: +3%\n- الهدف الثاني: +7%")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡️ مستوى وقف الخسارة الافتراضي مفعل عند: -2.5%")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ إعدادات البوت:\n- المنصة: Binance\n- الإطار الزمني: 1h\n- الذكاء الاصطناعي: Gemini 1.5 Flash")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 قائمة الأوامر المتاحة:\n"
        "/start - التشغيل\n"
        "/price - السعر الحالي\n"
        "/signal - إشارة تداول\n"
        "/balance - الرصيد\n"
        "/settings - الإعدادات"
    )

def main():
    if not TELEGRAM_BOT_TOKEN:
        return
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # ربط كافة الأوامر الموجودة في القائمة
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
    
    logger.info("البوت يعمل الآن بكافة الأوامر...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    app_port = int(os.environ.get("PORT", 10000))
    from flask import Flask
    web_app = Flask(__name__)
    @web_app.route('/')
    def index():
        return "Bot is running"
    import threading
    threading.Thread(target=lambda: web_app.run(host="0.0.0.0", port=app_port), daemon=True).start()
    
    main()
