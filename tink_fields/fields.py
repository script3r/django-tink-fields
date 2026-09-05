"""
Django Tink Fields - Encrypted model fields using Google Tink.

This module provides encrypted Django model fields that use Google Tink
for cryptographic operations, ensuring data confidentiality and integrity.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from os import PathLike
from pathlib import Path
from threading import RLock
from typing import Any, ClassVar, TypeVar, cast
from weakref import WeakSet

from django.conf import settings
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import models
from django.db.models.lookups import Exact, IsNull, Lookup
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.functional import cached_property
from tink import JsonKeysetReader, TinkError, aead, cleartext_keyset_handle, daead, read_keyset_handle


def _register_tink_primitives() -> None:
    """Register Tink primitives so direct module imports are safe."""
    aead.register()
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
    "clear_keyset_cache",
]


# Constants
UNSUPPORTED_PROPERTIES = frozenset(["primary_key", "db_index", "unique", "db_default"])
DEFAULT_KEYSET = "default"
DAEAD_AVAILABLE = True

AADCallback = Callable[[models.Field], bytes]


def _default_aad_callback(field: models.Field) -> bytes:
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

    path: str | PathLike[str]
    master_key_aead: aead.Aead | None = None
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

        if not Path(self.path).is_file():
            raise ImproperlyConfigured(f"Keyset `{self.path}` is not a readable file.")

        if not isinstance(self.cleartext, bool):
            raise ImproperlyConfigured("Keyset option `cleartext` must be a boolean.")

        if not self.cleartext and self.master_key_aead is None:
            raise ImproperlyConfigured("Encrypted keysets must specify `master_key_aead`.")


Primitive = TypeVar("Primitive", aead.Aead, daead.DeterministicAead)


@dataclass
class _KeysetEntry:
    handle: Any
    primitives: dict[type[Any], Any] = field(default_factory=dict)


class KeysetManager:
    """Manages Tink keyset handles and primitives.

    This class provides a centralized way to manage keyset handles and
    their associated primitives, with proper caching to avoid memory leaks.
    """

    _cache_size: ClassVar[int] = 32
    _cache_lock: ClassVar[RLock] = RLock()
    _handle_cache: ClassVar[OrderedDict[tuple[Any, ...], _KeysetEntry]] = OrderedDict()
    _managers: ClassVar[WeakSet[KeysetManager]] = WeakSet()

    def __init__(self, keyset_name: str, aad_callback: AADCallback = _default_aad_callback) -> None:
        """Initialize the keyset manager.

        Args:
            keyset_name: Name of the keyset to use
            aad_callback: Callable for additional authenticated data
        """
        self.keyset_name = keyset_name
        self.aad_callback = aad_callback
        self._entry: _KeysetEntry | None = None

        with self._cache_lock:
            self._managers.add(self)

    def _get_config(self) -> Mapping[str, Mapping[str, Any]]:
        """Get the Tink fields configuration from Django settings.

        Returns:
            Dictionary containing keyset configurations

        Raises:
            ImproperlyConfigured: If TINK_FIELDS_CONFIG is not found in settings
        """
        config = getattr(settings, "TINK_FIELDS_CONFIG", None)
        if config is None:
            raise ImproperlyConfigured("Could not find `TINK_FIELDS_CONFIG` attribute in settings.")
        if not isinstance(config, Mapping):
            raise ImproperlyConfigured("`TINK_FIELDS_CONFIG` must be a mapping of keyset names to options.")
        return config

    def _get_keyset_config(self) -> KeysetConfig:
        """Return and validate this manager's keyset configuration."""
        config = self._get_config()
        if self.keyset_name not in config:
            raise ImproperlyConfigured(
                f"Could not find configuration for keyset `{self.keyset_name}` in `TINK_FIELDS_CONFIG`."
            )

        options = config[self.keyset_name]
        if not isinstance(options, Mapping):
            raise ImproperlyConfigured(f"Configuration for keyset `{self.keyset_name}` must be a mapping.")
        try:
            return KeysetConfig(**options)
        except TypeError as error:
            raise ImproperlyConfigured(f"Invalid configuration for keyset `{self.keyset_name}`: {error}") from error

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached handles and primitives, for example after key rotation."""
        with cls._cache_lock:
            cls._handle_cache.clear()
            for manager in list(cls._managers):
                manager._entry = None

    def _get_keyset_entry(self) -> _KeysetEntry:
        """Load or reuse a keyset entry while holding the cache lock."""
        if self._entry is not None:
            return self._entry

        keyset_config = self._get_keyset_config()
        keyset_path = Path(keyset_config.path).expanduser().resolve()
        try:
            stat = keyset_path.stat()
        except OSError as error:
            raise ImproperlyConfigured(f"Could not load keyset `{self.keyset_name}`.") from error
        cache_key = (
            str(keyset_path),
            stat.st_mtime_ns,
            stat.st_size,
            keyset_config.cleartext,
            keyset_config.master_key_aead,
        )
        try:
            hash(cache_key)
        except TypeError:
            cache_key = ()

        cached_entry = self._handle_cache.get(cache_key) if cache_key else None
        if cached_entry is not None:
            self._handle_cache.move_to_end(cache_key)
            self._entry = cached_entry
        else:
            try:
                reader = JsonKeysetReader(keyset_path.read_text(encoding="utf-8"))
                if keyset_config.cleartext:
                    handle = cleartext_keyset_handle.read(reader)
                else:
                    master_key_aead = keyset_config.master_key_aead
                    assert master_key_aead is not None
                    handle = read_keyset_handle(reader, master_key_aead)
            except (OSError, TinkError) as error:
                raise ImproperlyConfigured(f"Could not load keyset `{self.keyset_name}`.") from error

            self._entry = _KeysetEntry(handle)
            if cache_key:
                self._handle_cache[cache_key] = self._entry
                self._handle_cache.move_to_end(cache_key)
                while len(self._handle_cache) > self._cache_size:
                    self._handle_cache.popitem(last=False)

        return self._entry

    def _get_tink_keyset_handle(self) -> Any:
        """Return this manager's configured handle."""
        with self._cache_lock:
            return self._get_keyset_entry().handle

    def _get_primitive(self, primitive_class: type[Primitive]) -> Primitive:
        # Keep construction and publication atomic with respect to clear_cache().
        # cached_property publishes after its getter returns, outside this lock.
        with self._cache_lock:
            entry = self._get_keyset_entry()
            if primitive_class not in entry.primitives:
                entry.primitives[primitive_class] = entry.handle.primitive(primitive_class)
            return entry.primitives[primitive_class]

    @property
    def aead_primitive(self) -> aead.Aead:
        """Get the AEAD primitive shared by managers using this keyset."""
        return self._get_primitive(aead.Aead)

    @property
    def daead_primitive(self) -> daead.DeterministicAead:
        """Get the deterministic AEAD primitive shared by this keyset."""
        try:
            return self._get_primitive(daead.DeterministicAead)
        except TinkError as error:
            raise ImproperlyConfigured(
                "Current keyset does not support deterministic AEAD. "
                "Please use a keyset that contains deterministic AEAD keys."
            ) from error


