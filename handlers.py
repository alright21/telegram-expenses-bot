from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sheets_helper import SheetsHelper
from config import Config
import logging

NAME, DAY, PRICE, PRIMARY_CATEGORY, SECONDARY_CATEGORY, CONFIRM = range(6)

PRIMARY_CATEGORIES = [
    "Housing", "Health", "Groceries", "Transport", "Out",
    "Travel", "Clothing", "Leisure", "Gifts", "Fees", "OtherExpenses"
]

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

sheets = SheetsHelper("creds.json")
logger = logging.getLogger(__name__)

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

async def scontrino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != Config.ALLOWED_USER_ID:
        logger.warning(f"Unauthorized access attempt by user ID {update.message.from_user.id}")
        return
    await update.message.reply_text("Hai selezionato /scontrino - Funzionalità in sviluppo.")

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