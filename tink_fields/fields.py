from functools import lru_cache
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
from django.db import models
from django.core.exceptions import FieldError, ImproperlyConfigured
from tink import (
    KeysetHandle,
    cleartext_keyset_handle,
    read_keyset_handle,
    JsonKeysetReader,
    aead,
    daead,
)
from django.conf import settings
from dataclasses import dataclass
from os.path import exists
from django.utils.encoding import force_bytes, force_str

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
    "DeterministicEncryptedField",
    "DeterministicEncryptedCharField",
    "DeterministicEncryptedEmailField",
    "DeterministicEncryptedIntegerField",
]


@dataclass
class KeysetConfig:
    path: str
    master_key_aead: Optional[aead.Aead] = None
    cleartext: bool = False

    def validate(self):
        if not self.path:
            raise ImproperlyConfigured("Keyset path cannot be None or empty")

        if not exists(self.path):
            raise ImproperlyConfigured(f"Keyset {self.path} does not exist")

        if not self.cleartext and self.master_key_aead is None:
            raise ImproperlyConfigured(
                f"Encrypted keysets must specify `master_key_aead`"
            )


class BaseEncryptedField(models.Field):
    _unsupported_properties = ["primary_key", "db_index", "unique"]
    _internal_type = "BinaryField"

    _keyset: str
    _keyset_handle: KeysetHandle
    _aad_callback: Callable[[models.Field], bytes]

    def __init__(self, *args, **kwargs):
        for prop in EncryptedField._unsupported_properties:
            if prop in kwargs:
                raise ImproperlyConfigured(
                    f"Field `{self.__class__.__name__}` does not support property `{prop}`"
                )

        self._keyset = kwargs.pop("keyset", "default")
        self._keyset_handle = self._get_tink_keyset_handle()
        self._aad_callback = kwargs.pop("aad_callback", lambda x: b"")

        super(BaseEncryptedField, self).__init__(*args, **kwargs)

    def _get_config(self) -> Dict[str, Any]:
        config = getattr(settings, "TINK_FIELDS_CONFIG", None)
        if config is None:
            raise ImproperlyConfigured(
                f"Could not find `TINK_FIELDS_CONFIG` attribute in settings"
            )
        return config

    def _get_tink_keyset_handle(self) -> KeysetHandle:
        """Read the configuration for the requested keyset and return a respective keyset handle"""
        config = self._get_config()

        if self._keyset not in config:
            raise ImproperlyConfigured(
                f"Could not find configuration for keyset `{self._keyset}` in `TINK_FIELDS_CONFIG`"
            )

        keyset_config = KeysetConfig(**config[self._keyset])
        keyset_config.validate()

        with open(keyset_config.path, "r") as f:
            reader = JsonKeysetReader(f.read())
            if keyset_config.cleartext:
                return cleartext_keyset_handle.read(reader)
            return read_keyset_handle(reader, keyset_config.master_key_aead)

    def get_internal_type(self) -> str:
        return self._internal_type

    @property
    @lru_cache(maxsize=None)
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


class EncryptedField(BaseEncryptedField):
    """A field that uses Tink primitives to protect the confidentiality and integrity of data"""

    @lru_cache(maxsize=None)
    def _get_aead_primitive(self) -> aead.Aead:
        return self._keyset_handle.primitive(aead.Aead)

    def get_db_prep_save(self, value: Any, connection: "BaseDatabaseWrapper") -> Any:
        val = super(EncryptedField, self).get_db_prep_save(value, connection)
        if val is not None:
            return connection.Database.Binary(
                self._get_aead_primitive().encrypt(
                    force_bytes(val), self._aad_callback(self)
                )
            )

    def from_db_value(self, value, expression, connection, *args):
        if value is not None:
            return self.to_python(
                force_str(
                    self._get_aead_primitive().decrypt(
                        bytes(value), self._aad_callback(self)
                    )
                )
            )


class DeterministicEncryptedField(BaseEncryptedField):
    """Field that is similar to EncryptedField, but support exact match lookups"""

    _unsupported_properties = []

    @lru_cache(maxsize=None)
    def _get_daead_primitive(self) -> daead.DeterministicAead:
        return self._keyset_handle.primitive(daead.DeterministicAead)

    def get_db_prep_value(
        self, value: Any, connection: "BaseDatabaseWrappr", prepared=False
    ) -> Any:

        val = super(DeterministicEncryptedField, self).get_db_prep_value(
            value, connection, prepared
        )
        if val is not None:
            return connection.Database.Binary(
                self._get_daead_primitive().encrypt_deterministically(
                    force_bytes(val), self._aad_callback(self)
                )
            )

    def from_db_value(self, value, expression, connection, *args):
        if value is not None:
            return self.to_python(
                force_str(
                    self._get_daead_primitive().decrypt_deterministically(
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
    (DeterministicEncryptedField, "exact"),
}


def is_lookup_allowed(cls, name) -> bool:
    for item in lookup_allowlist:
        if item[1] == name and isinstance(cls, item[0]):
            return True
    return False


# Override all lookups except in lookup_allowlist to get_prep_lookup
for name, lookup in models.Field.class_lookups.items():
    for cls in (EncryptedField, DeterministicEncryptedField):
        if not is_lookup_allowed(cls, name):
            continue

        lookup_class = type(
            cls.__name__ + name, (lookup,), {"get_prep_lookup": get_prep_lookup}
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


class DeterministicEncryptedCharField(DeterministicEncryptedField, models.CharField):
    pass


class DeterministicEncryptedEmailField(DeterministicEncryptedField, models.EmailField):
    pass


class DeterministicEncryptedIntegerField(
    DeterministicEncryptedField, models.IntegerField
):
    pass
