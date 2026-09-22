import os
import logging

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
    if value is None:
        return ""
    return str(value).strip().lower()


def ensure_database():
    if os.path.exists(DATABASE_FILE):
        return DATABASE_FILE

    try:
        logging.info("Downloading carmdi.csv from Google Drive...")
        output = gdown.download(DRIVE_URL, DATABASE_FILE, quiet=False, fuzzy=True)
        if output and os.path.exists(output):
            logging.info("Database downloaded to %s", output)
            return output
        if os.path.exists(DATABASE_FILE):
            logging.info("Database downloaded to %s", DATABASE_FILE)
            return DATABASE_FILE
    except Exception as exc:
        logging.exception("Failed to download carmdi.csv: %s", exc)

    return None


def get_search_columns(mode: str, columns):
    aliases = {
        "tel": ["phone", "telephone", "tel", "mobile", "portable", "numero_tel", "numero_telephone", "num_tel", "contact"],
        "plate": ["plate", "plaque", "immatriculation", "numero_plaque", "matricule", "registration", "vehicule"],
        "name": ["name", "nom", "prenom", "prenom_nom", "nom_prenom", "full_name", "noms", "personne", "client"],
    }

    candidates = []
    wanted = aliases.get(mode, [])
    for column in columns:
        normalized = normalize_text(column)
        if any(alias in normalized for alias in wanted) or normalized in wanted:
            candidates.append(column)

    if not candidates:
        for column in columns:
            normalized = normalize_text(column)
            if mode == "tel" and any(token in normalized for token in ["tel", "phone", "contact"]):
                candidates.append(column)
            elif mode == "plate" and any(token in normalized for token in ["plate", "plaque", "immat", "matricule"]):
                candidates.append(column)
            elif mode == "name" and any(token in normalized for token in ["name", "nom", "prenom"]):
                candidates.append(column)

    if not candidates:
        return list(columns)

    return candidates


def load_database():
    path = ensure_database()
    if not path:
        return pd.DataFrame()

    try:
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", low_memory=False).fillna("")
        logging.info("Loaded %s rows from %s", len(df), path)
        return df
    except Exception as exc:
        logging.exception("Error reading database %s: %s", path, exc)
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
        row_values = []
        for col in columns:
            row_values.append(normalize_text(row.get(col, "")))

        row_str = " ".join(row_values)
        if query in row_str:
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
    texts = {
        "tel": "Send phone number:",
        "plate": "Send plate number:",
        "name": "Send name (prenom nom):",
    }
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
        msg += "\n---\n" + "\n".join(f"{k}: {v}" for k, v in r.items())

    await update.message.reply_text(msg[:4000])


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing. Set it before running the bot.")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
