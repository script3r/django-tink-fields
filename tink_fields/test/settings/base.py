from pathlib import Path

INSTALLED_APPS = [
    "tink_fields.test",
]

SECRET_KEY = "secret"

USE_TZ = False

KEYSET_DIR = Path(__file__).resolve().parents[1]

TINK_FIELDS_CONFIG = {
    "default": {
        "cleartext": True,
        "path": KEYSET_DIR / "test_plaintext_keyset.json",
    },
    "alternate": {
        "cleartext": True,
        "path": KEYSET_DIR / "test_plaintext_keyset.json",
    },
    "cleartext_test": {
        "cleartext": True,
        "path": KEYSET_DIR / "test_cleartext_keyset.json",
    },
    "deterministic": {
        "cleartext": True,
        "path": KEYSET_DIR / "test_deterministic_keyset.json",
    },
}
