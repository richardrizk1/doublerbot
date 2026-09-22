import asyncio
import csv
import logging
import os
import re
import shutil
import threading
import unicodedata
import zipfile

import gdown
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

TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_FILE = os.getenv("CARMDI_FILE", "CARMDI.csv").strip() or "CARMDI.csv"
ARCHIVE_FILE = os.getenv("CARMDI_ARCHIVE", "CARMDI.csv.zip").strip() or "CARMDI.csv.zip"
DRIVE_FILE_ID = "1SJLWIC-JXHptMK_qEru1tMlStI814Mpz"
DRIVE_URL = f"https://drive.google.com/uc?export=download&id={DRIVE_FILE_ID}"
SEARCH_COLUMNS = {
    "tel": ["TelProp"],
    "plate": ["NoRegProp"],
    "name": ["Prenom", "Nom"],
}
MAX_RESULTS = 5

health_app = Flask(__name__)


@health_app.get("/")
def health_check():
    return "Bot is running", 200


def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    health_app.run(host="0.0.0.0", port=port)


def normalize_text(value) -> str:
    """Normalize case, accents, whitespace, and punctuation for searching."""
    if value is None:
        return ""

    value = unicodedata.normalize("NFKD", str(value).strip().casefold())
    value = "".join(
        character for character in value
        if not unicodedata.combining(character)
    )
    return "".join(character for character in value if character.isalnum())


def normalize_phone(value) -> str:
    """Return only phone digits so formatting does not affect matching."""
    if value is None:
        return ""
    return "".join(character for character in str(value) if character.isdigit())


def clean_column_name(value) -> str:
    return str(value).strip().replace("\ufeff", "")


def ensure_database():
    if os.path.exists(DATABASE_FILE) and os.path.getsize(DATABASE_FILE) > 0:
        return DATABASE_FILE

    try:
        logging.info("Downloading %s from Google Drive...", ARCHIVE_FILE)
        output = gdown.download(DRIVE_URL, ARCHIVE_FILE, quiet=False)
        archive_path = output or ARCHIVE_FILE

        if not os.path.exists(archive_path):
            logging.error("Google Drive download did not create %s", archive_path)
            return None
        if not zipfile.is_zipfile(archive_path):
            logging.error("Downloaded file is not a valid ZIP archive: %s", archive_path)
            return None

        with zipfile.ZipFile(archive_path, "r") as archive:
            csv_members = [
                member for member in archive.namelist()
                if member.lower().endswith(".csv") and not member.endswith("/")
            ]
            if not csv_members:
                logging.error("No CSV file was found inside %s", archive_path)
                return None

            member_name = next(
                (
                    member for member in csv_members
                    if os.path.basename(member).lower() == "carmdi.csv"
                ),
                csv_members[0],
            )

            with archive.open(member_name) as source, open(DATABASE_FILE, "wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

        logging.info(
            "Extracted %s to %s (%d bytes)",
            member_name,
            DATABASE_FILE,
            os.path.getsize(DATABASE_FILE),
        )
        return DATABASE_FILE if os.path.getsize(DATABASE_FILE) > 0 else None

    except Exception:
        logging.exception("Failed to download or extract %s", ARCHIVE_FILE)
        return None


def detect_csv_format(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as file:
        sample = file.read(1024 * 1024)

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    logging.info("Detected CSV delimiter: %r", delimiter)
    return delimiter


def load_database():
    path = ensure_database()
    if not path:
        logging.error("Database file is unavailable")
        return None, []

    try:
        delimiter = detect_csv_format(path)
        with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as file:
            reader = csv.reader(file, delimiter=delimiter)
            columns = [clean_column_name(column) for column in next(reader, [])]

        logging.info("CSV columns: %s", columns)
        logging.info("Database ready at %s; rows will be searched in streaming mode", path)
        return path, columns
    except Exception:
        logging.exception("Could not inspect database %s", path)
        return None, []


database_path, database_columns = load_database()


def find_column(name: str):
    wanted = normalize_text(name)
    for column in database_columns:
        if normalize_text(column) == wanted:
            return column
    return None


def search_data(query: str, mode: str):
    if not database_path:
        logging.warning("Search attempted, but database is unavailable")
        return []

    if mode == "tel":
        query_normalized = normalize_phone(query)
    else:
        query_normalized = normalize_text(query)

    if not query_normalized:
        return []

    columns = [
        actual_column
        for configured_column in SEARCH_COLUMNS.get(mode, [])
        if (actual_column := find_column(configured_column)) is not None
    ]
    if not columns:
        logging.error(
            "Search columns for mode %s were not found: %s",
            mode,
            database_columns,
        )
        return []

    delimiter = detect_csv_format(database_path)
    results = []
    try:
        with open(
            database_path,
            "r",
            encoding="utf-8-sig",
            errors="replace",
            newline="",
        ) as file:
            reader = csv.DictReader(file, delimiter=delimiter)
            for row in reader:
                if mode == "tel":
                    # Phone searches use an exact suffix match. For example,
                    # entering 123456 matches only numbers ending in 123456,
                    # not numbers that merely contain 123456 in the middle.
                    phone_value = normalize_phone(row.get(columns[0], ""))
                    matches = phone_value.endswith(query_normalized)
                else:
                    searchable_text = normalize_text(
                        " ".join(str(row.get(column, "")) for column in columns)
                    )
                    matches = query_normalized in searchable_text

                if matches:
                    results.append(dict(row))
                    if len(results) >= MAX_RESULTS:
                        break
    except Exception:
        logging.exception("Search failed for %r", query)
        return []

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
        "tel": "Send phone number or its last digits:",
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
