from .base import *  # noqa

import os

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
    "daead": {
        "cleartext": True,
        "path": os.path.join(HERE, "../test_plaintext_daead_keyset.json"),
    },
    "db_keyset": {
        "cleartext": True,
        "path": os.path.join(HERE, "../test_plaintext_keyset.json"),
    },
    "db_aead": {
        "db_name": "aead",
    },
    "db_daead": {
        "db_name": "daead",
    },
}
