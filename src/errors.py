class HeadHunterError(Exception):
    """Базовая ошибка сервиса HeadHunter"""


class HHResponseError(HeadHunterError):
    """Ошибка ответа на запрос"""


class DBError(Exception):
    """Базовая ошибка базы данных"""


class AlreadyExistsError(DBError):
    """Запись уже существует в БД"""


class NotExistsError(DBError):
    """Запись не найдена в БД"""
