import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    return int(raw)


def _apply_instance_template(value: str | None, instance_id: int) -> str | None:
    if not value:
        return value
    if "{id}" not in value:
        return value
    return value.format(id=instance_id)


SITE_URL = os.getenv("SITE_URL")
LOGIN_URL = os.getenv("LOGIN_URL")
CANDIDATO = os.getenv("CANDIDATO")
_RAW_USER_EMAIL = os.getenv("USER_EMAIL") or ""
USER_EMAILS = [e.strip() for e in _RAW_USER_EMAIL.split(",") if e.strip()]
USER_PASSWORD = os.getenv("USER_PASSWORD")

INSTANCE_ID = _int_env("INSTANCE_ID", 0)

# Quando rodar multiplas instancias, cada instancia usa um "par" de emails:
# - INSTANCE_ID=1 -> emails 1 e 2
# - INSTANCE_ID=2 -> emails 3 e 4
# - INSTANCE_ID=3 -> emails 5 e 6
if INSTANCE_ID > 0:
    start = (INSTANCE_ID - 1) * 2
    selected_emails = USER_EMAILS[start : start + 2]
    if not selected_emails:
        raise RuntimeError(
            f"INSTANCE_ID={INSTANCE_ID} requer USER_EMAIL com pelo menos {start + 1} email(s). "
            f"Recebido: {len(USER_EMAILS)}."
        )
    print(f"❌✅❌✅ Instância {INSTANCE_ID} usando emails: {selected_emails}")
    USER_EMAILS = selected_emails

DEBUG_PORT_BASE = _int_env("DEBUG_PORT_BASE", 9222)
DEBUG_PORT = _int_env("DEBUG_PORT", 0) or (DEBUG_PORT_BASE + (INSTANCE_ID - 1 if INSTANCE_ID > 0 else 0))

PROFILE_DIR = _apply_instance_template(os.getenv("PROFILE_DIR") or "Trabalho", INSTANCE_ID) or "Trabalho"

_raw_user_data_dir = os.getenv("MAIN_USER_DATA_DIR") or r"C:\\chrome-debug"
_templated_user_data_dir = _apply_instance_template(_raw_user_data_dir, INSTANCE_ID) or _raw_user_data_dir
if INSTANCE_ID > 0 and os.getenv("MAIN_USER_DATA_DIR") is None and "{id}" not in _raw_user_data_dir:
    MAIN_USER_DATA_DIR = f"{_templated_user_data_dir}-{INSTANCE_ID}"
else:
    MAIN_USER_DATA_DIR = _templated_user_data_dir

_raw_artifacts_dir = os.getenv("ARTIFACTS_DIR") or "artifacts"
_templated_artifacts_dir = _apply_instance_template(_raw_artifacts_dir, INSTANCE_ID) or _raw_artifacts_dir
if INSTANCE_ID > 0 and os.getenv("ARTIFACTS_DIR") is None and "{id}" not in _raw_artifacts_dir:
    ARTIFACTS_DIR = Path(_templated_artifacts_dir) / f"instance_{INSTANCE_ID}"
else:
    ARTIFACTS_DIR = Path(_templated_artifacts_dir)

COUNTER_FILE = ARTIFACTS_DIR / "count.txt"

MAX_INTERATIONS_NOW = _int_env("MAX_INTERATIONS_NOW", 20)
VOTAR_NOVAMENTE_RETRY = 3
KILL_CHROME_ON_RETRY = False

_bring_to_front = (os.getenv("BRING_TO_FRONT") or "").strip().lower()
BRING_TO_FRONT = True
