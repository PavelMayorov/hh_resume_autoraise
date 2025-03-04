import dataclasses
from datetime import datetime


@dataclasses.dataclass
class ToDictMixin:
    """Миксин для добавления метода сериализации в dict"""

    def to_dict(self) -> dict[str, str]:
        """Сериализует dataclass в dict"""
        return dataclasses.asdict(self)


@dataclasses.dataclass
class DBAccount(ToDictMixin):
    """DTO аккаунта пользователя HeadHunter"""

    login: str
    password: str


@dataclasses.dataclass
class DBResume(ToDictMixin):
    """DTO резюме пользователя HeadHunter"""

    resume_id: str
    title: str
    account_login: str
    last_raise: datetime | None = None
