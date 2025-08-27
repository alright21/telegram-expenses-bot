import json
import logging
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

with open("config.json") as f:
    config = json.load(f)

TELEGRAM_TOKEN = config["TELEGRAM_TOKEN"]
SHEET_ID = config["SHEET_ID"]
ALLOWED_USER_ID = config["ALLOWED_USER_ID"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID)

PRIMARY_CATEGORIES = ["Housing", "Health", "Groceries", "Transport", "Out", 
                      "Travel", "Clothing", "Leisure", "Gifts", "Fees", "OtherExpenses"]

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# ----- State -----
user_data = {}

def is_allowed(update):
    return update.message.from_user.id == ALLOWED_USER_ID


# ----- Handlers -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    if not is_allowed(update):
        await update.message.reply_text("⚠️ Non sei autorizzato a usare questo bot.")
        return

    month = context.user_data.get("month", "Sep")
    worksheet = sheet.worksheet(month)
    
    keyboard = [
        [InlineKeyboardButton("Carica scontrino", callback_data="receipt")],
        [InlineKeyboardButton("Manuale", callback_data="manual")],
        [InlineKeyboardButton("Cambia mese", callback_data="change_month")]
    ]
    await update.message.reply_text(f"Benvenuto! Il mese corrente è: {month}\nScegli un'opzione:", reply_markup=InlineKeyboardMarkup(keyboard))

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        
    query = update.callback_query
    await query.answer()

    if query.data == "receipt":
        user_data[query.from_user.id] = {"mode": "receipt"}
        await query.edit_message_text("Invia la foto dello scontrino.")
    elif query.data == "manual":
        user_data[query.from_user.id] = {"mode": "manual", "step": "name"}
        await query.edit_message_text("Inserisci il nome della spesa.")
    elif query.data == "change_month":
        await query.answer()
        keyboard = [
            [InlineKeyboardButton(m, callback_data=f"set_month:{m}")]
            for m in MONTHS
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Scegli il mese:", reply_markup=reply_markup)

    elif query.data.startswith("set_month:"):
        await query.answer()
        month = query.data.split(":")[1]
        context.user_data["month"] = month
        await query.edit_message_text(f"Mese cambiato a: {month}")
        await start(query, context)


async def receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    user_id = update.message.from_user.id
    if user_id not in user_data or user_data[user_id].get("mode") != "receipt":
        return

    # --- placeholder: send image to Gemini API to parse ---
    # You'd call Gemini API here. For now, fake result:
    parsed = {
        "price": 12.50,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "name": "Bar Caffè",
        "primary": "Out",
        "secondary": "Caffè"
    }
    user_data[user_id].update(parsed)
    user_data[user_id]["step"] = "confirm"

    text = (f"Ho letto:\n"
            f"Nome: {parsed['name']}\n"
            f"Data: {parsed['date']}\n"
            f"Prezzo: {parsed['price']}\n"
            f"Cat. primaria: {parsed['primary']}\n"
            f"Cat. secondaria: {parsed['secondary']}\n"
            f"Tutto ok?")
    keyboard = [
        [InlineKeyboardButton("Sì", callback_data="confirm_yes")],
        [InlineKeyboardButton("No (manuale)", callback_data="confirm_no")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def manual_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("In manual_text_handler")
    
    user_id = update.message.from_user.id
    if user_id not in user_data or user_data[user_id].get("mode") != "manual":
        return

    step = user_data[user_id].get("step")
    text = update.message.text.strip()

    if step == "name":
        user_data[user_id]["name"] = text
        user_data[user_id]["step"] = "date"
        await update.message.reply_text("Inserisci il giorno (DD):")
    elif step == "date":
        user_data[user_id]["date"] = text
        user_data[user_id]["step"] = "price"
        await update.message.reply_text("Inserisci il prezzo:")
    elif step == "price":
        user_data[user_id]["price"] = float(text)
        user_data[user_id]["step"] = "primary"
        # Build inline keyboard of categories
        keyboard = []
        for cat in PRIMARY_CATEGORIES:
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{cat}")])

        await update.message.reply_text(
            "Scegli categoria primaria:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif step == "secondary":
        user_data[user_id]["secondary"] = text
        user_data[user_id]["step"] = "confirm_manual"
        summary = (f"Riepilogo:\n"
                   f"Nome: {user_data[user_id]['name']}\n"
                   f"Data: {user_data[user_id]['date']}\n"
                   f"Prezzo: {user_data[user_id]['price']}\n"
                   f"Primaria: {user_data[user_id]['primary']}\n"
                   f"Secondaria: {user_data[user_id]['secondary']}\n"
                   f"Tutto ok?")
        keyboard = [
            [InlineKeyboardButton("Sì", callback_data="manual_yes")],
            [InlineKeyboardButton("No", callback_data="manual_no")]
        ]
        await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("Non capisco. Inizia con /start.")

async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("In category_handler")
    
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data or user_data[user_id].get("step") != "primary":
        return

    # Extract category name from callback_data
    chosen_cat = query.data.replace("cat_", "")
    user_data[user_id]["primary"] = chosen_cat
    user_data[user_id]["step"] = "secondary"

    await query.edit_message_text(f"Categoria primaria selezionata: {chosen_cat}\nInserisci categoria secondaria (testo libero):")


async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("In confirm_handler")
    
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "confirm_yes":
        data = user_data[user_id]
        sheet.append_row([data["name"], data["date"], data["price"], data["primary"], data["secondary"]])
        del user_data[user_id]
        await query.edit_message_text("Dati salvati su Google Sheets!")
        await start(query, context)
    elif query.data == "confirm_no":
        # fallback to manual mode
        user_data[user_id] = {"mode": "manual", "step": "name"}
        await query.edit_message_text("Passiamo al manuale. Inserisci il nome della spesa.")
    elif query.data == "manual_yes":
        data = user_data[user_id]
        sheet.append_row([data["name"], data["date"], data["price"], data["primary"], data["secondary"]])
        del user_data[user_id]
        await query.edit_message_text("Dati salvati su Google Sheets!")
        await start(query, context)
        del user_data[user_id]
    elif query.data == "manual_no":
        user_data[user_id] = {"mode": "manual", "step": "name"}
        await query.edit_message_text("Ok, reinserisci i dati manualmente.\nNome:")
        

# ----- Main -----
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(menu_handler, pattern="^(receipt|manual|change_month|set_month)"))
app.add_handler(CallbackQueryHandler(confirm_handler, pattern="^(confirm_yes|confirm_no|manual_yes|manual_no)$"))
app.add_handler(MessageHandler(filters.PHOTO, receipt_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manual_text_handler))
app.add_handler(CallbackQueryHandler(category_handler, pattern="^cat_"))

if __name__ == "__main__":
    print("Bot running...")
    app.run_polling()