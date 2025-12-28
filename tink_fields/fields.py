"""
Django Tink Fields - Encrypted model fields using Google Tink.

This module provides encrypted Django model fields that use Google Tink
for cryptographic operations, ensuring data confidentiality and integrity.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from django.conf import settings
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import models
from django.utils.encoding import force_bytes, force_str
from django.utils.functional import cached_property

from tink import (
    JsonKeysetReader,
    aead,
    cleartext_keyset_handle,
    read_keyset_handle,
)

# Try to import deterministic AEAD, fall back gracefully if not available
try:
    from tink import daead

    DAEAD_AVAILABLE = True
except ImportError:
    DAEAD_AVAILABLE = False
    daead = None


def _register_tink_primitives() -> None:
    """Register Tink primitives so direct module imports are safe."""
    aead.register()
    if DAEAD_AVAILABLE:
        daead.register()


_register_tink_primitives()

__all__ = [
    "EncryptedField",
    "EncryptedTextField",
    "EncryptedCharField",
    "EncryptedEmailField",
    "EncryptedBooleanField",
    "EncryptedIntegerField",
    "EncryptedPositiveIntegerField",
    "EncryptedFloatField",
    "EncryptedDecimalField",
    "EncryptedUUIDField",
    "EncryptedJSONField",
    "EncryptedURLField",
    "EncryptedSlugField",
    "EncryptedDateField",
    "EncryptedDateTimeField",
    "EncryptedBinaryField",
    "DeterministicEncryptedField",
    "DeterministicEncryptedTextField",
    "DeterministicEncryptedCharField",
    "DeterministicEncryptedEmailField",
    "DeterministicEncryptedIntegerField",
    "DeterministicEncryptedUUIDField",
    "DeterministicEncryptedBooleanField",
    "DeterministicEncryptedDateField",
    "DeterministicEncryptedDateTimeField",
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

    def __post_init__(self):
        """Validate the keyset configuration after initialization."""
        self.validate()

    def validate(self):
        """Validate the keyset configuration.

        Raises:
            ImproperlyConfigured: If the configuration is invalid
        """
        if not self.path:
            raise ImproperlyConfigured("Keyset path cannot be None or empty.")

        if not Path(self.path).exists():
            raise ImproperlyConfigured(f"Keyset {self.path} does not exist.")

        if not self.cleartext and self.master_key_aead is None:
            raise ImproperlyConfigured("Encrypted keysets must specify `master_key_aead`.")


class KeysetManager:
    """Manages Tink keyset handles and primitives.

    This class provides a centralized way to manage keyset handles and
    their associated primitives, with proper caching to avoid memory leaks.
    """

    _handle_cache: dict[tuple[str, str, bool, int], Any] = {}

    def __init__(self, keyset_name: str, aad_callback: Any):
        """Initialize the keyset manager.

        Args:
            keyset_name: Name of the keyset to use
            aad_callback: Callable for additional authenticated data
        """
        self.keyset_name = keyset_name
        self.aad_callback = aad_callback
        self._keyset_handle = None

        # Validate configuration immediately
        self._validate_config()

    def _validate_config(self):
        """Validate the keyset configuration.

        Raises:
            ImproperlyConfigured: If the configuration is invalid
        """
        config = self._get_config()

        if self.keyset_name not in config:
            raise ImproperlyConfigured(
                f"Could not find configuration for keyset `{self.keyset_name}` " f"in `TINK_FIELDS_CONFIG`."
            )

    def _get_config(self):
        """Get the Tink fields configuration from Django settings.

        Returns:
            Dictionary containing keyset configurations

        Raises:
            ImproperlyConfigured: If TINK_FIELDS_CONFIG is not found in settings
        """
        config = getattr(settings, "TINK_FIELDS_CONFIG", None)
        if config is None:
            raise ImproperlyConfigured("Could not find `TINK_FIELDS_CONFIG` attribute in settings.")
        return config

    def _get_tink_keyset_handle(self):
        """Read the configuration for the requested keyset and return a keyset handle.

        Returns:
            KeysetHandle: The configured Tink keyset handle

        Raises:
            ImproperlyConfigured: If keyset configuration is invalid or missing
        """
        if self._keyset_handle is None:
            config = self._get_config()

            if self.keyset_name not in config:
                raise ImproperlyConfigured(
                    f"Could not find configuration for keyset `{self.keyset_name}` " f"in `TINK_FIELDS_CONFIG`."
                )

            keyset_config = KeysetConfig(**config[self.keyset_name])
            cache_key = (
                self.keyset_name,
                keyset_config.path,
                keyset_config.cleartext,
                id(keyset_config.master_key_aead) if keyset_config.master_key_aead is not None else 0,
            )
            cached_handle = self._handle_cache.get(cache_key)
            if cached_handle is not None:
                self._keyset_handle = cached_handle
            else:
                with open(keyset_config.path, "r", encoding="utf-8") as f:
                    reader = JsonKeysetReader(f.read())
                    if keyset_config.cleartext:
                        self._keyset_handle = cleartext_keyset_handle.read(reader)
                    else:
                        self._keyset_handle = read_keyset_handle(reader, keyset_config.master_key_aead)
                self._handle_cache[cache_key] = self._keyset_handle

        return self._keyset_handle

    @cached_property
    def aead_primitive(self):
        """Get the AEAD primitive for encryption/decryption operations.

        Returns:
            aead.Aead: The AEAD primitive instance
        """
        return self._get_tink_keyset_handle().primitive(aead.Aead)

    @cached_property
    def daead_primitive(self):
        """Get the Deterministic AEAD primitive for encryption/decryption operations.

        Returns:
            daead.DeterministicAead: The Deterministic AEAD primitive instance

        Raises:
            ImproperlyConfigured: If deterministic AEAD is not available or keyset doesn't support it
        """
        if not DAEAD_AVAILABLE:
            raise ImproperlyConfigured(
                "Deterministic AEAD is not available in this version of Tink. "
                "Please upgrade to a newer version that supports deterministic AEAD."
            )

        try:
            return self._get_tink_keyset_handle().primitive(daead.DeterministicAead)
        except Exception as e:
            raise ImproperlyConfigured(
                f"Current keyset does not support deterministic AEAD: {e}. "
                "Please use a keyset that contains deterministic AEAD keys."
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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
                raise ImproperlyConfigured(f"Field `{self.__class__.__name__}` does not support " f"property `{prop}`.")

        # Extract custom parameters
        self._keyset = kwargs.pop("keyset", DEFAULT_KEYSET)
        self._aad_callback = kwargs.pop("aad_callback", DEFAULT_AAD_CALLBACK)

        # Call parent constructor first
        super().__init__(*args, **kwargs)

        # Initialize keyset manager after parent constructor
        # This ensures the field is properly initialized before accessing settings
        self._keyset_manager = KeysetManager(self._keyset, self._aad_callback)

    def _to_python_prepare(self, value: bytes) -> str:
        """Prepare decrypted value for to_python conversion.

        Args:
            value: Decrypted bytes value

        Returns:
            str: String representation of the value
        """
        return force_str(value)

    def _get_aead_primitive(self):
        """Get the AEAD primitive for encryption/decryption operations.

        This method is kept for backward compatibility with tests.

        Returns:
            aead.Aead: The AEAD primitive instance
        """
        return self._keyset_manager.aead_primitive

    @property
    def _keyset_handle(self):
        """Get the keyset handle for backward compatibility.

        Returns:
            KeysetHandle: The configured Tink keyset handle
        """
        return self._keyset_manager._get_tink_keyset_handle()

    def get_internal_type(self):
        """Return the internal Django field type.

        Returns:
            str: Always returns "BinaryField" for encrypted fields
        """
        return self._internal_type

    def get_db_prep_save(self, value: Any, connection: Any) -> Any:
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
                self._keyset_manager.aead_primitive.encrypt(force_bytes(val), self._aad_callback(self))
            )
        return None

    def from_db_value(
        self,
        value: Any,
        expression: Any,
        connection: Any,
        *args: Any,
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
            decrypted = self._keyset_manager.aead_primitive.decrypt(bytes(value), self._aad_callback(self))
            return self.to_python(self._to_python_prepare(decrypted))
        return None

    @cached_property
    def validators(self) -> list[Any]:
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

    def __repr__(self):
        """Return string representation of the field.

        Returns:
            str: String representation including keyset name
        """
        return f"<{self.__class__.__name__}: keyset={self._keyset}>"


def _create_lookup_class(lookup_name: str, base_lookup_class: type[Any]) -> type[Any]:
    """Create a lookup class that raises errors for encrypted fields.

    Args:
        lookup_name: Name of the lookup operation
        base_lookup_class: Base lookup class to inherit from

    Returns:
        type: New lookup class that raises FieldError
    """

    def get_prep_lookup(self) -> None:
        """Raise error for unsupported lookups."""
        raise FieldError(f"{self.lhs.field.__class__.__name__} `{self.lookup_name}` " f"does not support lookups.")

    return type(
        f"EncryptedField{lookup_name}",
        (base_lookup_class,),
        {"get_prep_lookup": get_prep_lookup},
    )


def _create_deterministic_lookup_class(lookup_name: str, base_lookup_class: type[Any]) -> type[Any]:
    """Create a lookup class for deterministic encrypted fields.

    For deterministic fields, we support exact lookups by encrypting the
    prepared value and comparing ciphertexts.

    Args:
        lookup_name: Name of the lookup operation
        base_lookup_class: Base lookup class to inherit from

    Returns:
        type: New lookup class for deterministic fields
    """

    def get_prep_lookup(self) -> Any:
        """Handle lookups for deterministic encrypted fields."""
        if self.lookup_name == "exact":
            # For exact lookups, we need to encrypt the value and use 'in' lookup
            value = self.rhs
            if value is None:
                return None

            # Get the field instance
            field = self.lhs.field
            if hasattr(field, "_keyset_manager"):
                prepared_value = field.get_prep_value(value)
                if prepared_value is None:
                    return None
                # Encrypt the value using the field's keyset manager
                encrypted_value = field._keyset_manager.daead_primitive.encrypt_deterministically(
                    force_bytes(prepared_value), field._aad_callback(field)
                )
                # Return the encrypted value directly
                return encrypted_value
            else:
                raise FieldError("Field does not have keyset manager for deterministic encryption.")
        elif self.lookup_name == "isnull":
            # isnull lookups are always supported
            return self.rhs
        else:
            # All other lookups are not supported
            raise FieldError(f"{self.lhs.field.__class__.__name__} `{self.lookup_name}` " f"does not support lookups.")

    return type(
        f"DeterministicEncryptedField{lookup_name}",
        (base_lookup_class,),
        {"get_prep_lookup": get_prep_lookup},
    )


def _register_lookup_classes():
    """Register lookup classes for encrypted fields."""
    for name, lookup in models.Field.class_lookups.items():
        if name != "isnull":
            # Register lookup class for regular encrypted fields
            lookup_class = _create_lookup_class(name, lookup)
            EncryptedField.register_lookup(lookup_class)

            # Register lookup class for deterministic encrypted fields
            deterministic_lookup_class = _create_deterministic_lookup_class(name, lookup)
            DeterministicEncryptedField.register_lookup(deterministic_lookup_class)


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


class EncryptedBooleanField(EncryptedField, models.BooleanField):
    """Encrypted boolean field."""

    pass


class EncryptedIntegerField(EncryptedField, models.IntegerField):
    """Encrypted integer field."""

    pass


class EncryptedPositiveIntegerField(EncryptedField, models.PositiveIntegerField):
    """Encrypted positive integer field."""

    pass


class EncryptedFloatField(EncryptedField, models.FloatField):
    """Encrypted float field."""

    pass


class EncryptedDecimalField(EncryptedField, models.DecimalField):
    """Encrypted decimal field."""

    pass


class EncryptedUUIDField(EncryptedField, models.UUIDField):
    """Encrypted UUID field."""

    pass


class EncryptedJSONField(EncryptedField, models.JSONField):
    """Encrypted JSON field."""

    def get_db_prep_save(self, value: Any, connection: Any) -> Any:
        """Prepare JSON values using JSONField semantics, then encrypt."""
        val = models.JSONField.get_db_prep_save(self, value, connection)
        if val is not None:
            return connection.Database.Binary(
                self._keyset_manager.aead_primitive.encrypt(force_bytes(val), self._aad_callback(self))
            )
        return None

    def from_db_value(
        self,
        value: Any,
        expression: Any,
        connection: Any,
        *args: Any,
    ) -> Any:
        """Convert database value to Python object with JSON decoding."""
        if value is not None:
            decrypted = self._keyset_manager.aead_primitive.decrypt(bytes(value), self._aad_callback(self))
            return models.JSONField.from_db_value(self, force_str(decrypted), expression, connection)
        return None


class EncryptedURLField(EncryptedField, models.URLField):
    """Encrypted URL field."""

    pass


class EncryptedSlugField(EncryptedField, models.SlugField):
    """Encrypted slug field."""

    pass


class EncryptedDateField(EncryptedField, models.DateField):
    """Encrypted date field."""

    pass


class EncryptedDateTimeField(EncryptedField, models.DateTimeField):
    """Encrypted datetime field."""

    pass


class EncryptedBinaryField(EncryptedField, models.BinaryField):
    """Encrypted binary field for storing binary data.

    This field is specifically designed for storing binary data that should
    not be converted to strings during decryption.
    """

    def _to_python_prepare(self, value: bytes) -> bytes:
        """Prepare decrypted value for to_python conversion.

        For binary fields, we return the raw bytes without string conversion.

        Args:
            value: Decrypted bytes value

        Returns:
            bytes: Raw bytes value
        """
        return value


class DeterministicEncryptedField(EncryptedField):
    """A field that uses Deterministic AEAD for searchable encryption.

    Deterministic AEAD provides the same security guarantees as regular AEAD
    but produces the same ciphertext for the same plaintext, making it
    possible to search encrypted data.

    Note: Deterministic encryption is less secure than regular AEAD as it
    reveals patterns in the data. Use only when searchability is required.
    """

    def get_db_prep_save(self, value: Any, connection: Any) -> Any:
        """Prepare the value for saving to the database using deterministic encryption.

        Args:
            value: The value to be saved
            connection: Database connection

        Returns:
            Binary object containing deterministically encrypted data, or None if value is None
        """
        # Call the grandparent's get_db_prep_save to avoid using regular AEAD
        val = super(EncryptedField, self).get_db_prep_save(value, connection)
        if val is not None:
            return connection.Database.Binary(
                self._keyset_manager.daead_primitive.encrypt_deterministically(
                    force_bytes(val), self._aad_callback(self)
                )
            )
        return None

    def from_db_value(
        self,
        value: Any,
        expression: Any,
        connection: Any,
        *args: Any,
    ) -> Any:
        """Convert database value to Python object using deterministic decryption.

        Args:
            value: Raw value from database
            expression: Database expression
            connection: Database connection
            *args: Additional arguments

        Returns:
            Decrypted and converted Python object, or None if value is None
        """
        if value is not None:
            decrypted = self._keyset_manager.daead_primitive.decrypt_deterministically(
                bytes(value), self._aad_callback(self)
            )
            return self.to_python(self._to_python_prepare(decrypted))
        return None


# Deterministic field implementations
class DeterministicEncryptedTextField(DeterministicEncryptedField, models.TextField):
    """Deterministic encrypted text field."""

    pass


class DeterministicEncryptedCharField(DeterministicEncryptedField, models.CharField):
    """Deterministic encrypted character field."""

    pass


class DeterministicEncryptedEmailField(DeterministicEncryptedField, models.EmailField):
    """Deterministic encrypted email field."""

    pass


class DeterministicEncryptedIntegerField(DeterministicEncryptedField, models.IntegerField):
    """Deterministic encrypted integer field."""

    pass


class DeterministicEncryptedUUIDField(DeterministicEncryptedField, models.UUIDField):
    """Deterministic encrypted UUID field."""

    pass


class DeterministicEncryptedBooleanField(DeterministicEncryptedField, models.BooleanField):
    """Deterministic encrypted boolean field."""

    pass


class DeterministicEncryptedDateField(DeterministicEncryptedField, models.DateField):
    """Deterministic encrypted date field."""

    pass


class DeterministicEncryptedDateTimeField(DeterministicEncryptedField, models.DateTimeField):
    """Deterministic encrypted datetime field."""

    pass


# Register lookup classes at module level
_register_lookup_classes()
