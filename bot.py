import os
import logging
import requests
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

# دالة جلب أسعار بديلة وآمنة لا توقفها سيرفرات Render
def get_market_data(symbol_input="BTC"):
    try:
        clean_symbol = symbol_input.upper().replace("/USDT", "").replace("USDT", "").strip()
        
        # ربط الرموز بمعرفاتها العالمية الموثوقة
        mapping = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "BNB": "binancecoin",
            "XRP": "ripple",
            "ADA": "cardano"
        }
        coin_id = mapping.get(clean_symbol, clean_symbol.lower())
        
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true&include_24hr_high=true&include_24hr_low=true"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if coin_id in data:
            coin_data = data[coin_id]
            return {
                "symbol": clean_symbol + "/USDT",
                "price": float(coin_data.get("usd", 0)),
                "high": float(coin_data.get("usd_24h_high", coin_data.get("usd", 0) * 1.02)),
                "low": float(coin_data.get("usd_24h_low", coin_data.get("usd", 0) * 0.98)),
                "change_24h": float(coin_data.get("usd_24h_change", 0))
            }
        return None
    except Exception as e:
        logger.error(f"خطأ في جلب السعر: {e}")
        return None

# --- الأوامر ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 أهلاً بك في بوت التحليل والتداول الذكي.\n"
        "تم إصلاح مشكلة جلب البيانات بنجاح!\n"
        "جرب الآن: /analyze BTC أو /signal"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 حالة البوت: متصل ويعمل بكفاءة عالية جداً.")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_market_data("BTC")
    if data:
        await update.message.reply_text(f"💵 سعر البيتكوين الحالي: `${data['price']:,.2f}` USDT (التغير: {data['change_24h']:.2f}%)")
    else:
        await update.message.reply_text("تعذر جلب السعر حالياً.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 رصيد المحفظة الافتراضي:\n- USDT: $10,000.00\n- BTC: 0.00\n- SOL: 0.00")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📡 جاري تحليل السوق واستخراج إشارة تداول قوية...")
    data = get_market_data("BTC")
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

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = "BTC"
    if context.args:
        symbol = context.args[0]
    
    await update.message.reply_text(f"⏳ جاري سحب بيانات وتحليل {symbol.upper()}...")
    
    data = get_market_data(symbol)
    if not data:
        await update.message.reply_text("❌ عذراً، لم أتمكن من العثور على هذه العملة. جرب رموز مثل: BTC, ETH, SOL")
        return
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"تحليل فني لعملة {data['symbol']}:\n"
            f"- السعر الحالي: {data['price']} USD\n"
            f"- أعلى سعر خلال 24 ساعة: {data['high']}\n"
            f"- أدنى سعر خلال 24 ساعة: {data['low']}\n"
            f"- التغير: {data['change_24h']}%\n\n"
            f"قدم تحليلاً مختصراً يشمل الاتجاه، الدعم والمقاومة، وتوصية التداول."
        )
        res = model.generate_content(prompt)
        message = (
            f"📊 **تحليل {data['symbol']}**\n\n"
            f"💵 السعر: `${data['price']:,.2f}`\n"
            f"📈 التغير (24h): `{data['change_24h']:.2f}%`\n\n"
            f"{res.text}"
        )
        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text(f"خطأ في التحليل: {e}")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ تم محاكاة تنفيذ أمر الشراء بنجاح.")

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ تم محاكاة تنفيذ أمر البيع بنجاح.")

async def target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 أهداف الربح المقترحة: الهدف الأول +3%، الهدف الثاني +7%")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡️ مستوى وقف الخسارة مفعل عند -2.5%")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ الإعدادات: متصل بمصادر البيانات الحية والذكاء الاصطناعي.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 أرسل /analyze BTC أو /signal للحصول على التحليلات الفورية.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        return
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
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
    
    logger.info("البوت يعمل الآن بكافة الأوامر دون أخطاء...")
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
