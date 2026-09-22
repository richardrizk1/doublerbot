import os
import re
import csv
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
CSV_PATH = "CARMdi.csv"
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def get_val(row, *names):
    for n in names:
        for k in row.keys():
            if k.lower().strip() == n.lower().strip():
                return str(row[k] or "").strip()
    return ""

def norm_phone(s):
    return re.sub(r'\D', '', str(s))

def norm_txt(s):
    return str(s).lower().strip()

def norm_plate(s):
    return str(s).upper().replace(" ", "").strip()

def search_tel(q):
    qp = norm_phone(q)
    if len(qp) < 3:
        return []
    res = []
    with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if qp in norm_phone(get_val(row, 'TelProp')):
                res.append(row)
                if len(res) >= 5:
                    break
    return res

def search_plate(q):
    qp = norm_plate(q)
    if not qp:
        return []
    res = []
    with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            plate = norm_plate(get_val(row, 'ActualNB') + get_val(row, 'CodeDesc'))
            if qp in plate:
                res.append(row)
                if len(res) >= 5:
                    break
    return res

def search_name(q):
    parts = norm_txt(q).split()
    if not parts:
        return []
    res = []
    with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prenom = norm_txt(get_val(row, 'Prenom'))
            nom = norm_txt(get_val(row, 'Nom'))
            if len(parts) >= 2:
                if (parts[0] in prenom and parts[1] in nom) or (parts[0] in nom and parts[1] in prenom):
                    res.append(row)
            else:
                if parts[0] in prenom or parts[0] in nom:
                    res.append(row)
            if len(res) >= 5:
                break
    return res

def format_row(row):
    return f"Plate: {get_val(row,'ActualNB')} {get_val(row,'CodeDesc')}\nName: {get_val(row,'Prenom')} {get_val(row,'Nom')}\nMother: {get_val(row,'NomMere')}\nTel: {get_val(row,'TelProp')}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Phone Number", callback_data='tel')],
        [InlineKeyboardButton("Plate Number", callback_data='plate')],
        [InlineKeyboardButton("Prenom + Nom", callback_data='name')],
    ]
    await update.message.reply_text("Choose search type:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data['mode'] = q.data
    if q.data == 'tel':
        await q.edit_message_text("Send phone number:")
    elif q.data == 'plate':
        await q.edit_message_text("Send plate number:")
    else:
        await q.edit_message_text("Send Prenom + Nom:")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text
    mode = context.user_data.get('mode', 'tel')
    if mode == 'tel':
        res = search_tel(q)
    elif mode == 'plate':
        res = search_plate(q)
    else:
        res = search_name(q)
    if not res:
        await update.message.reply_text(f"No results for: {q}. Use /start")
        return
    for r in res:
        await update.message.reply_text(format_row(r))

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def main():
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    threading.Thread(target=run_flask, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
