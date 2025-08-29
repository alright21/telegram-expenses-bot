import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env file if present

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    SHEET_ID = os.getenv("SHEET_ID")
    ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
    LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "bot.log")

    @classmethod
    def validate(cls):
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN is missing. Add it to your environment variables.")
        if not cls.SHEET_ID:
            raise ValueError("SHEET_ID is missing. Add it to your environment variables.")
        if cls.ALLOWED_USER_ID == 0:
            raise ValueError("ALLOWED_USER_ID is missing or invalid. Add it to your environment variables.")
