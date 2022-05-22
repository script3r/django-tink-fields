
# Django Tink Fields

Leverages [Google Tink](https://developers.google.com/tink) to encrypt Django's core model fields. This work is heavily based on the work of [Django Fernet Fields](https://github.com/orcasgit/django-fernet-fields) which seems to have been abandoned last few years.

## Installation

Use `pip` to install `django-tink-fields`:

```bash
pip install django-tink-fields
```

Edit `settings.py` and introduce a configuration section for `TINK_FIELDS_CONFIG`:

```python
TINK_FIELDS_CONFIG = {
    "default": {
        "cleartext": False,
        "path": "/path/to/an/encryted_keyset.json",
    },
    "another": {
        "cleartext": True,
        "path": "/path/to/a/cleartext_keyset.json",
    }
}
```

Tink keysets can be created via `tinkey` and may optionally be wrapped via a key-management system such as `AWS KMS` or `GCP KMS`.

To create a cleartext keyset for testing purposes:

```bash
tinkey create-keyset --out-format json --out test_plaintext_keyset.json --key-template AES128_GCM
```

Alternatively, to create an encrypted keyset that is wrapped by `GCP KMS`, specify `--master-key-uri` as follow:

```bash
tinkey create-keyset --out-format json --out test_encrypted_keyset.json --key-template AES128_GCM --master-key-uri=gcp-kms://projects/foo1/locations/global/keyRings/foo2/cryptoKeys/foo3
```

To learn more about `tinkey` [read the relevant documentation](https://github.com/google/tink/blob/master/docs/TINKEY.md).

## Examples

The following model creates an encrypted char field that makes use of the `default` keyset.

```python
from django.db import models
from tink_fields import EncryptedCharField

class SomeModel(models.Model):
    some_value = EncryptedCharField(max_length=32)

```

You may specify a specific keyset by providing a `keyset` keyword argument:

```python
from django.db import models
from tink_fields import EncryptedCharField

class AnotherModel(models.Model):
    some_value = EncryptedCharField(max_length=32, keyset="another")

```

Supported field types include: `EncryptedCharField`, `EncryptedTextField`, `EncryptedDateField`, `EncryptedDateTimeField`, `EncryptedEmailField`, and `EncryptedIntegerField`.

### Associated Data

The encrypted fields make use of `Authenticated Encryption With Associated Data (AEAD)` which offers confidentiality and integrity within the same mode of operation. This allows the caller to specify a cleartext fragment named `additional authenticated data (aad)` to the encryption and decryption operations and receive cryptographic guarantees that the ciphertext data has not been tampered with.

To specify the `aad` fragment, provide a callback function `aad_callback` in the keyword arguments:

```python
from django.db import models
from tink_fields import EncryptedCharField

class AnotherModel(models.Model):
    some_value = EncryptedCharField(max_length=32, aad_callback=lambda x: b"some value")

```

The value passed to the callback is the instance of the model field, with a signature of `Callable[[models.Field], bytes]`. As a reminder, the associated data is *not* encrypted so **do not store sensitive data in it**.

## Acknowledgements

- [Google Tink](https://github.com/google/tink/blob/master/docs/PYTHON-HOWTO.md)
- [Django Fernet Fields](https://github.com/orcasgit/django-fernet-fields)

## Authors

- [@script3r](https://www.github.com/script3r)
