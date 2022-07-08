from dataclasses import dataclass
from os.path import exists
from typing import Optional, TypeVar, Type, TYPE_CHECKING
from django.utils.functional import cached_property

from django.core.exceptions import ImproperlyConfigured
from tink import (
    aead,
    KeysetHandle,
    JsonKeysetReader,
    cleartext_keyset_handle,
    read_keyset_handle,
)

if TYPE_CHECKING:
    from .models import Keyset

P = TypeVar("P")


@dataclass
class KeysetConfig:
    path: Optional[str] = None
    db_name: Optional[str] = None
    master_key_aead: Optional[aead.Aead] = None
    cleartext: bool = False

    def validate(self):
        if not self.path and not self.db_name:
            raise ImproperlyConfigured("Keyset path or db_name must be set")
        if self.db_name and self.path:
            raise ImproperlyConfigured("Only one of keyset path or db_name must be set")

        if self.path:
            if not exists(self.path):
                raise ImproperlyConfigured(f"Keyset {self.path} does not exist")

            if not self.cleartext and self.master_key_aead is None:
                raise ImproperlyConfigured(
                    f"Encrypted keysets must specify `master_key_aead`"
                )

    def primitive(self, cls: Type[P]) -> P:
        if self.path:
            return self._load_from_path.primitive(cls)
        if self.db_name:
            return self._load_from_db.primitive(cls)

    @cached_property
    def _load_from_path(self) -> KeysetHandle:
        with open(self.path, "r") as f:
            reader = JsonKeysetReader(f.read())
            if self.cleartext:
                return cleartext_keyset_handle.read(reader)
            return read_keyset_handle(reader, self.master_key_aead)

    @cached_property
    def _load_from_db(self) -> "Keyset":
        from .models import Keyset

        keyset = Keyset.objects.get(name=self.db_name)
        return keyset
