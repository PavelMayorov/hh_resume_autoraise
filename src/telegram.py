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
    constants,
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


class DeleteResumeStates(StatesGroup):
    """Состояния удаления резюме"""

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
        bot = Bot(token=service.config.telegram.bot_token)
        dispatcher = Dispatcher(
            database=service.database,
            headhunter=service.headhunter,
        )
        dispatcher.startup.register(service.on_startup)
        dispatcher.shutdown.register(service.on_shutdown)
        return cls(
            bot=bot,
            dispatcher=dispatcher,
            admin_id=service.config.telegram.admin_id,
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
        self._dp.message(AddResumeStates.enter_login)(self._enter_login_to_add_resume)
        self._dp.message(AddResumeStates.enter_title)(self._enter_title_to_add_resume)

        self._dp.message(Command("del_resume"))(self._add_resume_handler)
        self._dp.message(DeleteResumeStates.enter_login)(self._enter_login_to_delete_resume)
        self._dp.message(DeleteResumeStates.enter_title)(self._enter_title_to_delete_resume)

        self._dp.message(Command("get_resumes"))(self._get_resumes_handler)

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

    async def _enter_login_to_add_resume(
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
            resumes = await provider.get_account_resumes_from_hh(
                hh=headhunter,
                account=account,
            )

        except Exception:
            self._logger.exception(f"failed to get {account=} resumes from hh")
            await message.reply(text="Произошла непредвиденная ошибка. Попробуйте повторить позже.")
            await state.clear()
            return

        self._logger.info(f"successful get {account=} {resumes=} from hh")
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

    async def _enter_title_to_add_resume(
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
            await provider.add_account_resume(
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
            await state.clear()
            return

        self._logger.info(f"successful add {resume=} to {account=}")
        await state.clear()
        await message.reply(
            text="Резюме успешно добавлено для автоматического поднятия.",
            reply_markup=types.ReplyKeyboardRemove(),
        )

    async def _enter_login_to_delete_resume(
        self,
        message: types.Message,
        state: FSMContext,
        database: "Repository",
    ) -> None:
        """Обработчик получения логина для удаления резюме"""
        login = utils.validate_phone_number(message.text)
        if login is None:
            await message.reply(text="Логин введен неверно. Попробуйте еще раз.")
            return

        try:
            resumes = await provider.get_account_resumes_from_db(
                db=database,
                login=login,
            )

        except Exception:
            self._logger.exception(f"failed to get account resumes by {login=} from db")
            await message.reply(text="Произошла непредвиденная ошибка. Попробуйте повторить позже.")
            return

        if not resumes:
            await message.reply(text="Для выбранного аккаунта нет добавленных резюме.")
            return

        await state.update_data(
            login=login,
            resumes=resumes,
        )
        await state.set_state(DeleteResumeStates.enter_title)

        resume_titles = (resume.title for resume in resumes)
        await message.reply(
            text="Выберете резюме для удаления.",
            reply_markup=self._build_keyboard(resume_titles),
        )

    async def _enter_title_to_delete_resume(
        self,
        message: types.Message,
        state: FSMContext,
        database: "Repository",
    ) -> None:
        """Обработчик получения названия резюме для его удаления"""
        if message.text == "Отмена":
            await state.clear()
            await message.reply(
                text="Удаление резюме отменено.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return

        state_data = await state.get_data()
        resumes: list[models.Resume] = state_data["resumes"]
        login: str = state_data["login"]

        resume: models.Resume | None = None
        for r in resumes:
            if r.title == message.text:
                resume = r
                break

        if resume is None:
            resume_titles = (resume.title for resume in resumes)
            await message.reply(
                text="Резюме не найдено. Попробуйте ввести название еще раз.",
                reply_markup=self._build_keyboard(resume_titles),
            )
            return

        try:
            await provider.delete_account_resume(
                db=database,
                login=login,
                title=resume.title,
            )

        except Exception:
            self._logger.exception(f"failed to delete {resume=}")
            await message.reply(text="Произошла непредвиденная ошибка. Попробуйте повторить позже.")
            await state.clear()
            return

        self._logger.info(f"successful delete {resume=}")
        await state.clear()
        await message.reply(
            text="Резюме успешно удалено из автоматического поднятия.",
            reply_markup=types.ReplyKeyboardRemove(),
        )

    async def _get_resumes_handler(
        self,
        message: types.Message,
        state: FSMContext,
        database: "Repository",
    ) -> None:
        """Обработчик запроса всех резюме"""
        if not self._is_admin(message):
            return

        try:
            accounts_resumes = await provider.get_all_accounts_resumes(database)

        except Exception:
            self._logger.exception("failed to get resumes")
            await message.reply(text="Произошла непредвиденная ошибка. Попробуйте повторить позже.")
            await state.clear()
            return

        if len(accounts_resumes) == 0:
            await message.reply(text="Ни одно резюме еще не добавлено.")
            return

        for i in range(0, len(accounts_resumes), constants.GET_RESUMES_PAGINATION_SIZE):
            text_paths = []
            for account, resume in accounts_resumes[i:i+constants.GET_RESUMES_PAGINATION_SIZE]:
                text_paths.append(f"Аккаунт {account.login} резюме {resume.title}")
                await message.reply(text="\n".join(text_paths))
