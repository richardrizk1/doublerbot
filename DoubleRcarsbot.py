import asyncio
import logging
import os

import gdown
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_FILE = os.getenv("CARMDI_FILE", "carmdi.csv")
DRIVE_FILE_ID = "1LXD6OCDcX-poauodsFjfVSriVPfZbkLJ"
DRIVE_URL = f"https://drive.google.com/uc?export=download&id={DRIVE_FILE_ID}"


def normalize_text(value) -> str:
    return "" if value is None else str(value).strip().lower()


def ensure_database():
    if os.path.exists(DATABASE_FILE):
        return DATABASE_FILE

    try:
        logging.info("Downloading carmdi.csv from Google Drive...")
        output = gdown.download(DRIVE_URL, DATABASE_FILE, quiet=False, fuzzy=True)
        if output and os.path.exists(output):
            return output
        if os.path.exists(DATABASE_FILE):
            return DATABASE_FILE
    except Exception:
        logging.exception("Failed to download carmdi.csv")

    return None


def get_search_columns(mode: str, columns):
    aliases = {
        "tel": ["phone", "telephone", "tel", "mobile", "portable", "contact"],
        "plate": ["plate", "plaque", "immatriculation", "matricule", "registration"],
        "name": ["name", "nom", "prenom", "full_name", "client"],
    }
    wanted = aliases.get(mode, [])
    matches = [
        column for column in columns
        if any(alias in normalize_text(column) for alias in wanted)
    ]
    return matches or list(columns)


def load_database():
    path = ensure_database()
    if not path:
        logging.error("Database file is unavailable")
        return pd.DataFrame()

    try:
        data = pd.read_csv(
            path,
            dtype=str,
            encoding="utf-8-sig",
            low_memory=False,
        ).fillna("")
        logging.info("Loaded %s rows from %s", len(data), path)
        return data
    except Exception:
        logging.exception("Could not read database %s", path)
        return pd.DataFrame()


df = load_database()


def search_data(query: str, mode: str):
    if df.empty:
        return []

    query = normalize_text(query)
    if not query:
        return []

    columns = get_search_columns(mode, list(df.columns))
    results = []
    for _, row in df.iterrows():
        searchable_text = " ".join(normalize_text(row.get(column, "")) for column in columns)
        if query in searchable_text:
            results.append(row.to_dict())
    return results[:5]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📞 Phone Number", callback_data="tel"),
            InlineKeyboardButton("🚗 Plate Number", callback_data="plate"),
        ],
        [InlineKeyboardButton("👤 Prenom+Nom", callback_data="name")],
    ]
    await update.message.reply_text(
        "Choose search type:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = query.data
    context.user_data["mode"] = mode
    prompts = {
        "tel": "Send phone number:",
        "plate": "Send plate number:",
        "name": "Send name (prenom nom):",
    }
    await query.message.reply_text(prompts.get(mode, "Send search:"))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    if not mode:
        await update.message.reply_text("Please press /start and choose type first")
        return

    text = update.message.text.strip()
    results = search_data(text, mode)
    if not results:
        await update.message.reply_text(f"No results for: {text}")
        return

    message = ""
    for result in results:
        message += "\n---\n" + "\n".join(
            f"{key}: {value}" for key, value in result.items()
        )
    await update.message.reply_text(message[:4000])


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing")

    # Python 3.14 no longer creates a default event loop automatically.
    # python-telegram-bot 22.3 still calls asyncio.get_event_loop() internally.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
