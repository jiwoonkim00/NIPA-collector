import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

SHEET_ID = os.getenv("SHEET_ID")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials.json")

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds = Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=scopes,
)

client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SHEET_ID)

print("스프레드시트 제목:", spreadsheet.title)
print("스프레드시트 ID:", SHEET_ID)
print("스프레드시트 URL:", spreadsheet.url)
print("\n워크시트 목록:")

for ws in spreadsheet.worksheets():
    values = ws.get_all_values()
    print(f"- {ws.title}: {len(values)}행 x {ws.col_count}열")
    if len(values) > 0:
        print("  첫 행:", values[0])
    if len(values) > 1:
        print("  둘째 행:", values[1][:5])