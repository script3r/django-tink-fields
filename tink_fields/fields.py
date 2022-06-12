from typing import Any, Callable, TYPE_CHECKING, Dict
from django.db import models
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.utils.functional import cached_property
from tink import (
    KeysetHandle,
    aead,
    daead,
)
from django.conf import settings
from django.utils.encoding import force_bytes, force_str

from tink_fields.config import KeysetConfig

if TYPE_CHECKING:
    from django.db.backends.base.base import BaseDatabaseWrapper


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
    "DeterministicEncryptedCharField",
    "DeterministicEncryptedEmailField",
    "DeterministicEncryptedIntegerField",
]

_config: Dict[str, KeysetConfig] = {}


def _get_config(keyset: str) -> KeysetConfig:
    global _config

    if keyset in _config:
        return _config[keyset]

    config = getattr(settings, "TINK_FIELDS_CONFIG", None)
    if config is None:
        raise ImproperlyConfigured(
            f"Could not find `TINK_FIELDS_CONFIG` attribute in settings"
        )

    if keyset not in config:
        raise ImproperlyConfigured(
            f"Could not find configuration for keyset `{keyset}` in `TINK_FIELDS_CONFIG`"
        )

    keyset_config = KeysetConfig(**config[keyset])
    keyset_config.validate()
    _config[keyset] = keyset_config

    return keyset_config


class BaseEncryptedField(models.Field):
    _unsupported_properties = ["primary_key", "db_index", "unique"]
    _internal_type = "BinaryField"

    _keyset: str
    _keyset_config: KeysetConfig
    _aad_callback: Callable[[models.Field], bytes]

    def __init__(self, *args, **kwargs):
        for prop in EncryptedField._unsupported_properties:
            if prop in kwargs:
                raise ImproperlyConfigured(
                    f"Field `{self.__class__.__name__}` does not support property `{prop}`"
                )

        self._keyset = kwargs.pop("keyset", "default")
        self._keyset_config = self._get_config()
        self._aad_callback = kwargs.pop("aad_callback", lambda x: b"")

        super(BaseEncryptedField, self).__init__(*args, **kwargs)

    def _get_config(self) -> KeysetConfig:
        return _get_config(self._keyset)

    def get_internal_type(self) -> str:
        return self._internal_type

    @cached_property
    def validators(self):
        # Temporarily pretend to be whatever type of field we're masquerading
        # as, for purposes of constructing validators (needed for
        # IntegerField and subclasses).
        self.__dict__["_internal_type"] = super(
            BaseEncryptedField, self
        ).get_internal_type()
        try:
            return super(BaseEncryptedField, self).validators
        finally:
            del self.__dict__["_internal_type"]

    def to_python_prepare(self, value: bytes) -> Any:
        if isinstance(self, models.BinaryField):
            return value

        return force_str(value)


class EncryptedField(BaseEncryptedField):
    """A field that uses Tink primitives to protect the confidentiality and integrity of data"""

    @cached_property
    def _aead_primitive(self) -> aead.Aead:
        return self._keyset_config.primitive(aead.Aead)

    def get_db_prep_save(self, value: Any, connection: "BaseDatabaseWrapper") -> Any:
        val = super(EncryptedField, self).get_db_prep_save(value, connection)
        if val is not None:
            return connection.Database.Binary(
                self._aead_primitive.encrypt(force_bytes(val), self._aad_callback(self))
            )

    def from_db_value(self, value, expression, connection, *args):
        if value is not None:
            return self.to_python(
                self.to_python_prepare(
                    self._aead_primitive.decrypt(bytes(value), self._aad_callback(self))
                )
            )


class DeterministicEncryptedField(BaseEncryptedField):
    """Field that is similar to EncryptedField, but support exact match lookups"""

    _unsupported_properties = []

    @cached_property
    def _daead_primitive(self) -> daead.DeterministicAead:
        return self._keyset_config.primitive(daead.DeterministicAead)

    def get_db_prep_value(
        self, value: Any, connection: "BaseDatabaseWrapper", prepared=False
    ) -> Any:
        val = super(DeterministicEncryptedField, self).get_db_prep_value(
            value, connection, prepared
        )
        if val is not None:
            return connection.Database.Binary(
                self._daead_primitive.encrypt_deterministically(
                    force_bytes(val), self._aad_callback(self)
                )
            )

    def from_db_value(self, value, expression, connection, *args):
        if value is not None:
            return self.to_python(
                self.to_python_prepare(
                    self._daead_primitive.decrypt_deterministically(
                        bytes(value), self._aad_callback(self)
                    )
                )
            )


def get_prep_lookup(self):
    """Raise errors for unsupported lookups"""
    raise FieldError(
        "{} `{}` does not support lookups".format(
            self.lhs.field.__class__.__name__, self.lookup_name
        )
    )


lookup_allowlist = {
    (object, "isnull"),
    (DeterministicEncryptedField, "exact"),  # TODO: Support key rotation
}


def is_lookup_allowed(cls, name) -> bool:
    for item in lookup_allowlist:
        if item[1] == name and issubclass(cls, item[0]):
            return True
    return False


# Override all lookups except in lookup_allowlist to get_prep_lookup
for name, lookup in models.Field.class_lookups.items():
    for cls in (EncryptedField, DeterministicEncryptedField):
        if is_lookup_allowed(cls, name):
            continue

        lookup_class = type(
            cls.__name__ + "__" + name, (lookup,), {"get_prep_lookup": get_prep_lookup}
        )
        cls.register_lookup(lookup_class)


class EncryptedTextField(EncryptedField, models.TextField):
    pass


class EncryptedCharField(EncryptedField, models.CharField):
    pass


class EncryptedEmailField(EncryptedField, models.EmailField):
    pass


class EncryptedIntegerField(EncryptedField, models.IntegerField):
    pass


class EncryptedDateField(EncryptedField, models.DateField):
    pass


class EncryptedDateTimeField(EncryptedField, models.DateTimeField):
    pass


class EncryptedBinaryField(EncryptedField, models.BinaryField):
    """Encrypted raw binary data, must be under 2^32 bytes (4.295GB)"""


class DeterministicEncryptedCharField(DeterministicEncryptedField, models.CharField):
    pass


class DeterministicEncryptedEmailField(DeterministicEncryptedField, models.EmailField):
    pass


class DeterministicEncryptedIntegerField(
    DeterministicEncryptedField, models.IntegerField
):
    pass
