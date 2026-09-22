import os, glob, zipfile, requests
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

FILE_ID = "1SJLWIC-JXHptMK_qEru1tMIStI814Mpz"
ZIP_FILE = "CARMDI.csv.zip"
DB = []

def download_drive_file(file_id, dest):
    print(f"Downloading {dest} with workaround...")
    URL = "https://docs.google.com/uc?export=download"
    session = requests.Session()
    response = session.get(URL, params={'id': file_id}, stream=True)
    
    token = None
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            token = value
            break
    
    if token:
        params = {'id': file_id, 'confirm': token}
        response = session.get(URL, params=params, stream=True)

    with open(dest, "wb") as f:
        for chunk in response.iter_content(32768):
            if chunk:
                f.write(chunk)
    print(f"Downloaded size: {os.path.getsize(dest)} bytes")

def find_csv_file():
    for f in glob.glob("*.csv"):
        return f
    return None

def load_db():
    global DB
    csv_file = find_csv_file()
    
    if not csv_file:
        if not os.path.exists(ZIP_FILE):
            download_drive_file(FILE_ID, ZIP_FILE)
        
        if os.path.exists(ZIP_FILE) and os.path.getsize(ZIP_FILE) > 1000:
            try:
                with zipfile.ZipFile(ZIP_FILE, "r") as z:
                    print(f"ZIP contains: {z.namelist()}")
                    z.extractall(".")
                print("Unzipped")
            except Exception as e:
                print(f"Unzip error: {e}")
    
    csv_file = find_csv_file()
    print(f"Using CSV file: {csv_file}")

    if not csv_file:
        print("No CSV found!")
        return

    try:
        df = pd.read_csv(csv_file, dtype=str, low_memory=False).fillna("")
        DB = df.to_dict(orient="records")
        print(f"DB loaded: {len(DB)} records from {csv_file}")
    except Exception as e:
        print(f"DB Error: {e}")

def clean(t):
    t = str(t).upper()
    return "".join(c for c in t if c.isalnum())

def search(q):
    q = clean(q)
    if not q: return []
    res = []
    for row in DB:
        full = clean(f"{row.get('ActualNB','')}{row.get('CodeDesc','')}")
        tel = clean(row.get('TelProp',''))
        if q in full or q in tel:
            res.append(row)
            if len(res) >= 10: break
    return res

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"DB loaded: {len(DB)} records. Send plate number")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = search(update.message.text.strip())
    if not results:
        await update.message.reply_text("No results found")
        return
    for r in results[:3]:
        msg = f"{r.get('ActualNB','')} {r.get('CodeDesc','')}\n{r.get('TelProp','')}\n{r.get('ModelDesc','')} {r.get('YearProd','')}"
        await update.message.reply_text(msg)

load_db()
TOKEN = os.getenv("BOT_TOKEN")
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
print("Bot running...")
app.run_polling()
