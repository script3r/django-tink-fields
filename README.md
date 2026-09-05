# Django Tink Fields

[![PyPI](https://img.shields.io/pypi/v/django-tink-fields.svg)](https://pypi.org/project/django-tink-fields/)
[![Python](https://img.shields.io/pypi/pyversions/django-tink-fields.svg)](https://pypi.org/project/django-tink-fields/)
[![Django](https://img.shields.io/pypi/djversions/django-tink-fields.svg)](https://pypi.org/project/django-tink-fields/)
[![CI](https://github.com/script3r/django-tink-fields/actions/workflows/ci.yml/badge.svg)](https://github.com/script3r/django-tink-fields/actions/workflows/ci.yml)

Encrypted Django model fields backed by [Google Tink](https://developers.google.com/tink). Randomized AEAD fields protect confidentiality and integrity; deterministic AEAD fields additionally support exact database lookups when their equality leakage is acceptable.

## Compatibility

| Python | Django |
| --- | --- |
| 3.10, 3.11 | 5.2 |
| 3.12 | 5.2, 6.0 |
| 3.13, 3.14 | 5.2, 6.0 |

The package is tested against SQLite. The fields use Django's `BinaryField` database type and are intended to work on every database supported by Django, but applications should run their own backend-specific integration tests.

## Installation

```bash
python -m pip install django-tink-fields
```

## Configuration

Create a Tink JSON keyset, then configure its path in Django settings. A cleartext keyset contains the encryption key itself: use one only for local development or when the file is protected by controls appropriate for production secrets.

```bash
tinkey create-keyset \
  --key-template AES256_GCM \
  --out-format json \
  --out keyset.json
```

```python
# settings.py
TINK_FIELDS_CONFIG = {
    "default": {
        "path": "/run/secrets/application-keyset.json",
        "cleartext": True,
    },
}
```

Encrypted keysets require a Tink `Aead` supplied by your KMS integration:

```python
TINK_FIELDS_CONFIG = {
    "default": {
        "path": "/run/secrets/encrypted-keyset.json",
        "cleartext": False,
        "master_key_aead": kms_aead,
    },
}
```

Configuration and key files are loaded lazily, when a field first encrypts or decrypts a value. This allows Django to import models and serialize migrations in environments that do not hold production keys.

## Usage

```python
from django.db import models
from tink_fields import EncryptedCharField, EncryptedDateField, EncryptedEmailField


class Customer(models.Model):
    name = EncryptedCharField(max_length=100)
    email = EncryptedEmailField()
    birth_date = EncryptedDateField(null=True)
```

Values are ordinary Python objects on model instances. Django validates them using the corresponding built-in field's validators, encrypts them before database storage, and decrypts them when loading rows.

### Randomized fields

| Encrypted field | Django value semantics |
| --- | --- |
| `EncryptedBinaryField` | `BinaryField` |
| `EncryptedBooleanField` | `BooleanField` |
| `EncryptedCharField` | `CharField` |
| `EncryptedDateField` | `DateField` |
| `EncryptedDateTimeField` | `DateTimeField` |
| `EncryptedDecimalField` | `DecimalField` |
| `EncryptedEmailField` | `EmailField` |
| `EncryptedFloatField` | `FloatField` |
| `EncryptedIntegerField` | `IntegerField` |
| `EncryptedJSONField` | `JSONField` |
| `EncryptedPositiveIntegerField` | `PositiveIntegerField` |
| `EncryptedSlugField` | `SlugField` |
| `EncryptedTextField` | `TextField` |
| `EncryptedURLField` | `URLField` |
| `EncryptedUUIDField` | `UUIDField` |

Randomized fields deliberately reject `primary_key`, `unique`, `db_index`, and `db_default`. They support `isnull` queries, including the equivalent `field=None`; every lookup that compares values raises `FieldError`. Inherited JSON key lookups, date transforms, and custom registered lookups are also rejected because they would operate on ciphertext. Database expressions such as `F()` assignments are also rejected because the database cannot encrypt them.

### Deterministic fields and exact lookups

Generate a separate deterministic keyset and name it in settings:

```bash
tinkey create-keyset \
  --key-template AES256_SIV \
  --out-format json \
  --out deterministic-keyset.json
```

```python
TINK_FIELDS_CONFIG = {
    "default": {"path": "/run/secrets/keyset.json", "cleartext": True},
    "search": {"path": "/run/secrets/deterministic-keyset.json", "cleartext": True},
}
```

```python
from tink_fields import DeterministicEncryptedCharField


class ExternalIdentity(models.Model):
    subject = DeterministicEncryptedCharField(
        max_length=255,
        keyset="search",
        db_index=True,
        unique=True,
    )


identity = ExternalIdentity.objects.get(subject="stable-external-id")
```

Available deterministic types are `Text`, `Char`, `Email`, `Integer`, `UUID`, `Boolean`, `Date`, and `DateTime`. They support only `exact` and `isnull` lookups. `db_index` and `unique` are supported; primary keys and database defaults are not.

Deterministic encryption reveals when rows contain equal values, which can expose frequency and membership information. Do not use it for low-entropy secrets such as Boolean values, status codes, or predictable identifiers unless that leakage is explicitly acceptable. An index makes equality patterns still easier to observe.

## Multiple keysets and AAD

Pass `keyset` to select a non-default configuration. Pass a module-level `aad_callback` to bind ciphertext to stable field context:

```python
from django.db import models
from django.utils.encoding import force_bytes
from tink_fields import EncryptedCharField


def field_aad(field: models.Field) -> bytes:
    return force_bytes(f"{field.model._meta.label}:{field.name}")


class Credential(models.Model):
    secret = EncryptedCharField(
        max_length=255,
        keyset="credentials",
        aad_callback=field_aad,
    )
```

The callback receives the Django field, not the model instance. It must return the same bytes for every future read of existing ciphertext. Keep it at module scope so Django migrations can serialize it. Renaming a model or field will make context-derived AAD change, so plan a data migration before such a rename.

## Key rotation and data migrations

Tink key rotation normally adds a new primary key while retaining old enabled keys for decryption. Replace the configured keyset atomically and restart application processes. If an immediate in-process reload is required, call:

```python
from tink_fields import clear_keyset_cache

clear_keyset_cache()
```

Cache invalidation is synchronized with keyset loading and primitive construction. Operations that already obtained a primitive may finish with the old key; subsequent field operations load the replacement. The cache is local to each process, so reload or restart every worker.

Changing `keyset=` does not re-encrypt existing rows; it only changes how future reads and writes are processed. Likewise, changing an existing plaintext Django field to an encrypted field requires an explicit staged data migration. Back up data and test recovery before any key or ciphertext migration.

## Security limitations

- Losing the keyset or required master key makes data unrecoverable.
- Exposing a cleartext keyset exposes every value encrypted with it.
- Encryption does not hide row existence, nullness, ciphertext length, access patterns, or—when deterministic encryption is used—equality patterns.
- Ordering encrypted columns is permitted by databases but orders ciphertext, not plaintext, and has no useful application meaning.
- AAD authenticates context but is not secret and is not stored automatically.
- Validation happens before storage but is not a substitute for authorization, logging controls, backups, or database security.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and supported releases.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,test]" build twine pip-audit bandit tox

python -m pytest
python -m pytest -c example_project/pytest.ini example_project/example_app/tests
ruff check .
ruff format --check .
pyright --pythonpath "$(command -v python)"
tox
```

The release process is documented in [RELEASING.md](RELEASING.md). Changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## License

BSD-3-Clause. See [LICENSE.txt](LICENSE.txt).
