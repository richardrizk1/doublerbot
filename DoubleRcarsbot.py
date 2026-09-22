import os, re, csv, threading
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
    q_phone = norm_phone(q)
    if len(q_phone) < 3: return []
    results = []
    with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tel = norm_phone(get_val(row, 'TelProp'))
            if q_phone in tel:
                results.append(row)
                if len(results) >= 5: break
    return results

def search_plate(q):
    q_plate = norm_plate(q)
    results = []
    with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            plate = norm_plate(get_val(row, 'ActualNB') + get_val(row, 'CodeDesc'))
            if q_plate in plate:
                results.append(row)
                if len(results) >= 5: break
    return results

def search_name(q):
    parts = norm_txt(q).split()
    results = []
    with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prenom = norm_txt(get_val(row, 'Prenom'))
            nom = norm_txt(get_val(row, 'Nom'))
            full = f"{prenom} {nom}"
            if len(parts) >= 2:
                if (parts[0] in prenom and parts[1] in nom) or (f"{parts[0]} {parts[1]}" in full):
                    results.append(row)
            else:
                if parts[0] in prenom or parts[0] in nom:
                    results.append(row)
            if len(results) >= 5: break
    return results

def format_row(row):
    return f"Plate: {get_val(row,'ActualNB')} {get_val(row,'CodeDesc')}\nName: {get_val(row,'Prenom')} {get_val(row,'Nom')}\nMother: {get_val(row,'NomMere')}\nTel: {get_val(row,'TelProp')}\nAge: {get_val(row,'AgeProp')}"
async def start(update, context):
    keyboard = [[InlineKeyboardButton("Phone Number", callback_data='tel')],[InlineKeyboardButton("Plate Number", callback_data='plate')],[InlineKeyboardButton("Prenom + Nom", callback_data='name')]]
    await update.message.reply_text("Choose search type:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data['mode'] = q.data
    if q.data == 'tel': await q.edit_message_text("Send phone number:")
    if q.data == 'plate': await q.edit_message_text("Send plate number:")
    if q.data == 'name': await q.edit_message_text("Send Prenom + Nom:")

async def handle(update, context):
    q = update.message.text
    mode = context.user_data.get('mode', 'tel')
    if mode == 'tel': res = search_tel(q)
    elif mode == 'plate': res = search_plate(q)
    else: res = search_name(q)
    if not res:
        await update.message.reply_text(f"No results for: {q}")
        return
    for r in res:
        await update.message.reply_text(format_row(r))

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling()

if __name__ == '__main__':
    main()
