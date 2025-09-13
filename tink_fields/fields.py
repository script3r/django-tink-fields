"""
Django Tink Fields - Encrypted model fields using Google Tink.

This module provides encrypted Django model fields that use Google Tink
for cryptographic operations, ensuring data confidentiality and integrity.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from django.conf import settings
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.utils.encoding import force_bytes, force_str

from tink import (
    JsonKeysetReader,
    KeysetHandle,
    aead,
    cleartext_keyset_handle,
    read_keyset_handle,
)

__all__ = [
    "EncryptedField",
    "EncryptedTextField",
    "EncryptedCharField",
    "EncryptedEmailField",
    "EncryptedIntegerField",
    "EncryptedDateField",
    "EncryptedDateTimeField",
]


# Constants
UNSUPPORTED_PROPERTIES = frozenset(["primary_key", "db_index", "unique"])
DEFAULT_KEYSET = "default"


def _default_aad_callback(x: Any) -> bytes:
    """Default AAD callback that returns empty bytes."""
    return b""


DEFAULT_AAD_CALLBACK = _default_aad_callback


@dataclass(frozen=True)
class KeysetConfig:
    """Configuration for a Tink keyset.

    Attributes:
        path: Path to the keyset file
        master_key_aead: Master key for encrypted keysets (optional)
        cleartext: Whether the keyset is in cleartext format
    """

    path: str
    master_key_aead: Optional[aead.Aead] = None
    cleartext: bool = False

    def __post_init__(self) -> None:
        """Validate the keyset configuration after initialization."""
        self.validate()

    def validate(self) -> None:
        """Validate the keyset configuration.

        Raises:
            ImproperlyConfigured: If the configuration is invalid
        """
        if not self.path:
            raise ImproperlyConfigured("Keyset path cannot be None or empty.")

        if not Path(self.path).exists():
            raise ImproperlyConfigured(f"Keyset {self.path} does not exist.")

        if not self.cleartext and self.master_key_aead is None:
            raise ImproperlyConfigured(
                "Encrypted keysets must specify `master_key_aead`."
            )


class EncryptedField(models.Field):
    """A field that uses Tink primitives to protect data confidentiality and integrity.

    This field encrypts data before storing it in the database and decrypts it
    when retrieving. It supports various Django field types through inheritance.

    Attributes:
        _unsupported_properties: Set of properties not supported by encrypted fields
        _internal_type: Internal Django field type (always BinaryField)
    """

    _unsupported_properties = UNSUPPORTED_PROPERTIES
    _internal_type = "BinaryField"

    # Type hints for instance attributes
    _keyset: str
    _keyset_handle: KeysetHandle
    _aad_callback: Callable[[models.Field], bytes]

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the encrypted field.

        Args:
            *args: Positional arguments passed to parent field
            **kwargs: Keyword arguments, including:
                keyset: Name of the keyset to use (default: "default")
                aad_callback: Callable for additional authenticated data
        """
        # Validate unsupported properties
        for prop in self._unsupported_properties:
            if prop in kwargs:
                raise ImproperlyConfigured(
                    f"Field `{self.__class__.__name__}` does not support property `{prop}`."
                )

        # Extract custom parameters
        self._keyset = kwargs.pop("keyset", DEFAULT_KEYSET)
        self._aad_callback = kwargs.pop("aad_callback", DEFAULT_AAD_CALLBACK)

        # Initialize keyset handle
        self._keyset_handle = self._get_tink_keyset_handle()

        # Call parent constructor
        super().__init__(*args, **kwargs)

    def _get_config(self) -> Dict[str, Any]:
        """Get the Tink fields configuration from Django settings.

        Returns:
            Dictionary containing keyset configurations

        Raises:
            ImproperlyConfigured: If TINK_FIELDS_CONFIG is not found in settings
        """
        config = getattr(settings, "TINK_FIELDS_CONFIG", None)
        if config is None:
            raise ImproperlyConfigured(
                "Could not find `TINK_FIELDS_CONFIG` attribute in settings."
            )
        return config

    def _get_tink_keyset_handle(self) -> KeysetHandle:
        """Read the configuration for the requested keyset and return a keyset handle.

        Returns:
            KeysetHandle: The configured Tink keyset handle

        Raises:
            ImproperlyConfigured: If keyset configuration is invalid or missing
        """
        config = self._get_config()

        if self._keyset not in config:
            raise ImproperlyConfigured(
                f"Could not find configuration for keyset `{self._keyset}` in `TINK_FIELDS_CONFIG`."
            )

        keyset_config = KeysetConfig(**config[self._keyset])

        with open(keyset_config.path, "r", encoding="utf-8") as f:
            reader = JsonKeysetReader(f.read())
            if keyset_config.cleartext:
                return cleartext_keyset_handle.read(reader)
            return read_keyset_handle(reader, keyset_config.master_key_aead)

    @lru_cache(maxsize=None)
    def _get_aead_primitive(self) -> aead.Aead:
        """Get the AEAD primitive for encryption/decryption operations.

        Returns:
            aead.Aead: The AEAD primitive instance
        """
        return self._keyset_handle.primitive(aead.Aead)

    def get_internal_type(self) -> str:
        """Return the internal Django field type.

        Returns:
            str: Always returns "BinaryField" for encrypted fields
        """
        return self._internal_type

    def get_db_prep_save(self, value: Any, connection: BaseDatabaseWrapper) -> Any:
        """Prepare the value for saving to the database.

        Args:
            value: The value to be saved
            connection: Database connection

        Returns:
            Binary object containing encrypted data, or None if value is None
        """
        val = super().get_db_prep_save(value, connection)
        if val is not None:
            return connection.Database.Binary(
                self._get_aead_primitive().encrypt(
                    force_bytes(val), self._aad_callback(self)
                )
            )
        return None

    def from_db_value(
        self,
        value: Any,
        expression: Any,
        connection: BaseDatabaseWrapper,
        *args,
    ) -> Any:
        """Convert database value to Python object.

        Args:
            value: Raw value from database
            expression: Database expression
            connection: Database connection
            *args: Additional arguments

        Returns:
            Decrypted and converted Python object, or None if value is None
        """
        if value is not None:
            return self.to_python(
                force_str(
                    self._get_aead_primitive().decrypt(
                        bytes(value), self._aad_callback(self)
                    )
                )
            )
        return None

    @property
    @lru_cache(maxsize=None)
    def validators(self) -> list:
        """Get field validators.

        Temporarily modifies the internal type to get appropriate validators
        from the parent field class.

        Returns:
            list: List of validators for the field
        """
        # Temporarily pretend to be whatever type of field we're masquerading
        # as, for purposes of constructing validators (needed for
        # IntegerField and subclasses).
        original_internal_type = self._internal_type
        self.__dict__["_internal_type"] = super().get_internal_type()
        try:
            return super().validators
        finally:
            self.__dict__["_internal_type"] = original_internal_type

    def __repr__(self) -> str:
        """Return string representation of the field.

        Returns:
            str: String representation including keyset name
        """
        return f"<{self.__class__.__name__}: keyset={self._keyset}>"


