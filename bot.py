import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from config import Config
import handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(Config.LOG_FILE_PATH),  # file log
        logging.StreamHandler()                                # console log
    ]
)

def main():
    # Validate config
    Config.validate()

    # Create application
    application = ApplicationBuilder().token(Config.TELEGRAM_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))

    application.add_handler(CommandHandler("scontrino", handlers.scontrino))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("manuale", handlers.manuale_start)],
        states={
            handlers.NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.manuale_name)],
            handlers.DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.manuale_day)],
            handlers.PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.manuale_price)],
            handlers.PRIMARY_CATEGORY: [CallbackQueryHandler(handlers.manuale_primary_category)],
            handlers.SECONDARY_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.manuale_secondary_category)],
            handlers.CONFIRM: [CallbackQueryHandler(handlers.manuale_confirm)]
        },
        fallbacks=[CommandHandler("cancel", handlers.manuale_cancel)],
    )
    application.add_handler(conv_handler)

    application.add_handler(CommandHandler("cambia_mese", handlers.cambia_mese))
    application.add_handler(CallbackQueryHandler(handlers.cambia_mese_callback, pattern="^set_month:"))

    # Run bot
    application.run_polling()

if __name__ == "__main__":
    main()

