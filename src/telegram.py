import logging
from collections.abc import Iterable
from typing import (
    TYPE_CHECKING,
    Self,
)

from aiogram import (
    Bot,
    Dispatcher,
    types,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import (
    State,
    StatesGroup,
)
from aiogram.utils.keyboard import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from . import (
    errors,
    models,
    provider,
    utils,
)

if TYPE_CHECKING:
    from .database import Repository
    from .headhunter import HeadHunter
    from .service import Service


class AddAccountStates(StatesGroup):
    """Состояния добавления учетной записи"""

    enter_login = State()
    enter_password = State()


class AddResumeStates(StatesGroup):
    """Состояния добавления резюме для поднятия в поиске"""

    enter_login = State()
    enter_title = State()


class Telegram:
    """Абстракция для взаимодействия с сервисом Telegram"""

    def __init__(
        self,
        bot: Bot,
        dispatcher: Dispatcher,
        admin_id: int,
    ) -> None:
        self._bot = bot
        self._dp = dispatcher
        self._admin_id = admin_id
        self._logger = logging.getLogger("auto_raise.telegram")

    @classmethod
    def build(cls, service: "Service") -> Self:  # noqa: D102
        bot = Bot(service.config.bot_token)
        dispatcher = Dispatcher(
            database=service.database,
            headhunter=service.headhunter,
        )
        dispatcher.startup.register(service.on_startup)
        dispatcher.shutdown.register(service.on_shutdown)
        return cls(
            bot=bot,
            dispatcher=dispatcher,
            admin_id=service.config.tg_admin_id,
        )

    async def on_startup(self) -> None:  # noqa: D102
        await self.send_notification_to_admin("🟢 Бот запущен")
        self._logger.info("telegram started")

    async def on_shutdown(self) -> None:  # noqa: D102
        await self.send_notification_to_admin("🔴 Бот остановлен")
        self._logger.info("telegram stopped")

    async def start(self) -> None:
        """Запускает телеграм бота"""
        self._register_message_handlers()
        await self._dp.start_polling(
            self._bot,
            skip_updates=True,
        )

    def _register_message_handlers(self) -> None:
        """Устанавливает обработчиков сообщений и команд"""
        self._dp.message(Command("add_account"))(self._add_account_handler)
        self._dp.message(AddAccountStates.enter_login)(self._set_account_login)
        self._dp.message(AddAccountStates.enter_password)(self._set_account_password)

        self._dp.message(Command("add_resume"))(self._add_resume_handler)
        self._dp.message(AddResumeStates.enter_login)(self._set_resume_login)
        self._dp.message(AddResumeStates.enter_title)(self._set_resume_title)

    async def send_notification_to_admin(self, message: str) -> None:
        """Отправляет уведомление/сообщение администратору сервиса"""
        await self._bot.send_message(self._admin_id, message)

    def _is_admin(self, message: types.Message) -> bool:
        """Проверяет, является ли отправитель сообщения администратором сервиса"""
        return (message.from_user is not None
                and message.from_user.id == self._admin_id)

    def _build_keyboard(self, button_names: Iterable[str]) -> ReplyKeyboardMarkup:
        """Собирает клавиатуру для добавления в ответное сообщение"""
        buttons = [[KeyboardButton(text=button_name)] for button_name in button_names]
        buttons.append([KeyboardButton(text="Отмена")])
        return ReplyKeyboardMarkup(keyboard=buttons)

    async def _add_account_handler(
        self,
        message: types.Message,
        state: FSMContext,
    ) -> None:
        """Обработчик команды добавления нового аккаунта"""
        if not self._is_admin(message):
            return

        await state.set_state(AddAccountStates.enter_login)
        await message.reply(text="Введите логин (номер телефона) от учетной записи HeadHunter.")

    async def _set_account_login(
        self,
        message: types.Message,
        state: FSMContext,
    ) -> None:
        """Обработчик получения логина для добавления нового аккаунта"""
        login = utils.validate_phone_number(message.text)
        if login is None:
            await message.reply(text="Логин введен неверно. Попробуйте еще раз.")
            return

        await state.update_data(login=login)
        await state.set_state(AddAccountStates.enter_password)
        await message.reply(text="Введите пароль от учетной записи HeadHunter.")

    async def _set_account_password(
        self,
        message: types.Message,
        state: FSMContext,
        database: "Repository",
        headhunter: "HeadHunter",
    ) -> None:
        """Обработчик получения пароля для добавления нового аккаунта"""
        if message.text is None:
            await message.reply(text="Пароль введен неверно. Попробуйте еще раз")
            return

        state_data = await state.get_data()
        login: str = state_data["login"]
        await state.clear()

        account = models.Account(
            login=login,
            password=message.text,
        )

        try:
            await provider.add_account(
                db=database,
                hh=headhunter,
                account=account,
            )

        except errors.HHResponseError:
            await message.reply(text="Ошибка авторизации. Проверьте логин и пароль и попробуйте снова.")
            return

        except errors.AlreadyExistsError:
            await message.reply(text="Учетная запись уже существует.")
            return

        except Exception:
            self._logger.exception(f"failed to add {account=}")
            await message.reply(text="Произошла непредвиденная ошибка. Попробуйте повторить позже.")
            return

        self._logger.info(f"successful add {account=}")
        await message.reply(text="Учетная запись успешно добавлена.")

    async def _add_resume_handler(
        self,
        message: types.Message,
        state: FSMContext,
    ) -> None:
        """Обработчик команды добавления резюме для поднятия в поиске"""
        if not self._is_admin(message):
            return

        await state.set_state(AddResumeStates.enter_login)
        await message.reply(text="Введите логин (номер телефона) от учетной записи HeadHunter.")

    async def _set_resume_login(
        self,
        message: types.Message,
        state: FSMContext,
        database: "Repository",
        headhunter: "HeadHunter",
    ) -> None:
        """Обработчик получения логина для добавления резюме"""
        login = utils.validate_phone_number(message.text)
        if login is None:
            await message.reply(text="Логин введен неверно. Попробуйте еще раз.")
            return

        try:
            account = await provider.get_account_by_login(
                db=database,
                login=login,
            )

        except errors.NotExistsError:
            await message.reply(text="Учетная запись не найдена.")
            return

        except Exception:
            self._logger.exception(f"failed to get account by {login=}")
            await message.reply(text="Произошла непредвиденная ошибка. Попробуйте повторить позже.")
            return

        try:
            resumes = await provider.get_account_resumes(
                hh=headhunter,
                account=account,
            )

        except Exception:
            self._logger.exception(f"failed to get {account=} resumes")
            await message.reply(text="Произошла непредвиденная ошибка. Попробуйте повторить позже.")
            return

        self._logger.info(f"successful get {account=} {resumes=}")
        await state.update_data(
            account=account,
            resumes=resumes,
        )
        await state.set_state(AddResumeStates.enter_title)

        resume_titles = (resume.title for resume in resumes)
        await message.reply(
            text="Выберете резюме для добавления.",
            reply_markup=self._build_keyboard(resume_titles),
        )

    async def _set_resume_title(
        self,
        message: types.Message,
        state: FSMContext,
        database: "Repository",
    ) -> None:
        """Обработчик получения названия резюме для его добавления"""
        if message.text == "Отмена":
            await state.clear()
            await message.reply(
                text="Добавление резюме отменено.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return

        state_data = await state.get_data()
        account: models.Account = state_data["account"]
        resumes: list[models.Resume] = state_data["resumes"]

        resume: models.Resume | None = None
        for r in resumes:
            if r.title == message.text:
                resume = r
                break

        if resume is None:
            resume_titles = (resume.title for resume in resumes)
            await message.reply(
                text="Резюме не найдено. Попробуйте еще раз.",
                reply_markup=self._build_keyboard(resume_titles),
            )
            return

        try:
            await provider.add_resume(
                db=database,
                account=account,
                resume=resume,
            )

        except errors.AlreadyExistsError:
            self._logger.exception(f"already exists {resume=} to {account=}")
            await message.reply(text="Резюме уже существует.")
            return

        except Exception:
            self._logger.exception(f"failed to add {resume=} to {account=}")
            await message.reply(text="Произошла непредвиденная ошибка. Попробуйте повторить позже.")
            return

        self._logger.info(f"successful add {resume=} to {account=}")
        await state.clear()
        await message.reply(
            text="Резюме успешно добавлено для автоматического поднятия.",
            reply_markup=types.ReplyKeyboardRemove(),
        )
