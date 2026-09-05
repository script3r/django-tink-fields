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

Runtime dependencies are `Django>=5.2,<6.1` and `tink>=1.13,<2`. CI covers all eight Python/Django combinations above and separately tests Tink 1.13.0.

SQLite has full ORM integration coverage. PostgreSQL tests use the real psycopg driver adapter without a server; PostgreSQL, MySQL, and Oracle server compatibility is not established by this suite. Encrypted columns use Django's `BinaryField` database type, but backend-dependent serialization still affects some values and deterministic equality. See the [operations guide](https://github.com/script3r/django-tink-fields/blob/main/docs/operations.md).

## Upgrading to 0.5.0

Read the [upgrade guide](https://github.com/script3r/django-tink-fields/blob/main/docs/upgrading-to-0.5.md) before deploying. Check existing slug indexes even if `makemigrations` reports no changes, review rejected field/query configurations, and assess PostgreSQL binary values or datetimes already corrupted by earlier writes. This release prevents new failures; it cannot reconstruct lost or previously shifted data automatically.

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

Configuration and key files are loaded lazily, when a field first encrypts or decrypts a value. This allows Django to import models and serialize migrations in environments that do not hold production keys. `path` accepts strings or path-like objects and expands `~`; `cleartext` must be a Boolean and defaults to `False`. Encrypted keyset loading uses empty keyset-encryption AAD. A KMS client and credentials must be configured by the application; a URI or raw master key is not an `Aead` instance.

## Usage

```python
from django.db import models
from tink_fields import EncryptedCharField, EncryptedDateField, EncryptedEmailField


class Customer(models.Model):
    name = EncryptedCharField(max_length=100)
    email = EncryptedEmailField()
    birth_date = EncryptedDateField(null=True)
```

On reads, field values are decrypted into the corresponding Python types. The fields use the corresponding built-in field's validators, encrypt values before database storage, and decrypt them when loading rows. As with ordinary Django models, `save()` does not call `full_clean()` automatically; use a validated model form or call `full_clean()` explicitly when validation is required.

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

Randomized fields reject field-level `primary_key`, `unique`, `db_index`, and `db_default`, whether supplied positionally or by keyword. They support `isnull` queries, including `field=None`; value comparisons raise `FieldError`. `EncryptedSlugField` defaults to `db_index=False`. Older migrations may omit the former default, so removing an old physical index can require an explicit database migration even when `makemigrations` reports no changes.

JSON key lookups/projections, date transforms, and custom registered lookups are rejected. Database expressions such as `F()` assignments and the `CASE` expressions used by `bulk_update()` are unsupported. Literal saves, `bulk_create()`, and literal `QuerySet.update()` encrypt through the field; validation remains explicit.

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
from django.db import models
from tink_fields import DeterministicEncryptedCharField


class ExternalIdentity(models.Model):
    subject = DeterministicEncryptedCharField(
        max_length=255,
        keyset="search",
        db_index=True,
        unique=True,
    )


ExternalIdentity.objects.create(subject="stable-external-id")
identity = ExternalIdentity.objects.get(subject="stable-external-id")
```

Available deterministic types are `DeterministicEncryptedTextField`, `DeterministicEncryptedCharField`, `DeterministicEncryptedEmailField`, `DeterministicEncryptedIntegerField`, `DeterministicEncryptedUUIDField`, `DeterministicEncryptedBooleanField`, `DeterministicEncryptedDateField`, and `DeterministicEncryptedDateTimeField`.

They support only `exact` and `isnull` lookups, including `field=None`. `db_index` and `unique` are supported; primary keys and database defaults are not. Equality and uniqueness compare ciphertext from the same prepared bytes, key generation, and AAD. They do not provide plaintext collation, case folding, or equality across differently normalized values. For example, PostgreSQL datetime values representing the same instant with different offsets can serialize differently; review the [representation limits](https://github.com/script3r/django-tink-fields/blob/main/docs/operations.md#database-behavior).

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

The default AAD is empty and does not bind ciphertext to a row, tenant, field, or model. The callback receives the Django field, not the model instance; it cannot implement row-specific context. It must return the same bytes for every future read of existing ciphertext. Keep it at module scope so Django migrations can serialize it. Renaming a model or field will make context-derived AAD change, so plan a data migration before such a rename.

## Key rotation and data migrations

Tink key rotation normally adds a new primary key while retaining old enabled keys for decryption. Replace the configured keyset atomically and restart application processes. If an immediate in-process reload is required, call:

```python
from tink_fields import clear_keyset_cache

clear_keyset_cache()
```

Cache invalidation is synchronized with keyset loading and primitive construction. Operations that already obtained a primitive may finish with the old key; subsequent field operations load the replacement. The cache is local to each process, so reload or restart every worker.

For deterministic fields, promoting a new primary key changes the ciphertext used by exact lookups. Retaining old keys permits decryption but does not make new equality queries match rows encrypted under an old primary key, and a unique ciphertext index cannot enforce plaintext uniqueness across key generations. Plan a coordinated data migration before rotating deterministic keys; cache invalidation alone does not solve this.

Changing `keyset=` does not re-encrypt existing rows; it only changes how future reads and writes are processed. Likewise, changing an existing plaintext Django field to an encrypted field requires an explicit staged data migration. Back up data and test recovery before any key or ciphertext migration.

## Security limitations

- Losing the keyset or required master key makes data unrecoverable.
- Exposing a cleartext keyset exposes every value encrypted with it.
- Encryption does not hide row existence, nullness, ciphertext length, access patterns, or—when deterministic encryption is used—equality patterns.
- Ordering, explicit SQL functions, aggregates, and custom database constraints can operate on ciphertext; the lookup restrictions are not a SQL sandbox and do not give these operations plaintext semantics.
- AAD authenticates context but is not secret and is not stored automatically.
- Field validation requires a model form or an explicit `full_clean()` call; encryption is not a substitute for application validation, authorization, logging controls, backups, or database security.

See the [security policy](https://github.com/script3r/django-tink-fields/blob/main/SECURITY.md) for vulnerability reporting and supported releases.

## Documentation and development

- [Operations and limitations](https://github.com/script3r/django-tink-fields/blob/main/docs/operations.md): queries, validation, AAD, caching, rotation, and backend behavior.
- [0.5.0 upgrade guide](https://github.com/script3r/django-tink-fields/blob/main/docs/upgrading-to-0.5.md): schema checks, compatibility changes, and historical data recovery.
- [Contributing](https://github.com/script3r/django-tink-fields/blob/main/CONTRIBUTING.md): setup, the nine-environment test matrix, lint/type checks, audits, and builds.
- [Example project](https://github.com/script3r/django-tink-fields/blob/main/example_project/README.md): a SQLite test harness using disposable fixture keys.
- [Release process](https://github.com/script3r/django-tink-fields/blob/main/RELEASING.md) and [changelog](https://github.com/script3r/django-tink-fields/blob/main/CHANGELOG.md).
- [September 2026 review](https://github.com/script3r/django-tink-fields/blob/main/docs/code-review-2026-09.md): findings, benchmark methodology, and remaining work.

## License

BSD-3-Clause. See [LICENSE.txt](https://github.com/script3r/django-tink-fields/blob/main/LICENSE.txt).
