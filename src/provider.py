from typing import TYPE_CHECKING

from . import models
from .database import dto

if TYPE_CHECKING:
    from .database import Repository
    from .headhunter import HeadHunter


async def add_account(
    db: "Repository",
    hh: "HeadHunter",
    account: models.Account,
) -> None:
    """Добавляет новый аккаунт в БД"""
    await hh.get_account_auth_tokens(account)
    db_account = dto.DBAccount(
        login=account.login,
        password=account.password,
    )
    await db.add_account(db_account)


async def get_account_by_login(
    db: "Repository",
    login: str,
) -> models.Account:
    """Запрашивает и возвращает аккаунт из БД по логину"""
    db_account = await db.get_account_by_login(login)
    return models.Account.from_db(db_account)


async def get_account_resumes_from_hh(
    hh: "HeadHunter",
    account: models.Account,
) -> list[models.Resume]:
    """Запрашивает и возвращает все резюме аккаунта из HeadHunter"""
    return await hh.get_resumes(account)


async def add_account_resume(
    db: "Repository",
    account: models.Account,
    resume: models.Resume,
) -> None:
    """Добавляет резюме в БД"""
    db_resume = dto.DBResume(
        resume_id=resume.resume_id,
        title=resume.title,
        account_login=account.login,
    )
    await db.add_account_resume(db_resume)


async def get_all_accounts_resumes(
    db: "Repository",
) -> list[tuple[models.Account, models.Resume]]:
    """Запрашивает и возвращает все резюме всех аккаунтов из БД"""
    db_accounts_resumes = await db.get_all_accounts_resumes()
    return [
        (models.Account.from_db(db_account), models.Resume.from_db(db_resume))
        for db_account, db_resume in db_accounts_resumes
    ]


async def get_account_resumes_from_db(
    db: "Repository",
    login: str,
) -> list[models.Resume]:
    """Запрашивает и возвращает все резюме аккаунта из БД"""
    db_resumes = await db.get_account_resumes(login)
    return [models.Resume.from_db(db_resume) for db_resume in db_resumes]


async def delete_account_resume(
    db: "Repository",
    login: str,
    title: str,
) -> None:
    """Удаляет резюме из БД"""
    await db.delete_account_resume(login, title)
