import asyncio
import logging
from contextlib import suppress
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from typing import (
    TYPE_CHECKING,
    NoReturn,
    Self,
)

from . import (
    constants,
    errors,
    provider,
)

if TYPE_CHECKING:
    from .database import Repository
    from .headhunter import HeadHunter
    from .service import Service
    from .telegram import Telegram


class Scheduler:
    """Планировщик для поднятия резюме на платформе HeadHunter"""

    def __init__(
        self,
        database: "Repository",
        headhunter: "HeadHunter",
        telegram: "Telegram",
        resume_check_frequency: timedelta,
    ) -> None:
        self._database = database
        self._headhunter = headhunter
        self._telegram = telegram
        self._resume_check_frequency = resume_check_frequency
        self._logger = logging.getLogger("auto_raise.scheduler")
        self._raise_resumes_task: asyncio.Task | None = None

    @classmethod
    def build(cls, service: "Service") -> Self:  # noqa: D102
        return cls(
            database=service.database,
            headhunter=service.headhunter,
            telegram=service.telegram,
            resume_check_frequency=service.config.scheduler.resume_check_frequency,
        )

    async def on_startup(self) -> None:  # noqa: D102
        self._raise_resumes_task = asyncio.create_task(self._raise_resumes())
        self._logger.info("scheduler started")

    async def on_shutdown(self) -> None:  # noqa: D102
        if self._raise_resumes_task is None:
            return

        self._raise_resumes_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._raise_resumes_task

        self._logger.info("scheduler stopped")

    async def _raise_resumes(self) -> NoReturn:
        """С заданной частотой проверяет и поднимает резюме в поиске, уведомляя администратора об успехе"""
        while True:
            await asyncio.sleep(self._resume_check_frequency.total_seconds())

            try:
                accounts_resumes = await provider.get_all_accounts_resumes(self._database)

            except errors.DBError:
                self._logger.exception("failed to get all accounts resumes from DB")
                continue

            for account, resume in accounts_resumes:
                if (resume.last_raise is not None
                        and datetime.now(UTC) - resume.last_raise < constants.RE_RISING_PERIOD):
                    continue

                try:
                    await self._headhunter.raise_resume(account, resume)
                    await self._database.update_last_raise_resume(resume.resume_id)

                except Exception:
                    self._logger.exception(f"failed to raise {account=} {resume=}")
                    await self._telegram.send_notification_to_admin(
                        message=f"❗️ При попытке поднятия резюме {resume.title} в поиске возникла ошибка.",
                    )
                    continue

                await self._telegram.send_notification_to_admin(
                    message=f"🔝 Резюме {resume.title} успешно поднято в поиске.",
                )
                self._logger.info(f"successful raise {account=} {resume=}")
