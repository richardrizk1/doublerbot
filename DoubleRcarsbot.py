import os
import logging
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
EXCEL_FILE = os.getenv("EXCEL_FILE", "data.xlsx")

df = pd.DataFrame()
try:
    df = pd.read_excel(EXCEL_FILE, dtype=str).fillna("")
    print(f"Loaded {len(df)} rows")
except Exception as e:
    print(f"Error loading excel: {e}")

def search_data(query, mode):
    if df.empty: return []
    query = str(query).lower().strip()
    results = []
    for _, row in df.iterrows():
        row_str = " ".join([str(v).lower() for v in row.values])
        if query in row_str:
            results.append(row.to_dict())
    return results[:5]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📞 Phone Number", callback_data="tel"),
         InlineKeyboardButton("🚗 Plate Number", callback_data="plate")],
        [InlineKeyboardButton("👤 Prenom+Nom", callback_data="name")]
    ]
    await update.message.reply_text("Choose search type:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = query.data
    context.user_data["mode"] = mode
    texts = {"tel": "Send phone number:", "plate": "Send plate number:", "name": "Send name (prenom nom):"}
    await query.message.reply_text(texts.get(mode, "Send search:"))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    if not mode:
        await update.message.reply_text("Please press /start and choose type first")
        return
    text = update.message.text.strip()
    res = search_data(text, mode)
    if not res:
        await update.message.reply_text(f"No results for: {text}")
        return
    msg = ""
    for r in res:
        msg += "\n---\n" + "\n".join([f"{k}: {v}" for k,v in r.items()])
    await update.message.reply_text(msg[:4000])

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
