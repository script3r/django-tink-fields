"""
Django Tink Fields - Encrypted model fields using Google Tink.

This package provides encrypted Django model fields that use Google Tink
for cryptographic operations, ensuring data confidentiality and integrity.
"""

# Register Tink primitives
from tink import aead

# Try to import deterministic AEAD, fall back gracefully if not available
try:
    from tink import daead

    DAEAD_AVAILABLE = True
except ImportError:
    DAEAD_AVAILABLE = False
    daead = None

from .fields import (
    EncryptedBinaryField,
    EncryptedCharField,
    EncryptedDateField,
    EncryptedDateTimeField,
    EncryptedEmailField,
    EncryptedField,
    EncryptedIntegerField,
    EncryptedTextField,
    DeterministicEncryptedField,
    DeterministicEncryptedTextField,
    DeterministicEncryptedCharField,
    DeterministicEncryptedEmailField,
    DeterministicEncryptedIntegerField,
    DeterministicEncryptedDateField,
    DeterministicEncryptedDateTimeField,
)

aead.register()
if DAEAD_AVAILABLE:
    daead.register()

__version__ = "0.3.0"
__all__ = [
    "EncryptedField",
    "EncryptedTextField",
    "EncryptedCharField",
    "EncryptedEmailField",
    "EncryptedIntegerField",
    "EncryptedDateField",
    "EncryptedDateTimeField",
    "EncryptedBinaryField",
    "DeterministicEncryptedField",
    "DeterministicEncryptedTextField",
    "DeterministicEncryptedCharField",
    "DeterministicEncryptedEmailField",
    "DeterministicEncryptedIntegerField",
    "DeterministicEncryptedDateField",
    "DeterministicEncryptedDateTimeField",
]
