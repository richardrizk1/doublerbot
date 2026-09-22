import os, re, zipfile, requests
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

FILE_ID = "1SJLWIC-JXHptMK_qEru1tMIStI814Mpz"
CSV_FILE = "CAR.csv"
ZIP_FILE = "CAR.csv.zip"
DB = []

def download_from_drive(file_id, dest):
    print(f"Downloading {dest} from Drive...")
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    session = requests.Session()
    r = session.get(url, stream=True)
    for key, value in r.cookies.items():
        if key.startswith('download_warning'):
            url = f"https://drive.google.com/uc?export=download&confirm={value}&id={file_id}"
            r = session.get(url, stream=True)
            break
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(32768):
            if chunk:
                f.write(chunk)
    print("Download done")

def load_db():
    global DB
    if not os.path.exists(CSV_FILE):
        if not os.path.exists(ZIP_FILE):
            download_from_drive(FILE_ID, ZIP_FILE)
        if os.path.exists(ZIP_FILE) and ZIP_FILE.endswith('.zip'):
            try:
                with zipfile.ZipFile(ZIP_FILE, 'r') as z:
                    z.extractall(".")
                print("Unzipped")
            except:
                os.rename(ZIP_FILE, CSV_FILE)
    
    try:
        df = pd.read_csv(CSV_FILE, dtype=str, low_memory=False).fillna("")
        DB = df.to_dict(orient="records")
        print(f"DB loaded: {len(DB)} records")
    except Exception as e:
        print(f"Error: {e}")

def clean(t): 
    return re.sub(r'[^A-Z