def clear_keyset_cache() -> None:
    """Clear all in-process keyset handles and primitives.

    Call this after replacing a keyset file when a process must adopt the new
    primary key without restarting.
    """
    KeysetManager.clear_cache()


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
            if (prop == "db_default" and prop in kwargs) or kwargs.get(prop):
                raise ImproperlyConfigured(f"Field `{self.__class__.__name__}` does not support property `{prop}`.")

        # Extract custom parameters
        self._keyset = kwargs.pop("keyset", DEFAULT_KEYSET)
        self._aad_callback = kwargs.pop("aad_callback", DEFAULT_AAD_CALLBACK)
        if not isinstance(self._keyset, str) or not self._keyset:
            raise ImproperlyConfigured("`keyset` must be a non-empty string.")
        if not callable(self._aad_callback):
            raise ImproperlyConfigured("`aad_callback` must be callable.")
        self._aad_callback = cast(AADCallback, self._aad_callback)

        # Call parent constructor first
        super().__init__(*args, **kwargs)

        self._keyset_manager = KeysetManager(self._keyset, self._aad_callback)

    def deconstruct(self) -> tuple[str | None, str, Sequence[Any], dict[str, Any]]:
        """Serialize encryption options into Django migrations."""
        name, path, args, kwargs = super().deconstruct()
        if self._keyset != DEFAULT_KEYSET:
            kwargs["keyset"] = self._keyset
        if self._aad_callback is not DEFAULT_AAD_CALLBACK:
            kwargs["aad_callback"] = self._aad_callback
        return name, path, args, kwargs

    def _to_python_prepare(self, value: bytes) -> str:
        """Prepare decrypted value for to_python conversion.

        Args:
            value: Decrypted bytes value

        Returns:
            str: String representation of the value
        """
        return force_str(value)

    def _get_aead_primitive(self) -> aead.Aead:
        """Get the AEAD primitive for encryption/decryption operations.

        This method is kept for backward compatibility with tests.

        Returns:
            aead.Aead: The AEAD primitive instance
        """
        return self._keyset_manager.aead_primitive

    def _get_aad(self) -> bytes:
        """Return validated associated authenticated data for this field."""
        aad = self._aad_callback(self)
        if not isinstance(aad, bytes):
            raise ImproperlyConfigured(
                f"`aad_callback` for {self.__class__.__name__} must return bytes, got {type(aad).__name__}."
            )
        return aad

    @property
    def _keyset_handle(self) -> Any:
        """Get the keyset handle for backward compatibility.

        Returns:
            KeysetHandle: The configured Tink keyset handle
        """
        return self._keyset_manager._get_tink_keyset_handle()

    def get_internal_type(self) -> str:
        """Return the internal Django field type.

        Returns:
            str: Always returns "BinaryField" for encrypted fields
        """
        return self._internal_type

    def get_lookup(self, lookup_name: str) -> type[Lookup]:
        """Select only operations that are meaningful for ciphertext."""
        if lookup_name == "isnull":
            return IsNull
        if lookup_name == "exact":
            return EncryptedExact
        raise FieldError(f"{self.__class__.__name__} `{lookup_name}` does not support lookups.")

    def get_transform(self, lookup_name: str) -> None:
        """Prevent inherited date and JSON transforms from inspecting ciphertext."""
        raise FieldError(f"{self.__class__.__name__} `{lookup_name}` does not support lookups.")

    def get_db_prep_save(self, value: Any, connection: Any) -> Any:
        """Prepare the value for saving to the database.

        Args:
            value: The value to be saved
            connection: Database connection

        Returns:
            Binary object containing encrypted data, or None if value is None
        """
        if hasattr(value, "resolve_expression"):
            raise FieldError(f"{self.__class__.__name__} does not support database expressions.")
        val = self._prepare_value_for_database(value, connection)
        if val is not None:
            return connection.Database.Binary(
                self._keyset_manager.aead_primitive.encrypt(force_bytes(val), self._get_aad())
            )
        return None

    def _prepare_value_for_database(self, value: Any, connection: Any) -> Any:
        """Apply the concrete Django field's database preparation semantics."""
        return super().get_db_prep_save(value, connection)

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
            decrypted = self._keyset_manager.aead_primitive.decrypt(bytes(value), self._get_aad())
            return self._convert_decrypted_value(decrypted, connection)
        return None

    def _convert_decrypted_value(self, value: bytes, connection: Any) -> Any:
        """Restore the Python value after decrypting a binary database value."""
        return self.to_python(self._to_python_prepare(value))

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

    def __repr__(self) -> str:
        """Return string representation of the field.

        Returns:
            str: String representation including keyset name
        """
        return f"<{self.__class__.__name__}: keyset={self._keyset}>"


