from datetime import timedelta
from typing import Annotated

from pydantic import (
    BaseModel,
    Field,
)


class Telegram(BaseModel):
    """Конфигурация telegram"""

    bot_token: Annotated[
        str,
        Field(description="Токен телеграм бота"),
    ]
    tg_admin_id: Annotated[
        int,
        Field(description="ID администратора этого сервиса в телеграм"),
    ]


class DataBase(BaseModel):
    """Конфигурация базы данных"""

    db_url: Annotated[
        str,
        Field(description="URL SQLite базы данных"),
    ] = "sqlite+aiosqlite:///src/database/autoraise.db"


class Scheduler(BaseModel):
    """Конфигурация планировщика"""

    resume_check_frequency: Annotated[
        timedelta,
        Field(description="Частота проверки возможности поднятия резюме"),
    ] = timedelta(minutes=5)

class Config(BaseModel):
    """Конфигурация сервиса"""

    telegram: Telegram
    database: DataBase
    scheduler: Scheduler
