import os, glob, zipfile, threading, sys, asyncio, csv
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gdown

if sys.version_info >= (3, 12):
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

flask_app = Flask(__name__)
CSV_PATH = None

@flask_app.route('/')
def home():
    return f"Bot running - {CSV_PATH}"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

FILE_ID = "1LXD6OCDcX-poauodsFjfVSriVPfZbkLJ"
ZIP_FILE = "CARMDI.csv.zip"

def download_drive_file(file_id, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 100000000:
        return
    gdown.download(id=file_id, output=dest, quiet=False)

def find_csv():
    for f in glob.glob("*.csv"):
        return f
    return None

def load_db():
    global CSV_PATH
    if not find_csv():
        if not os.path.exists(ZIP_FILE) or os.path.getsize(ZIP_FILE) < 100000000:
            download_drive_file(FILE_ID, ZIP_FILE)
        if os.path.exists(ZIP_FILE):
            with zipfile.ZipFile(ZIP_FILE, "r") as z:
                z.extractall(".")
    CSV_PATH = find_csv()

def search(q):
    q = q.strip().upper().replace(" ", "")
    if not q or not CSV_PATH:
        return []
    res = []
    with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        
        print(f"Columns: {reader.fieldnames}")
        for row in reader:
            full = f"{row.get('ActualNB','').strip()}{row.get('CodeDesc','').strip()}".upper().replace(" ", "")
            if full == q:
                res.append(row)
                if len(res) >= 5:
                    break
    return res

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send plate like: 2146G")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = search(update.message.text)
    if not results:
        await update.message.reply_text("No results found")
        return
    for r in results:
       
        phone = r.get('TelProp','') or r.get('TELPROP','') or r.get('Phone','') or r.get('Tel','') or r.get('Mobile','') or ""
        owner = r.get('OwnerName','') or r.get('Name','') or r.get('PropName','') or ""
        model = r.get('ModelDesc','') or r.get('Model','') or ""
        year = r.get('YearProd','') or r.get('Year','') or ""
        
        text = f"Plate: {r.get('ActualNB','')} {r.get('CodeDesc','')}\n"
        text += f"Phone: {phone}\n"
        if owner:
            text += f"Name: {owner}\n"
        if model:
            text += f"Car: {model} {year}"
        
        await update.message.reply_text(text)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    load_db()
    TOKEN = os.getenv("BOT_TOKEN")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling()