class EncryptedExact(Exact):
    """Allow Django to rewrite equality with None to an IS NULL lookup."""

    def get_prep_lookup(self) -> Any:
        if self.rhs is None:
            return None
        field = self.lhs.output_field
        raise FieldError(f"{field.__class__.__name__} `exact` does not support lookups.")


class DeterministicEncryptedExact(Exact):
    """Compare ciphertext prepared using the same conversion as writes."""

    def get_prep_lookup(self) -> Any:
        if hasattr(self.rhs, "resolve_expression"):
            raise FieldError("Deterministic encrypted lookups do not support database expressions.")
        return self.rhs

    def get_db_prep_lookup(self, value: Any, connection: Any) -> tuple[str, list[Any]]:
        field = self.lhs.output_field
        prepared_value = field._prepare_value_for_database(value, connection)
        if prepared_value is None:
            return "%s", [None]
        encrypted_value = field._keyset_manager.daead_primitive.encrypt_deterministically(
            force_bytes(prepared_value), field._get_aad()
        )
        return "%s", [connection.Database.Binary(encrypted_value)]

    def as_sql(self, compiler: Any, connection: Any) -> tuple[str, tuple[Any, ...]]:
        """Render equality without Django's plaintext Boolean shortcut."""
        lhs_sql, lhs_params = self.process_lhs(compiler, connection)
        rhs_sql, rhs_params = self.process_rhs(compiler, connection)
        rhs_sql = self.get_rhs_op(connection, rhs_sql)
        return f"{lhs_sql} {rhs_sql}", (*lhs_params, *rhs_params)


