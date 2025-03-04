import enum
from datetime import timedelta

from yarl import URL

HHHost = URL("https://hh.ru")


@enum.unique
class HHPaths(enum.StrEnum):
    """Пути запросов к HeadHunter"""

    LOGIN = "account/login"
    GET_RESUMES = "applicant/resumes"
    RAISE_RESUME = "applicant/resumes/touch"


RE_RISING_PERIOD = timedelta(hours=4)
