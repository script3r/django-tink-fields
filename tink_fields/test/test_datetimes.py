"""Timezone conversions must survive storage in a binary column."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.test import override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes

from tink_fields import DeterministicEncryptedDateTimeField, EncryptedDateTimeField

from . import models


@pytest.mark.django_db
@pytest.mark.parametrize("model", [models.EncryptedDateTime, models.DeterministicEncryptedDateTime])
@pytest.mark.parametrize("database_timezone", ["UTC", "Asia/Kolkata"])
@override_settings(USE_TZ=True, TIME_ZONE="America/New_York")
def test_aware_datetime_round_trip_and_resave(model, database_timezone):
    original = datetime(2026, 9, 5, 12, 34, 56, 123456, tzinfo=ZoneInfo("Asia/Tokyo"))
    with patch.object(connection, "timezone", ZoneInfo(database_timezone)):
        instance = model.objects.create(value=original)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT value FROM {model._meta.db_table} WHERE id = %s", [instance.pk])
            ciphertext = bytes(cursor.fetchone()[0])
        assert force_bytes(str(original)) not in ciphertext

        instance.refresh_from_db()
        assert timezone.is_aware(instance.value)
        assert instance.value == original
        assert model.objects.values_list("value", flat=True).get(pk=instance.pk) == original

        instance.save()
        instance.refresh_from_db()
        assert instance.value == original
        if model is models.DeterministicEncryptedDateTime:
            assert model.objects.get(value=original).pk == instance.pk
            assert model.objects.get(value=instance.value).pk == instance.pk
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT value FROM {model._meta.db_table} WHERE id = %s", [instance.pk])
                assert bytes(cursor.fetchone()[0]) == ciphertext


@pytest.mark.parametrize("field_cls", [EncryptedDateTimeField, DeterministicEncryptedDateTimeField])
@pytest.mark.parametrize("plaintext", ["2026-09-05 03:04:05.123456", "2026-09-05 08:34:05.123456+05:30"])
@override_settings(USE_TZ=True, TIME_ZONE="America/New_York")
def test_existing_datetime_ciphertext_remains_readable(field_cls, plaintext):
    deterministic = field_cls is DeterministicEncryptedDateTimeField
    field = field_cls(keyset="deterministic" if deterministic else "default")
    if deterministic:
        primitive = field._keyset_manager.daead_primitive
        ciphertext = primitive.encrypt_deterministically(force_bytes(plaintext), b"")
    else:
        ciphertext = field._keyset_manager.aead_primitive.encrypt(force_bytes(plaintext), b"")
    result = field.from_db_value(ciphertext, None, connection)
    assert result == datetime(2026, 9, 5, 3, 4, 5, 123456, tzinfo=ZoneInfo("UTC"))


@pytest.mark.parametrize("field_cls", [EncryptedDateTimeField, DeterministicEncryptedDateTimeField])
@pytest.mark.parametrize("value", [None, datetime(2026, 9, 5, 12, 34, 56)])
@override_settings(USE_TZ=False)
def test_naive_datetime_and_null_round_trip(field_cls, value):
    field = field_cls(keyset="deterministic" if field_cls is DeterministicEncryptedDateTimeField else "default")
    assert field.from_db_value(field.get_db_prep_save(value, connection), None, connection) == value
