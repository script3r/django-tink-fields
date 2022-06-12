from typing import List, TypeVar, Type, Optional, Set, Union

from django.db import models
from django.db import transaction
from django.utils.functional import cached_property
from tink.proto import tink_pb2

from .fields import EncryptedBinaryField
from tink.core import PrimitiveSet, Registry, KeyManager
from tink.core._primitive_set import Entry
from tink.core import crypto_format

__all__ = ["Keyset", "Key"]
P = TypeVar("P")


class Keyset(models.Model):
    name = models.CharField(max_length=100, unique=True)
    type_url = models.CharField(max_length=250)

    @classmethod
    def create(cls, name: str, key_template: tink_pb2.KeyTemplate) -> "Keyset":
        """Create a keyset with one primary key"""
        with transaction.atomic():
            instance = cls(name=name, type_url=key_template.type_url)
            instance.save()

            key = instance.generate_key(key_template)
            key.is_primary = True
            key.save()

        return instance

    def generate_key(self, key_template: tink_pb2.KeyTemplate) -> "Key":
        """Create and save a key"""
        key_data = self.key_manager().new_key_data(key_template)
        key = Key.create_from_keydata(self, key_data, key_template.output_prefix_type)

        return key

    def set_primary_key(self, key: Union["Key", int]):
        key_id = key
        if isinstance(key, Key):
            key_id = key.pk

        with transaction.atomic():
            self.key_set.update(is_primary=False)
            self.key_set.filter(pk=key_id).update(is_primary=True)

    def key_manager(self) -> "KeyManager":
        return Registry.key_manager(self.type_url)

    @property
    def primitive(self) -> P:
        """Get primitive of the stored type"""
        return Registry.wrap(
            self.primitive_set,
            self.key_manager().primitive_class(),
        )

    @cached_property
    def primitive_set(self) -> PrimitiveSet:
        return _DatabasePrimitiveKeyset(self, self.key_manager().primitive_class())

    def export_keyset(self) -> tink_pb2.Keyset:
        return tink_pb2.Keyset(
            primary_key_id=self.key_set.get(is_primary=True).id,
            key=[key.key for key in self.key_set.all()],
        )

    def export_keyset_info(self) -> tink_pb2.KeysetInfo:
        return tink_pb2.KeysetInfo(
            primary_key_id=self.key_set.get(is_primary=True).id,
            key_info=[key.key_info for key in self.key_set.all()],
        )


class _DatabasePrimitiveKeyset(PrimitiveSet[P]):
    _keyset: Keyset

    def __init__(self, keyset: Keyset, primitive_class: Type[P]):
        super().__init__(primitive_class)
        self._keyset = keyset
        del self._primary

    def primitive_from_identifier(self, identifier: bytes) -> List[Entry]:
        for key in (
            self._keyset.key_set.filter(output_prefix=identifier)
            .exclude(id__in=list(self._all_cached_key_ids()))
            .all()
        ):
            self._add_key_to_cache(key)

        return super().primitive_from_identifier(identifier)

    def entry_by_id(self, identifier: bytes, key_id: int) -> Optional[Entry]:
        primitives = self._primitives.get(identifier, [])
        for item in primitives:
            if item.key_id == key_id:
                return item

    def _add_key_to_cache(self, key: "Key"):
        if not self.entry_by_id(key.output_prefix, key.id):
            entries = self._primitives.setdefault(key.output_prefix, [])
            entries.append(key.entry)

    def _add_entry_to_cache(self, entry: Entry):
        entries = self._primitives.setdefault(entry.identifier, [])
        entries.append(entry)  # XXX: This does not check for dupes

    def _all_cached_key_ids(self) -> Set[int]:
        out = set()
        for keys in self._primitives.values():
            for key in keys:
                out.add(key.key_id)

        return out

    def all(self) -> List[List[Entry]]:
        for key in self._keyset.key_set.exclude(
            id__in=list(self._all_cached_key_ids())
        ).all():
            self._add_key_to_cache(key)

        return super().all()

    def add_primitive(self, primitive: P, key: tink_pb2.Keyset.Key) -> Entry:
        assert isinstance(primitive, self._primitive_class)

        key = Key.from_key(self._keyset, key)
        key.save()

        self._add_key_to_cache(key)

        return key.entry

    def set_primary(self, entry: Entry) -> None:
        self._keyset.set_primary_key(entry.key_id)

    def primary(self) -> Entry:
        key = self._keyset.key_set.get(is_primary=True)
        entry = self.entry_by_id(key.output_prefix, key.id)
        if entry:
            return entry

        self._add_key_to_cache(key)
        return key.entry


class Key(models.Model):
    """Key instance in a keyset.

    It is expected that Key is immutable except for is_primary, status field"""

    keyset = models.ForeignKey(Keyset, on_delete=models.CASCADE, editable=False)
    is_primary = models.BooleanField()

    # Serialized KeyData
    key_data = EncryptedBinaryField(editable=False)
    status = models.PositiveIntegerField(choices=tink_pb2.KeyStatusType.items())
    output_prefix_type = models.PositiveIntegerField(
        choices=tink_pb2.OutputPrefixType.items()
    )
    # Output prefix can be derived from output_prefix_type + id, however
    # we store it here to be able to lookup without parsing Tink format ourselves
    output_prefix = models.BinaryField(editable=False)

    @cached_property
    def key(self) -> tink_pb2.Keyset.Key:
        return tink_pb2.Keyset.Key(
            key_data=self.key_data_pb,
            status=self.status,
            key_id=self.id,
            output_prefix_type=self.output_prefix_type,
        )

    @cached_property
    def key_info(self) -> tink_pb2.KeysetInfo.KeyInfo:
        return tink_pb2.KeysetInfo.KeyInfo(
            type_url=self.keyset.type_url,
            status=self.status,
            key_id=self.id,
            output_prefix_type=self.output_prefix_type,
        )

    @property
    def key_data_pb(self) -> tink_pb2.KeyData:
        out = tink_pb2.KeyData()
        out.ParseFromString(self.key_data)
        return out

    @property
    def primitive(self) -> P:
        return Registry.primitive(
            self.key_data_pb,
            self.keyset.key_manager().primitive_class(),
        )

    @cached_property
    def entry(self) -> Entry:
        return Entry(
            primitive=self.primitive,
            identifier=self.output_prefix,
            status=self.status,
            output_prefix_type=self.output_prefix_type,
            key_id=self.id,
        )

    @classmethod
    def from_key(cls, keyset: "Keyset", key: tink_pb2.Keyset.Key):
        return cls(
            id=key.key_id,
            is_primary=False,
            keyset=keyset,
            data=key.key_data.SerializeToString(),
            status=key.status,
            output_prefix=crypto_format.output_prefix(key),
            output_prefix_type=key.output_prefix_type,
        )

    @classmethod
    def create_from_keydata(
        cls,
        keyset: "Keyset",
        keydata: tink_pb2.KeyData,
        output_prefix_type: tink_pb2.OutputPrefixType,
    ):
        with transaction.atomic():
            out = cls(
                keyset=keyset,
                is_primary=False,
                key_data=keydata.SerializeToString(),
                status=tink_pb2.ENABLED,
                output_prefix_type=output_prefix_type,
            )
            out.save()
            out.refresh_from_db()
            out.output_prefix = crypto_format.output_prefix(out.key)
            out.save()

        return out

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="one_primary_per_keyset",
                fields=("keyset", "is_primary"),
                condition=models.Q(is_primary=True),
            ),
        ]
