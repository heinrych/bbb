import random
from .config import USER_EMAILS

def pick_user_email() -> str:
    if not USER_EMAILS:
        raise RuntimeError("USER_EMAIL nao configurado (defina no .env; pode ser separado por virgula).")
    return random.choice(USER_EMAILS)