def _create_lookup_class(lookup_name: str, base_lookup_class: type) -> type:
    """Create a lookup class that raises errors for encrypted fields.

    Args:
        lookup_name: Name of the lookup operation
        base_lookup_class: Base lookup class to inherit from

    Returns:
        type: New lookup class that raises FieldError
    """

    def get_prep_lookup(self) -> None:
        """Raise error for unsupported lookups."""
        raise FieldError(
            f"{self.lhs.field.__class__.__name__} `{self.lookup_name}` does not support lookups."
        )

    return type(
        f"EncryptedField{lookup_name}",
        (base_lookup_class,),
        {"get_prep_lookup": get_prep_lookup},
    )


def _register_lookup_classes() -> None:
    """Register lookup classes for encrypted fields."""
    for name, lookup in models.Field.class_lookups.items():
        if name != "isnull":
            lookup_class = _create_lookup_class(name, lookup)
            EncryptedField.register_lookup(lookup_class)


# Register lookup classes at module level
_register_lookup_classes()


# Field implementations
class EncryptedTextField(EncryptedField, models.TextField):
    """Encrypted text field."""

    pass


class EncryptedCharField(EncryptedField, models.CharField):
    """Encrypted character field."""

    pass


class EncryptedEmailField(EncryptedField, models.EmailField):
    """Encrypted email field."""

    pass


class EncryptedIntegerField(EncryptedField, models.IntegerField):
    """Encrypted integer field."""

    pass


class EncryptedDateField(EncryptedField, models.DateField):
    """Encrypted date field."""

    pass


class EncryptedDateTimeField(EncryptedField, models.DateTimeField):
    """Encrypted datetime field."""

    pass
