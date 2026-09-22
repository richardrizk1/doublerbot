import asyncio
import logging
import os
import re
import threading
import unicodedata

import gdown
import pandas as pd
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Strip accidental spaces/newlines when the token is pasted into Render.
TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_FILE = os.getenv("CARMDI_FILE", "carmdi.csv").strip() or "carmdi.csv"
DRIVE_FILE_ID = "1LXD6OCDcX-poauodsFjfVSriVPfZbkLJ"
DRIVE_URL = f"https://drive.google.com/uc?export=download&id={DRIVE_FILE_ID}"

health_app = Flask(__name__)


@health_app.get("/")
def health_check():
    return "Bot is running", 200


def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    health_app.run(host="0.0.0.0", port=port)


def normalize_text(value) -> str:
    """Normalize accents, spaces, punctuation, and letter case for searching."""
    if value is None:
        return ""

    value = unicodedata.normalize("NFKD", str(value).strip().lower())
    value = "".join(
        character for character in value
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]", "", value)


def clean_column_name(value) -> str:
    return str(value).strip().replace("\ufeff", "")


def ensure_database():
    if os.path.exists(DATABASE_FILE):
        return DATABASE_FILE

    try:
        logging.info("Downloading carmdi.csv from Google Drive...")
        # gdown 6.x does not support the fuzzy keyword in download().
        output = gdown.download(DRIVE_URL, DATABASE_FILE, quiet=False)
        if output and os.path.exists(output):
            logging.info("Database downloaded to %s", output)
            return output
        if os.path.exists(DATABASE_FILE):
            logging.info("Database downloaded to %s", DATABASE_FILE)
            return DATABASE_FILE
    except Exception:
        logging.exception("Failed to download carmdi.csv")

    return None


def load_database():
    path = ensure_database()
    if not path:
        logging.error("Database file is unavailable")
        return pd.DataFrame()

    try:
        # Detect comma, semicolon, tab, and other common delimiters.
        data = pd.read_csv(
            path,
            dtype=str,
            encoding="utf-8-sig",
            sep=None,
            engine="python",
            keep_default_na=False,
        ).fillna("")
        data.columns = [clean_column_name(column) for column in data.columns]
        logging.info("Loaded %s rows from %s", len(data), path)
        logging.info("CSV columns: %s", list(data.columns))
        return data
    except Exception:
        logging.exception("Could not read database %s", path)
        return pd.DataFrame()


df = load_database()

# These are the actual column names shown in the CARMDI screens.
SEARCH_COLUMNS = {
    "tel": ["TelProp"],
    "plate": ["NoRegProp"],
    "name": ["Prenom", "Nom"],
}


def find_column(name: str):
    """Find a CSV column case-insensitively and ignoring formatting."""
    wanted = normalize_text(name)
    for column in df.columns:
        if normalize_text(column) == wanted:
            return column
    return None


def search_data(query: str, mode: str):
    if df.empty:
        logging.warning("Search attempted, but database is empty")
        return []

    query_normalized = normalize_text(query)
    if not query_normalized:
        return []

    configured_columns = SEARCH_COLUMNS.get(mode, [])
    columns = [
        actual_column
        for configured_column in configured_columns
        if (actual_column := find_column(configured_column)) is not None
    ]

    if not columns:
        logging.error(
            "Search columns for mode %s were not found. Available columns: %s",
            mode,
            list(df.columns),
        )
        return []

    results = []
    for _, row in df.iterrows():
        # Joining Prenom and Nom allows searching either one or both together.
        searchable_text = normalize_text(
            " ".join(str(row.get(column, "")) for column in columns)
        )
        if query_normalized in searchable_text:
            results.append(row.to_dict())
        if len(results) >= 5:
            break

    logging.info(
        "Search mode=%s columns=%s query=%r results=%d",
        mode,
        columns,
        query,
        len(results),
    )
    return results


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
        "name": "Send first name, last name, or both:",
    }
    await query.message.reply_text(prompts.get(mode, "Send search:"))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    if not mode:
        await update.message.reply_text("Please press /start and choose a search type first.")
        return

    text = (update.message.text or "").strip()
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


async def run_bot():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing")

    threading.Thread(target=run_health_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
    await asyncio.Event().wait()

    await app.stop()
    await app.shutdown()


if __name__ == "__main__":
    asyncio.run(run_bot())
