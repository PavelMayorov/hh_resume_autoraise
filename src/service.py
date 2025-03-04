import asyncio
import logging

from .database import SQLiteDB
from .env import Config
from .headhunter import HeadHunter
from .scheduler import Scheduler
from .telegram import Telegram


class Service:
    """Основной класс сервиса"""

    def __init__(self) -> None:
        self.config = Config()
        self.headhunter = HeadHunter.build(self)
        self.database = SQLiteDB.build(self)
        self.telegram = Telegram.build(self)
        self.scheduler = Scheduler.build(self)

    async def on_startup(self) -> None:  # noqa: D102
        await self.database.on_startup()
        await self.telegram.on_startup()
        await self.scheduler.on_startup()

    async def on_shutdown(self) -> None:  # noqa: D102
        await self.scheduler.on_shutdown()
        await self.telegram.on_shutdown()

    @staticmethod
    def setup_logger() -> logging.Logger:
        """Создает основного логгера интеграции и настраивает его"""
        logger = logging.getLogger("auto_raise")
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def run(self) -> None:
        """Точка входа сервиса"""
        logger = self.setup_logger()
        logger.info("starting service")
        try:
            asyncio.run(self.telegram.start())
        finally:
            logger.info("stopping service")
