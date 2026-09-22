import os, zipfile, requests
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

FILE_ID = "1SJLWIC-JXHptMK_qEru1tMIStI814Mpz"
CSV_FILE = "CAR.csv"
ZIP_FILE = "CAR.csv.zip"
DB = []

def download_from_drive(file_id, dest):
    print(f"Downloading {dest}...")
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    s = requests.Session()
    r = s.get(url, stream=True)
    for k, v in r.cookies.items():
        if k.startswith("download_warning"):
            url = f"https://drive.google.com/uc?export=download&confirm={v}&id={file_id}"
            r = s.get(url, stream=True)
            break
    with open(dest, "wb") as f:
        for chunk in r.iter_content(32768):
            if chunk:
                f.write(chunk)
    print("Download done")

def load_db():
    global DB
    if not os.path.exists(CSV_FILE):
        if not os.path.exists(ZIP_FILE):
            download_from_drive(FILE_ID, ZIP_FILE)
        if os.path.exists(ZIP_FILE):
            try:
                with zipfile.ZipFile(ZIP_FILE, "r") as z:
                    z.extractall(".")
                print("Unzipped")
            except:
                try:
                    os.rename(ZIP_FILE, CSV_FILE)
                except:
                    pass
    try:
        df = pd.read_csv(CSV_FILE, dtype=str, low_memory=False).fillna("")
        DB = df.to_dict(orient="records")
        print(f"DB loaded: {len(DB)} records")
    except Exception as e:
        print(f"Error: {e}")

def clean(t):
    t = str(t).upper()
    out = ""
    for c in t:
        if c.isalnum():
            out += c
    return out

def search(q):
    q = clean(q)
    if not q:
        return []
    res = []
    for row in DB:
        full = clean(f"{row.get('ActualNB','')}{row.get('CodeDesc','')}")
        tel = clean(row.get('TelProp',''))
        if q in full or q in tel:
            res.append(row)
            if len(res) >= 10:
                break
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
