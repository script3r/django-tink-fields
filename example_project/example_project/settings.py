from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

SECRET_KEY = "example-secret-key"
DEBUG = True
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "tink_fields",
    "example_app",
]

MIDDLEWARE: list[str] = []
ROOT_URLCONF = "example_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

WSGI_APPLICATION = "example_project.wsgi.application"
ASGI_APPLICATION = "example_project.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
USE_TZ = False

MIGRATION_MODULES = {"example_app": None}

TINK_FIELDS_CONFIG = {
    "default": {
        "cleartext": True,
        "path": str(ROOT_DIR / "tink_fields" / "test" / "test_plaintext_keyset.json"),
    },
    "deterministic": {
        "cleartext": True,
        "path": str(ROOT_DIR / "tink_fields" / "test" / "test_deterministic_keyset.json"),
    },
}
