import asyncio
import logging
from typing import (
    TYPE_CHECKING,
    Self,
)

from fake_useragent import UserAgent
import httpx
from bs4 import BeautifulSoup

from . import (
    errors,
    models,
)
from .constants import (
    HHHost,
    HHPaths,
)

if TYPE_CHECKING:
    from .service import Service


class HeadHunter:
    """Абстракция для взаимодействия с сервисом HeadHunter"""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        user_agent: UserAgent,
    ) -> None:
        self._http_client = http_client
        self._user_agent = user_agent
        self._login_to_tokens: dict[str, models.HHAuthTokens] = {}
        self._anon_tokens: models.HHAuthTokens | None = None
        self._tokens_lock = asyncio.Lock()
        self._logger = logging.getLogger("auto_raise.headhunter")

    @classmethod
    def build(cls, service: "Service") -> Self:  # noqa: D102
        http_client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=5,
        )
        user_agent = UserAgent()
        return cls(
            http_client=http_client,
            user_agent=user_agent,
        )

    @staticmethod
    def _build_headers(user_tokens: models.HHAuthTokens, user_agent: str) -> dict[str, str]:
        """Собирает и возвращает заголовки запроса"""
        return {
            "cookie": f"_xsrf={user_tokens.xsrf_token}; hhtoken={user_tokens.hh_token};",
            "user-agent": user_agent,
            "x-xsrftoken": user_tokens.xsrf_token,
        }

    @staticmethod
    def _build_auth_data(account: models.Account, xsrf_token: str) -> dict[str, str]:
        """Собирает и возвращает данные для запроса авторизации"""
        return {
            "_xsrf": xsrf_token,
            "backUrl": "https://hh.ru/",
            "failUrl": "/account/login",
            "remember": "yes",
            "username": account.login,
            "password": account.password,
            "isBot": "false",
        }

    async def _get_anon_auth_tokens(self) -> models.HHAuthTokens:
        """Получение анонимных токенов авторизации"""
        url = str(HHHost)
        response = await self._http_client.request(
            method="HEAD",
            url=url,
            headers={"user-agent": self._user_agent.random},
        )
        response.raise_for_status()

        xsrf_token = response.cookies.get("_xsrf")
        hh_token = response.cookies.get("hhtoken")
        if xsrf_token is not None and hh_token is not None:
            self._anon_tokens = models.HHAuthTokens(
                xsrf_token=xsrf_token,
                hh_token=hh_token,
            )

        if self._anon_tokens is None:
            raise errors.HeadHunterError("anon auth token missing")

        return self._anon_tokens

    async def _authorize_account(self, account: models.Account) -> models.HHAuthTokens:
        """Авторизация аккаунта (получение токенов авторизации)"""
        url = str(HHHost / HHPaths.LOGIN)
        anon_tokens = await self._get_anon_auth_tokens()
        headers = self._build_headers(
            user_tokens=anon_tokens,
            user_agent=self._user_agent.random,
        )
        auth_data = self._build_auth_data(
            account=account,
            xsrf_token=anon_tokens.xsrf_token,
        )

        response = await self._http_client.request(
            method="POST",
            url=url,
            headers=headers,
            data=auth_data,
        )
        response.raise_for_status()

        response_model = models.HHAuthResponse.model_validate_json(response.content)
        if response_model.login_error is not None:
            raise errors.HHResponseError("authorization failed")

        return models.HHAuthTokens(
            xsrf_token=response.cookies["_xsrf"],
            hh_token=response.cookies["hhtoken"],
        )

    async def get_account_auth_tokens(self, account: models.Account) -> models.HHAuthTokens:
        """Возвращает токены авторизации из маппинга или запрашивает новые"""
        async with self._tokens_lock:
            if self._login_to_tokens.get(account.login) is None:
                self._login_to_tokens[account.login] = await self._authorize_account(account)

            return self._login_to_tokens[account.login]

    async def _reset_account_auth_tokens(self, account: models.Account) -> None:
        """Удаляет токены авторизации из маппинга"""
        async with self._tokens_lock:
            self._login_to_tokens.pop(account.login)

    @staticmethod
    def _extract_resumes_from_page(page: str) -> list[models.Resume]:
        """Парсит страницу с резюме и извлекает их названия и идентификаторы"""
        soup = BeautifulSoup(page, "lxml")
        resumes_div = soup.select('div[data-qa="resume"]')
        resumes = []
        for resume_div in resumes_div:
            title = resume_div.get("data-qa-title")
            if not isinstance(title, str):
                continue

            link_tag = resume_div.select_one("a[href]")
            if link_tag is None:
                continue

            link = link_tag.get("href")
            if not isinstance(link, str):
                continue

            resume_id = link.split("/")[-1].split("?")[0]
            resume = models.Resume(
                resume_id=resume_id,
                title=title,
            )
            resumes.append(resume)
        return resumes

    async def get_resumes(self, account: models.Account) -> list[models.Resume]:
        """Запрашивает все резюме пользователя"""
        url = str(HHHost / HHPaths.GET_RESUMES)
        tokens = await self.get_account_auth_tokens(account)
        headers = self._build_headers(
            user_tokens=tokens,
            user_agent=self._user_agent.random,
        )

        response = await self._http_client.request(
            method="GET",
            url=url,
            headers=headers,
        )
        response.raise_for_status()

        return self._extract_resumes_from_page(response.text)

    async def raise_resume(
        self,
        account: models.Account,
        resume: models.Resume,
    ) -> None:
        """Отправляет запрос на поднятие резюме в поиске"""
        url = str(HHHost / HHPaths.RAISE_RESUME)
        url = "https://hh.ru/applicant/resumes/touch"
        tokens = await self.get_account_auth_tokens(account)
        headers = self._build_headers(
            user_tokens=tokens,
            user_agent=self._user_agent.random,
        )
        raise_data = {
            "resume": resume.resume_id,
            "undirectable": "true",
        }

        response = await self._http_client.request(
            method="POST",
            url=url,
            headers=headers,
            data=raise_data,
        )
        if response.status_code == httpx.codes.FORBIDDEN:
            await self._reset_account_auth_tokens(account)

        response.raise_for_status()
