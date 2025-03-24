import os
from datetime import timedelta
from typing import (
    Annotated,
    Self,
)

import yaml
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
    admin_id: Annotated[
        int,
        Field(description="ID администратора этого сервиса в телеграм"),
    ]


class DataBase(BaseModel):
    """Конфигурация базы данных"""

    db_path: Annotated[
        str,
        Field(description="Путь до файла базы данных SQLite"),
    ] = "db/autoraise.db"


class Scheduler(BaseModel):
    """Конфигурация планировщика поднятия резюме"""

    resume_check_frequency: Annotated[
        timedelta,
        Field(description="Частота проверки возможности поднятия резюме"),
    ] = timedelta(minutes=5)


class ServiceConfig(BaseModel):
    """Конфигурация сервиса"""

    telegram: Telegram
    database: DataBase
    scheduler: Scheduler

    @classmethod
    def build(cls, path: str | None = None) -> Self:
        """Собирает модели конфигурации сервиса из файла"""
        if not path:
            path = os.path.join("config.d", "config.yml")
        with open(path, encoding="utf8") as f:
            parsed_data = yaml.safe_load(f.read())
        return cls.model_validate(parsed_data)
