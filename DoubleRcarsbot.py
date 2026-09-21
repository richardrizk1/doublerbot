import os, zipfile, csv, re, requests

FILE_ID = "1SJLWIC-JXHptMK_qEru1tMIStI814Mpz"
FILE_ZIP = "CARMDI.csv.zip"
FILE = "CARMDI.csv"

def download_file_from_google_drive(id, destination):
    print("Downloading database from Drive...")
    import requests
    if os.path.exists(destination):
        os.remove(destination)
    
    URL = "https://drive.google.com/uc?export=download"
    session = requests.Session()
    response = session.get(URL, params={'id': id}, stream=True)
    
    token = None
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            token = value
            break
    
    if token:
        params = {'id': id, 'confirm': token}
        response = session.get(URL, params=params, stream=True)
    
    with open(destination, "wb") as f:
        for chunk in response.iter_content(32768):
            if chunk:
                f.write(chunk)
    
    print("Download finished!")
if not os.path.exists("CARMDI.csv"):
    if not os.path.exists(FILE_ZIP):
        download_file_from_google_drive(FILE_ID, FILE_ZIP)
    print("Extracting...")
    with zipfile.ZipFile(FILE_ZIP, 'r') as zip_ref:
        zip_ref.extractall(".")
    print("Extracted!")

print(f"Loading {FILE}...")
DB = list(csv.DictReader(open(FILE, 'r', encoding='utf-8', errors='ignore')))
print(f"Loaded {len(DB)} records")
def clean(v):
    v=str(v or "").strip()
    return "" if v.lower() in ["none","null"] else v
    
START = """Hello this is Carmdi Bot! 
You can ask me to lookup car numbers or phone numbers. 
For car numbers: write the number followed by the code (e.g. 1111 B). 
For phone numbers: write the number without the extension. (e.g. if the number is 70/123456, send *only* 123456)."""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START)

def format_car(r):
    return f"""ActualNB: {clean(r.get('ActualNB') or r.get('ActualNo'))}
CodeDesc: {clean(r.get('CodeDesc'))}
PRODDATE: {clean(r.get('ProdYear') or r.get('PRODDATE'))}
Chassis: {clean(r.get('Chassis'))}
Moteur: {clean(r.get('Moteur'))}
dateaquisition: {clean(r.get('DateAquisition'))}
PreMiseCirc: {clean(r.get('PreMiseCirc'))}
CouleurDesc: {clean(r.get('CouleurDesc'))}
MarqueDesc: {clean(r.get('MarqueDesc') or r.get('Brand'))}
TypeDesc: {clean(r.get('TypeDesc') or r.get('Model'))}
UtilisDesc: {clean(r.get('UtilisDesc'))}
Prenom: {clean(r.get('Prenom'))}
Nom: {clean(r.get('Nom'))}
Addresse: {clean(r.get('Addresse'))}
NomMere: {clean(r.get('NomMere'))}
TelProp: {clean(r.get('TelProp') or r.get('Tel'))}
NoRegProp: {clean(r.get('NoRegProp'))}
AgeProp: {clean(r.get('AgeProp'))}
BirthPlace: {clean(r.get('BirthPlace'))}
HorsService: {clean(r.get('HorsService'))}"""

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    
    # 1. اذا فيه حروف وارقام كتير متل شاسي - امنعو متل البوت الأصلي
    if re.search(r'[A-Za-z]', raw) and len(re.sub(r'[^A-Za-z0-9]', '', raw)) > 8:
        if not re.search(r'[ج-ي]', raw): # اذا مش حرف عربي تبع نمر
            await update.message.reply_text("Error: Please send a valid input (number or number followed by a letter).")
            return

    num = re.sub(r'[^0-9]', '', raw)
    code = re.sub(r'[0-9\s/]', '', raw).strip()

    if len(num) < 3:
        await update.message.reply_text("Error: Please send a valid input (number or number followed by a letter).")
        return

    # 2. اذا الرقم 6 ارقام - يعني تلفون ناقص - طلع menu متل الأصلي
    if len(num) == 6 and not code:
        keyboard = [
            [InlineKeyboardButton(f"03/{num}", callback_data=f"tel:03/{num}")],
            [InlineKeyboardButton(f"76/{num} ج ج", callback_data=f"tel:76/{num}")],
            [InlineKeyboardButton(f"70/{num}", callback_data=f"tel:70/{num}")],
            [InlineKeyboardButton(f"71/{num}", callback_data=f"tel:71/{num}")],
            [InlineKeyboardButton(f"+96103{num}", callback_data=f"tel:03/{num}")],
        ]
        await update.message.reply_text("Choose an option:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # بحث عادي
    results = []
    if code:
        results = [r for r in DB if str(r.get('ActualNB','') or r.get('ActualNo','')).strip()==num and clean(r.get('CodeDesc',''))==code]
    if not results:
        results = [r for r in DB if str(r.get('ActualNB','') or r.get('ActualNo','')).strip()==num]
    if not results and len(num)>=5:
        full = raw if "/" in raw else num
        results = [r for r in DB if full in str(r.get('TelProp','')) or num in str(r.get('TelProp',''))][:3]

    if not results:
        await update.message.reply_text("No results found.")
        return

    for r in results[:2]:
        await update.message.reply_text(format_car(r))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data.replace("tel:","")
    results = [r for r in DB if data in str(r.get('TelProp',''))][:3]
    if not results:
        num = re.sub(r'[^0-9]', '', data)
        results = [r for r in DB if num in str(r.get('TelProp',''))][:3]
    if not results:
        await q.message.reply_text("No results found.")
        return
    for r in results:
        await q.message.reply_text(format_car(r))

TOKEN = "8805137194:AAFax72olCGlkXUjzTtOaBmernC9vAo2a8A"
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
print("بوت جديد - متل carmdi الأصلي مع menu")
app.run_polling()
