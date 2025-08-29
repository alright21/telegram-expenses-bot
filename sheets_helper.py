import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import Config

class SheetsHelper:
    def __init__(self, creds_file: str):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(Config.SHEET_ID)
        self.month = "Sep"
        self.worksheet = self.sheet.worksheet(self.month)

    def append_expense(self, expense: dict):
        # Expense is expected to be a dict with fixed keys
        row = [
            expense.get("expense_name"),
            expense.get("day"),
            expense.get("price"),
            expense.get("primary_category"),
            expense.get("secondary_category")
        ]
        self.worksheet.append_row(row, value_input_option="USER_ENTERED")
    
    def set_month(self, month: str):
        self.month = month
        self.worksheet = self.sheet.worksheet(month)
