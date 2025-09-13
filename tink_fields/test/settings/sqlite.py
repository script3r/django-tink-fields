import os

from .base import *  # noqa

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "testdb.sqlite")

USE_TZ = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB,
        "TEST": {
            "NAME": DB,
        },
    },
}

TINK_FIELDS_CONFIG = {
    "default": {
        "cleartext": True,
        "path": os.path.join(HERE, "../test_plaintext_keyset.json"),
    },
    "alternate": {
        "cleartext": True,
        "path": os.path.join(HERE, "../test_plaintext_keyset.json"),
    },
    "cleartext_test": {
        "cleartext": True,
        "path": os.path.join(HERE, "../test_cleartext_keyset.json"),
    },
    "deterministic": {
        "cleartext": True,
        "path": os.path.join(HERE, "../test_deterministic_keyset.json"),
    },
}
