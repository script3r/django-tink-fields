from os import getenv

from .base import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": getenv("PGDATABASE", "tink_fields"),
        "USER": getenv("PGUSER", "postgres"),
        "PASSWORD": getenv("PGPASSWORD", ""),
        "HOST": getenv("PGHOST", "localhost"),
        "PORT": getenv("PGPORT", "5432"),
    },
}
