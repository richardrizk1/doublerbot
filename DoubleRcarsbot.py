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
    size = "No DB"
    if CSV_PATH and os.path.exists(CSV_PATH):
        size = f"{os.path.getsize(CSV_PATH)//1024//1024}MB"
    return f"Bot running - DB: {size} - Path: {CSV_PATH}"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

FILE_ID = "1LXD6OCDcX-poauodsFjfVSriVPfZbkLJ"
ZIP_FILE = "CARMDI.csv.zip"

def download_drive_file(file_id, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 100000000:
        print(f"File exists {os.path.getsize(dest)} bytes, skipping download")
        return
    print(f"Downloading {dest}...")
    gdown.download(id=file_id, output=dest, quiet=False)
    print(f"Downloaded: {os.path.getsize(dest)} bytes")

def find_csv():
    for f in glob.glob("*.csv"):
        return f
    return None

def load_db():
    global CSV_PATH
    csv_file = find_csv()
    if not csv_file:
        if not os.path.exists(ZIP_FILE) or os.path.getsize(ZIP_FILE) < 100000000:
            download_drive_file(FILE_ID, ZIP_FILE)
        if os.path.exists(ZIP_FILE):
            print("Extracting...")
            with zipfile.ZipFile(ZIP_FILE, "r") as z:
                print(f"ZIP: {z.namelist()}")
                z.extractall(".")
    CSV_PATH = find_csv()
    if CSV_PATH:
        print(f"CSV ready: {CSV_PATH} size={os.path.getsize(CSV_PATH)//1024//1024}MB")
    else:
        print("No CSV found!")

def clean(t):
    return "".join(c for c in str(t).upper() if c.isalnum())

def search(q):
    q = clean(q)
    if not q or not CSV_PATH or not os.path.exists(CSV_PATH):
        return []
    res = []
    try:
        with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                full = clean(f"{row.get('ActualNB','')}{row.get('CodeDesc','')}")
                tel = clean(row.get('TelProp',''))
                if q in full or q in tel:
                    res.append(row)
                    if len(res) >= 10:
                        break
    except Exception as e:
        print(f"Search error: {e}")
    return res

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"DB ready: {CSV_PATH}\nSend plate number")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = search(update.message.text.strip())
    if not results:
        await update.message.reply_text("No results found")
        return
    for r in results[:3]:
        msg = f"{r.get('ActualNB','')} {r.get('CodeDesc','')}\n{r.get('TelProp','')}\n{r.get('ModelDesc','')} {r.get('YearProd','')}"
        await update.message.reply_text(msg)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    load_db()
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("BOT_TOKEN not set!")
    else:
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
        print("Bot running...")
        app.run_polling()
