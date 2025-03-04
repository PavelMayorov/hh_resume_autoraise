import logging
from abc import ABC, abstractmethod
from datetime import (
    UTC,
    datetime,
)
from typing import (
    TYPE_CHECKING,
    Self,
)

from sqlalchemy import (
    insert,
    select,
    update,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..errors import NotExistsError
from ..utils import handle_sqlalchemy_errors
from . import (
    dto,
    tables,
)

if TYPE_CHECKING:
    from ..service import Service


class Repository(ABC):
    """Интерфейс для реализации паттерна репозиторий"""

    @abstractmethod
    async def add_account(self, account: dto.DBAccount) -> None:
        """Добавление нового аккаунта в БД"""
        raise NotImplementedError

    @abstractmethod
    async def get_account_by_login(self, login: str) -> dto.DBAccount:
        """Получение аккаунта по логину"""
        raise NotImplementedError

    @abstractmethod
    async def add_resume(self, resume: dto.DBResume) -> None:
        """Добавление резюме в БД"""
        raise NotImplementedError

    @abstractmethod
    async def get_all_accounts_resumes(self) -> list[tuple[dto.DBAccount, dto.DBResume]]:
        """Получение всех аккаунтов и их резюме"""
        raise NotImplementedError

    @abstractmethod
    async def update_last_raise_resume(self, resume_id: str) -> None:
        """Обновление времени последнего поднятия резюме текущим временем"""
        raise NotImplementedError


class SQLiteDB(Repository):
    """Реализация репозитория для БД SQLite"""

    def __init__(
        self,
        engine: AsyncEngine,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._engine = engine
        self._session_maker = session_maker
        self._logger = logging.getLogger("auto_raise.database")

    @classmethod
    def build(cls, service: "Service") -> Self:  # noqa: D102
        engine = create_async_engine(service.config.db_url)
        session_maker = async_sessionmaker[AsyncSession](
            bind=engine,
            expire_on_commit=False,
        )
        return cls(
            engine=engine,
            session_maker=session_maker,
        )

    async def on_startup(self) -> None:
        """Создает таблицы в БД, если их нет"""
        async with self._engine.begin() as conn:
            await conn.run_sync(tables.Base.metadata.create_all)

        self._logger.debug("tables created successfully")

    @handle_sqlalchemy_errors
    async def add_account(self, account: dto.DBAccount) -> None:
        """Добавление нового аккаунта в БД"""
        query = (
            insert(tables.Account)
            .values(**account.to_dict())
        )
        async with self._session_maker() as session:
            await session.execute(query)
            await session.commit()

    @handle_sqlalchemy_errors
    async def get_account_by_login(self, login: str) -> dto.DBAccount:
        """Получение аккаунта по логину"""
        query = (
            select(tables.Account)
            .where(tables.Account.login == login)
        )
        async with self._session_maker() as session:
            result = await session.execute(query)

        row = result.scalar_one_or_none()
        if row is None:
            raise NotExistsError("account not found")

        return dto.DBAccount(
            login=row.login,
            password=row.password,
        )

    @handle_sqlalchemy_errors
    async def add_resume(self, resume: dto.DBResume) -> None:
        """Добавление резюме в БД"""
        query = insert(tables.Resume).values(**resume.to_dict())
        async with self._session_maker() as session:
            await session.execute(query)
            await session.commit()

    @handle_sqlalchemy_errors
    async def get_all_accounts_resumes(self) -> list[tuple[dto.DBAccount, dto.DBResume]]:
        """Получение всех аккаунтов и их резюме"""
        query = (
            select(tables.Account, tables.Resume)
            .join(tables.Resume, tables.Account.login == tables.Resume.account_login)
        )
        async with self._session_maker() as session:
            result = await session.execute(query)

        accounts_resumes: list[tuple[dto.DBAccount, dto.DBResume]] = []
        for account_row, resume_row in result.all():
            account = dto.DBAccount(
                login=account_row.login,
                password=account_row.password,
            )
            resume = dto.DBResume(
                resume_id=resume_row.resume_id,
                title=resume_row.title,
                account_login=resume_row.account_login,
                last_raise=resume_row.last_raise.replace(tzinfo=UTC) if resume_row.last_raise else None,
            )
            accounts_resumes.append((account, resume))

        return accounts_resumes

    @handle_sqlalchemy_errors
    async def update_last_raise_resume(self, resume_id: str) -> None:
        """Обновление времени последнего поднятия резюме текущим временем"""
        query = (
            update(tables.Resume)
            .values(last_raise=datetime.now(UTC))
            .where(tables.Resume.resume_id == resume_id)
        )
        async with self._session_maker() as session:
            await session.execute(query)
            await session.commit()
