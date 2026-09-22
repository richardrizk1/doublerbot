import os, re
import pandas as pd
import gdown
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

FILE_ID = "1SJLWIC-JXHptMK_qEru1tMIStI814Mpz"
GDRIVE_URL = f"https://drive.google.com/uc?id={FILE_ID}"
CSV_FILE = "CAR.csv"
DB = []

def load_db():
    global DB
    if not os.path.exists(CSV_FILE):
        print("Downloading CAR.csv from Drive...")
        gdown.download(GDRIVE_URL, CSV_FILE, quiet=False)
    try:
        df = pd.read_csv(CSV_FILE, dtype=str, low_memory=False).fillna("")
        DB = df.to_dict(orient="records")
        print(f"DB loaded: {len(DB)} records")
    except Exception as e:
        print(f"Error: {e}")
        DB = []

def clean(t): 
    return re.sub(r'[^A-Z0-9]', '', str(t).upper())

def search(query):
    q = clean(query)
    if not q: 
        return []
    res = []
    for row in DB:
        full_nb = clean(f"{row.get('ActualNB','')}{row.get('CodeDesc','')}")
        only_nb = clean(row.get('ActualNB',''))
        tel = clean(row.get('TelProp',''))
        if q in full_nb or q == only_nb or q in tel:
            res.append(row)
            if len(res) >= 10: 
                break
    return res

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"DB loaded: {len(DB)} records. Send plate number like 2146 G")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = search(query)
    if not results:
        await update.message.reply_text("No results found")
        return
    for r in results[:3]:
        msg = f"{r.get('ActualNB','')} {r.get('CodeDesc','')}\n{r.get('TelProp','')}\n{r.get('ModelDesc','')} {r.get('ColorDesc','')} {r.get('YearProd','')}"
        await update.message.reply_text(msg)

load_db()
TOKEN = os.getenv("BOT_TOKEN")
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
print("Bot running...")
app.run_polling()
