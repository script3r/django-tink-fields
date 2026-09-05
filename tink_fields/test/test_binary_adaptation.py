"""Use the real PostgreSQL driver adapter without needing a server."""

from unittest.mock import patch

import pytest
from django.db import connection
from django.db.backends.postgresql.base import DatabaseWrapper

from tink_fields import EncryptedBinaryField

from . import models


@pytest.mark.parametrize("value", [b"", b"binary\x00\xff", bytearray(b"mutable\xff"), memoryview(b"view\x00")])
def test_postgresql_binary_adapter_wraps_ciphertext_only(value):
    postgres = DatabaseWrapper({})
    field = EncryptedBinaryField()
    with patch.object(postgres.Database, "Binary", wraps=postgres.Database.Binary) as binary:
        adapted = field.get_db_prep_save(value, postgres)
    assert field.from_db_value(adapted.obj, None, postgres) == bytes(value)
    assert binary.call_count == 1
    assert bytes(adapted.obj) != bytes(value)


def test_postgresql_binary_null_skips_adaptation():
    postgres = DatabaseWrapper({})
    with patch.object(postgres.Database, "Binary", wraps=postgres.Database.Binary) as binary:
        assert EncryptedBinaryField().get_db_prep_save(None, postgres) is None
    binary.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("value", [b"", b"binary\x00\xff", bytearray(b"mutable\xff"), memoryview(b"view\x00")])
def test_binary_buffer_values_round_trip_in_database(value):
    instance = models.EncryptedBinary.objects.create(value=value)
    instance.refresh_from_db()
    assert instance.value == bytes(value)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT value FROM {models.EncryptedBinary._meta.db_table} WHERE id = %s", [instance.pk])
        assert bytes(cursor.fetchone()[0]) != bytes(value)


@pytest.mark.parametrize("value", ["not binary", 3])
def test_non_buffer_values_are_rejected(value):
    with pytest.raises(TypeError):
        EncryptedBinaryField().get_db_prep_save(value, connection)
