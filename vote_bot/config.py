import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SITE_URL = os.getenv("SITE_URL")
LOGIN_URL = os.getenv("LOGIN_URL")
CANDIDATO = os.getenv("CANDIDATO")
_RAW_USER_EMAIL = os.getenv("USER_EMAIL") or ""
USER_EMAILS = [e.strip() for e in _RAW_USER_EMAIL.split(",") if e.strip()]
USER_PASSWORD = os.getenv("USER_PASSWORD")

DEBUG_PORT = 9222
PROFILE_DIR = "Trabalho"
MAIN_USER_DATA_DIR = r"C:\\chrome-debug"
COUNTER_FILE = Path("artifacts") / "count.txt"
MAX_INTERATIONS_NOW = 20
VOTAR_NOVAMENTE_RETRY = 3
KILL_CHROME_ON_RETRY = False

BRING_TO_FRONT = True

