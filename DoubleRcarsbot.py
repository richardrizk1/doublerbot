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
    return "Bot is running"

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

def get_val(row, *keys):
    for k in keys:
        for rk in row.keys():
            if rk.lower() == k.lower() and row[rk]:
                v = str(row[rk]).strip()
                if v and v!= "0":
                    return v
    return ""

def search(q):
    q_clean = q.strip().upper().replace(" ", "")
    if not q_clean or not CSV_PATH or not os.path.exists(CSV_PATH):
        return []
    res = []
    try:
        with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                actual = get_val(row, 'ActualNB')
                code = get_val(row, 'CodeDesc')
                plate_full = f"{actual}{code}".upper().replace(" ", "")
                tel = get_val(row, 'TelProp', 'TELPROP', 'Phone', 'Mobile').replace(" ", "").replace("+", "")

                if plate_full == q_clean:
                    res.append(row)
                    if len(res) >= 3:
                        break
                elif q_clean.isdigit() and len(q_clean) >= 6 and q_clean in tel:
                    res.append(row)
                    if len(res) >= 3:
                        break
    except:
        pass
    return res

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل رقم اللوحة مثل: 2146 G\nأو 2146G\nأو رقم الهاتف")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) < 2:
        return

    results = search(text)
    if not results:
        await update.message.reply_text("No results found")
        return

    for r in results:
        plate_nb = get_val(r, 'ActualNB')
        plate_code = get_val(r, 'CodeDesc')
        phone = get_val(r, 'TelProp', 'Phone', 'Mobile')
        owner = get_val(r, 'OwnerName', 'PropName', 'Name', 'FullName')
        model = get_val(r, 'ModelDesc', 'Model', 'Make')
        year = get_val(r, 'YearProd', 'Year', 'ModelYear')
        color = get_val(r, 'ColorDesc', 'Color')
        chassis = get_val(r, 'ChassisNB', 'Chassis')
        address = get_val(r, 'Address', 'PropAddress')

        msg = f"Plate: {plate_nb} {plate_code}\n"
        if phone:
            msg += f"Phone: {phone}\n"
        if owner:
            msg += f"Name: {owner}\n"
        if model:
            msg += f"Car: {model}"
            if year:
                msg += f" {year}"
            msg += "\n"
        if color:
            msg += f"Color: {color}\n"
        if chassis:
            msg += f"Chassis: {chassis}\n"
        if address:
            msg += f"Address: {address}"

        await update.message.reply_text(msg.strip())

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    load_db()
    TOKEN = os.getenv("BOT_TOKEN")
    if TOKEN:
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
        app.run_polling(drop_pending_updates=True)
