from collections.abc import (
    Callable,
    Coroutine,
)
from functools import wraps
from typing import (
    Any,
    ParamSpec,
    TypeAlias,
    TypeVar,
)

import phonenumbers as pn
from sqlalchemy.exc import (
    IntegrityError,
    SQLAlchemyError,
)

from . import errors

_T = TypeVar("_T")
_P = ParamSpec("_P")
AsyncFunc: TypeAlias = Callable[_P, Coroutine[Any, Any, _T]]


def handle_sqlalchemy_errors(func: AsyncFunc[_P, _T]) -> AsyncFunc[_P, _T]:
    """Обработка исключений базы данных и перенос их в кастомные ошибки"""

    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        try:
            return await func(*args, **kwargs)

        except IntegrityError as ex:
            raise errors.AlreadyExistsError from ex

        except SQLAlchemyError as ex:
            raise errors.DBError from ex

    return wrapper


MOBILE_NUMBER_TYPES = (
    pn.PhoneNumberType.MOBILE,
    pn.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    pn.PhoneNumberType.FIXED_LINE,
)


def validate_phone_number(phone_number: str | None) -> str | None:
    """Валидация номера телефона и возврат в определенном формате"""
    if phone_number is None:
        return None

    try:
        number = pn.parse(phone_number, "RU")

    except pn.NumberParseException:
        return None

    if (not pn.is_valid_number(number)
            or pn.number_type(number) not in MOBILE_NUMBER_TYPES):
        return None

    return pn.format_number(number, pn.PhoneNumberFormat.INTERNATIONAL)
