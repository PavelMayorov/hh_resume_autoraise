from datetime import datetime
from typing import Any, Self

from pydantic import (
    BaseModel,
    Field,
)

from .database import dto


class Account(BaseModel):
    """Модель аккаунта пользователя HeadHunter"""

    login: str
    password: str

    @classmethod
    def from_db(cls, db_account: dto.DBAccount) -> Self:
        """Создает модель из DTO"""
        return cls(
            login=db_account.login,
            password=db_account.password,
        )


class Resume(BaseModel):
    """Модель резюме пользователя HeadHunter"""

    resume_id: str
    title: str
    last_raise: datetime | None = None

    @classmethod
    def from_db(cls, db_resume: dto.DBResume) -> Self:
        """Создает модель из DTO"""
        return cls(
            resume_id=db_resume.resume_id,
            title=db_resume.title,
            last_raise=db_resume.last_raise,
        )


class HHAuthTokens(BaseModel):
    """Модель токенов авторизации аккаунта HeadHunter"""

    xsrf_token: str
    hh_token: str


class Recaptcha(BaseModel):  # noqa: D101
    is_bot: bool = Field(alias="isBot")
    site_key: str = Field(alias="siteKey")


class HHCaptcha(BaseModel):  # noqa: D101
    is_bot: bool = Field(alias="isBot")
    captcha_error: Any = Field(alias="captchaError", default=None)
    captcha_key: Any = Field(alias="captchaKey", default=None)


class AuthError(BaseModel):  # noqa: D101
    code: str
    trl: str


class HHAuthResponse(BaseModel):
    """Модель ответа сервиса HeadHunter на запрос авторизации"""

    recaptcha: Recaptcha
    hhcaptcha: HHCaptcha
    redirect_url: str | None = Field(alias="redirectUrl", default=None)
    show2_fa_popup: bool | None = Field(alias="show2FAPopup", default=None)
    login_error: AuthError | None = Field(alias="loginError", default=None)
