from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class Base(DeclarativeBase):
    """Базовый класс для таблиц в БД"""


class Account(Base):
    """Данные аккаунтов"""

    __tablename__ = "account"

    login: Mapped[str] = mapped_column(String, primary_key=True)
    password: Mapped[str] = mapped_column(String, nullable=False)


class Resume(Base):
    """Данные резюме пользователей"""

    __tablename__ = "resume"

    resume_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    last_raise: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    account_login: Mapped[str] = mapped_column(
        String,
        ForeignKey(column="account.login", ondelete="cascade"),
        nullable=False,
    )
