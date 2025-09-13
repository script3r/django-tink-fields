"""
Django Tink Fields - Encrypted model fields using Google Tink.

This package provides encrypted Django model fields that use Google Tink
for cryptographic operations, ensuring data confidentiality and integrity.
"""

# Register Tink AEAD primitives
from tink import aead

from .fields import (
    EncryptedCharField,
    EncryptedDateField,
    EncryptedDateTimeField,
    EncryptedEmailField,
    EncryptedField,
    EncryptedIntegerField,
    EncryptedTextField,
)

aead.register()

__version__ = "0.3.0"
__all__ = [
    "EncryptedField",
    "EncryptedTextField",
    "EncryptedCharField",
    "EncryptedEmailField",
    "EncryptedIntegerField",
    "EncryptedDateField",
    "EncryptedDateTimeField",
]
