from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets_helper import SheetsHelper
from config import Config
import logging
import json
from google import genai
from pydantic import BaseModel

NAME, DAY, PRICE, PRIMARY_CATEGORY, SECONDARY_CATEGORY, CONFIRM = range(6)

PHOTO, PHOTO_RESULT = range(100, 102)

PRIMARY_CATEGORIES = [
    "Housing", "Health", "Groceries", "Transport", "Out",
    "Travel", "Clothing", "Leisure", "Gifts", "Fees", "OtherExpenses"
]

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

class ExpenseData(BaseModel):
    name: str
    price: float
    date: str
    primary_category: str
    secondary_category: str

sheets = SheetsHelper("creds.json")
logger = logging.getLogger(__name__)
client = genai.Client(api_key=Config.GEMINI_API_KEY)


PROMPT = """
You are an assistant that extracts receipt data from a photo.
Return ONLY a JSON object with exactly these fields (no extra text, no explanations, no code blocks):
{
  "name": "<expense name>",
  "price": <numeric price, no currency symbol>,
  "date": "<day as two digits, e.g. \"01\", \"02\", ...>",
  "primary_category": "<one of [Housing, Health, Groceries, Transport, Out, Travel, Clothing, Leisure, Gifts, Fees, OtherExpenses]>",
  "secondary_category": "<free text – specific subcategory>"
}

The are some rules you must follow:
- The name must be as short as possible. For example, for Esselunga receipts, you use "Esselunga" as name.
- The price must be a number only, without any currency symbol. Use dot as decimal separator.
- If the receipt shows that the amount was paid also with BUONO PASTO (or similar), just extract the amount paid in cash/card.
- The date must be only the day of the month, as two digits (e.g. "01", "02", ..., "31"). The date in the receipt is in format DD/MM/YYYY.
- The primary_category must be one of the predefined categories.
- When I go eating out, I want to categorize the expense as "Out", not "Groceries" or "Leisure".
- The secondary_category can be any text, and should be more specific than the primary_category. But when I eat out, I want to use Breakfast, Lunch, Dinner, Snack, Coffee, Bar as secondary categories.
- When I buy groceries, I want to use Supermarket as secondary category.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != Config.ALLOWED_USER_ID:
        logger.warning(f"Unauthorized access attempt by user ID {update.message.from_user.id}")
        return
    await update.message.reply_text(f"Benvenuto! Usa /help per vedere i comandi disponibili. Mese corrente: {sheets.month}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != Config.ALLOWED_USER_ID:
        logger.warning(f"Unauthorized access attempt by user ID {update.message.from_user.id}")
        return
    await update.message.reply_text("Comandi disponibili:\n/scontrino - Carica foto dello scontrino\n/manuale - Inserimento manuale\n/cambia_mese - Cambia il mese di riferimento")

async def scontrino_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != Config.ALLOWED_USER_ID:
        logger.warning(f"Unauthorized access attempt by user ID {update.message.from_user.id}")
        return
    await update.message.reply_text("Invia la foto dello scontrino.")
    return PHOTO

async def scontrino_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    file_path = "./receipt.jpg"
    await photo_file.download_to_drive(file_path)
    await update.message.reply_text("Foto ricevuta. Elaborazione in corso...")

    try:
        # Prepare the multimodal request
        uploaded_image = client.files.upload(file=file_path)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                PROMPT,uploaded_image
            ],
            config={
                "response_mime_type": "application/json",
                "response_schema": ExpenseData
            }
        )
        text = response.text.strip()
        await update.message.reply_text("Elaborazione completata.")

        json_data = json.loads(text)

        context.user_data["expense_name"] = json_data.get("name", "").strip()
        context.user_data["day"] = json_data.get("date", "").strip()
        context.user_data["price"] = float(json_data.get("price", 0))
        context.user_data["primary_category"] = json_data.get("primary_category", "").strip()
        context.user_data["secondary_category"] = json_data.get("secondary_category", "").strip()

        data = context.user_data
        review_text = (
            f"**Riepilogo spesa:**\n"
            f"- Nome: {data['expense_name']}\n"
            f"- Giorno: {data['day']}\n"
            f"- Prezzo: {data['price']:.2f}\n"
            f"- Categoria principale: {data['primary_category']}\n"
            f"- Categoria secondaria: {data['secondary_category']}\n\n"
            f"Confermi?"
        )

        buttons = [
            [
                InlineKeyboardButton("Sì", callback_data="yes"),
                InlineKeyboardButton("No", callback_data="no")
            ]
        ]
        await update.message.reply_text(
            review_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except json.JSONDecodeError:
        reply = f"Non è stato possibile estrarre i dati in formato JSON. Response was:\n\n{text}"
        await update.message.reply_text(reply)
        return ConversationHandler.END
    except Exception as e:
        reply = f"Errore nell'analisi dello scontrino: {e}"
        await update.message.reply_text(reply)
        return ConversationHandler.END

    return CONFIRM

# Conversation Handlers for "manuale" command

async def manuale_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != Config.ALLOWED_USER_ID:
        logger.warning(f"Unauthorized access attempt by user ID {update.message.from_user.id}")
        return
    await update.message.reply_text("Inserisci il *nome* della spesa:", parse_mode="Markdown")
    return NAME

async def manuale_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["expense_name"] = update.message.text.strip()
    await update.message.reply_text("Inserisci il *giorno* (DD):", parse_mode="Markdown")
    return DAY

async def manuale_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = update.message.text.strip()
    if not day.isdigit() or not (1 <= int(day) <= 31):
        await update.message.reply_text("Giorno non valido. Inserisci un numero da 1 a 31.")
        return DAY
    context.user_data["day"] = day
    await update.message.reply_text("Inserisci il *prezzo*:", parse_mode="Markdown")
    return PRICE

async def manuale_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price_text = update.message.text.strip().replace(",", ".")
    try:
        price = float(price_text)
    except ValueError:
        await update.message.reply_text("Prezzo non valido. Inserisci un numero.")
        return PRICE
    context.user_data["price"] = price

    # Show category buttons
    buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in PRIMARY_CATEGORIES]
    await update.message.reply_text(
        "Seleziona la *categoria principale*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return PRIMARY_CATEGORY

async def manuale_primary_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["primary_category"] = query.data
    await query.edit_message_text("Inserisci la *categoria secondaria* (testo libero):", parse_mode="Markdown")
    return SECONDARY_CATEGORY

async def manuale_secondary_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["secondary_category"] = update.message.text.strip()

    # Show summary and ask confirmation
    data = context.user_data
    review_text = (
        f"**Riepilogo spesa:**\n"
        f"- Nome: {data['expense_name']}\n"
        f"- Giorno: {data['day']}\n"
        f"- Prezzo: {data['price']:.2f}\n"
        f"- Categoria principale: {data['primary_category']}\n"
        f"- Categoria secondaria: {data['secondary_category']}\n\n"
        f"Confermi?"
    )

    buttons = [
        [
            InlineKeyboardButton("Sì", callback_data="yes"),
            InlineKeyboardButton("No", callback_data="no")
        ]
    ]
    await update.message.reply_text(
        review_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return CONFIRM

async def manuale_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "yes":
        data = context.user_data
        # Save to Google Sheets
        sheets.append_expense(data)
        await query.edit_message_text("Spesa salvata con successo! ✅")
    else:
        await query.edit_message_text("Operazione annullata. ❌")
    return ConversationHandler.END

async def manuale_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != Config.ALLOWED_USER_ID:
        logger.warning(f"Unauthorized access attempt by user ID {update.message.from_user.id}")
        return
    await update.message.reply_text("Operazione annullata.")
    return ConversationHandler.END

async def cambia_mese(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != Config.ALLOWED_USER_ID:
        logger.warning(f"Unauthorized access attempt by user ID {update.message.from_user.id}")
        return
    buttons = [
        [InlineKeyboardButton(month, callback_data=f"set_month:{month}")]
        for month in MONTHS
    ]
    await update.message.reply_text(
        "Seleziona il mese:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def cambia_mese_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Extract the month from callback data
    _, month = query.data.split(":", 1)

    sheets.set_month(month)

    await query.edit_message_text(f"Mese impostato su {month} ✅")