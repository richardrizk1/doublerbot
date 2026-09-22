import os, json, re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from flask import Flask
import threading

# تحميل الداتا
try:
    with open("data.json", "r", encoding="utf-8") as f:
        DB = json.load(f)
except:
    DB = []

def clean(t):
    return re.sub(r'[^A-Z0-9]', '', str(t).upper())

def format_car(r):
    tel = str(r.get('TelProp',''))
    plate = str(r.get('ActualNB','') or r.get('ActualNo','')).strip()
    code = str(r.get('CodeDesc','')).strip()
    model = str(r.get('ModelDesc','') or r.get('MakeDesc','')).strip()
    color = str(r.get('ColorDesc','')).strip()
    year = str(r.get('YearProd','')).strip()
    return f"🚗 {plate}/{code}\n📞 {tel}\n🚙 {model} {color} {year}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send plate number or phone number")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    num = re.sub(r'[^0-9A-Z/]', '', raw.upper())
    code = ""
    if "/" in raw:
        parts = raw.upper().split("/")
        if len(parts) > 1:
            code = clean(parts[1])
            num = re.sub(r'[^0-9]', '', parts[0])

    results = []
    if code:
        results = [r for r in DB if isinstance(r, dict) and str(r.get('ActualNB','') or r.get('ActualNo','')).strip()==num and clean(r.get('CodeDesc',''))==code]
    if not results:
        results = [r for r in DB if isinstance(r, dict) and str(r.get('ActualNB','') or r.get('ActualNo','')).strip()==num]
    if not results and len(num)>=5:
        full = raw if "/" in raw else num
        results = [r for r in DB if isinstance(r, dict) and (full in str(r.get('TelProp','')) or num in str(r.get('TelProp','')) )][:3]

    if not results:
        await update.message.reply_text("No results found.")
        return
    for r in results[:2]:
        await update.message.reply_text(format_car(r))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data.replace("tel:", "")
    results = [r for r in DB if isinstance(r, dict) and data in str(r.get('TelProp',''))][:3]
    if not results:
        num = re.sub(r'[^0-9]', '', data)
        results = [r for r in DB if isinstance(r, dict) and num in str(r.get('TelProp',''))][:3]
    if not results:
        await q.message.reply_text("No results found.")
        return
    for r in results:
        await q.message.reply_text(format_car(r))

TOKEN = os.getenv("BOT_TOKEN")
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run_polling()