def _restore_datetime_timezone(value: datetime, connection: Any) -> datetime:
    # Binary columns skip the backend's DateTimeField result converters.
    # Use the database timezone that was used to prepare existing ciphertext.
    if settings.USE_TZ and timezone.is_naive(value):
        return timezone.make_aware(value, connection.timezone)
    return value


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

    def _prepare_value_for_database(self, value: Any, connection: Any) -> Any:
        """Serialize JSON before database-specific adapters can wrap it."""
        if value is None:
            return None
        return json.dumps(value, cls=self.encoder)

    def from_db_value(
        self,
        value: Any,
        expression: Any,
        connection: Any,
        *args: Any,
    ) -> Any:
        """Convert database value to Python object with JSON decoding."""
        if value is not None:
            decrypted = self._keyset_manager.aead_primitive.decrypt(bytes(value), self._get_aad())
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

    def _convert_decrypted_value(self, value: bytes, connection: Any) -> datetime:
        return _restore_datetime_timezone(super()._convert_decrypted_value(value, connection), connection)


class EncryptedBinaryField(EncryptedField, models.BinaryField):
    """Encrypted binary field for storing binary data.

    This field is specifically designed for storing binary data that should
    not be converted to strings during decryption.
    """

    def _prepare_value_for_database(self, value: Any, connection: Any) -> bytes | None:
        """Keep buffer contents as plaintext; adapt only the final ciphertext."""
        value = self.get_prep_value(value)
        if value is None:
            return None
        return bytes(memoryview(value))

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

    _unsupported_properties = frozenset(["primary_key", "db_default"])

    def get_lookup(self, lookup_name: str) -> type[Lookup]:
        if lookup_name == "exact":
            return DeterministicEncryptedExact
        return super().get_lookup(lookup_name)

    def get_db_prep_save(self, value: Any, connection: Any) -> Any:
        """Prepare the value for saving to the database using deterministic encryption.

        Args:
            value: The value to be saved
            connection: Database connection

        Returns:
            Binary object containing deterministically encrypted data, or None if value is None
        """
        if hasattr(value, "resolve_expression"):
            raise FieldError(f"{self.__class__.__name__} does not support database expressions.")
        val = self._prepare_value_for_database(value, connection)
        if val is not None:
            return connection.Database.Binary(
                self._keyset_manager.daead_primitive.encrypt_deterministically(force_bytes(val), self._get_aad())
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
            decrypted = self._keyset_manager.daead_primitive.decrypt_deterministically(bytes(value), self._get_aad())
            return self._convert_decrypted_value(decrypted, connection)
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

    def _convert_decrypted_value(self, value: bytes, connection: Any) -> datetime:
        return _restore_datetime_timezone(super()._convert_decrypted_value(value, connection), connection)
