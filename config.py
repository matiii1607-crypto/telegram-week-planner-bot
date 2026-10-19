import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno {name}. Copia .env.example a .env y completala."
        )
    return value


TELEGRAM_BOT_TOKEN = _required("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = _required("GEMINI_API_KEY")

_allowed_user = os.getenv("ALLOWED_TELEGRAM_USER_ID", "").strip()
ALLOWED_TELEGRAM_USER_ID = int(_allowed_user) if _allowed_user else None

TIMEZONE_NAME = os.getenv("TIMEZONE", "UTC")
TIMEZONE = ZoneInfo(TIMEZONE_NAME)

GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_DIR = os.path.join(BASE_DIR, "credentials")
GOOGLE_CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials.json")
GOOGLE_TOKEN_FILE = os.path.join(CREDENTIALS_DIR, "token.json")
