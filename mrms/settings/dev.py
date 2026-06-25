from .base import *  # noqa: F401, F403
from decouple import config

DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost").split(",")

LOGGING["root"]["handlers"] = (
    ["console"] if DEBUG else ["file", "error_file"]
)
LOGGING["loggers"]["django"]["handlers"] = (
    ["console"] if DEBUG else ["file"]
)
LOGGING["loggers"]["django.db.backends"]["handlers"] = (
    ["console"] if DEBUG else []
)
