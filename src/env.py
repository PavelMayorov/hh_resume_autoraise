import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Конфигурация из переменных окружения"""

    bot_token: str = os.getenv("BOT_TOKEN") or ""
    tg_admin_id: int = int(os.getenv("TG_ADMIN_ID")) # type: ignore[arg-type]

    db_url: str = os.getenv("DB_URL") or ""
    resume_check_frequency: timedelta = timedelta(minutes=int(os.getenv("RESUME_CHECK_FREQUENCY"))) # type: ignore[arg-type]
