"""Encrypted columns must never inherit plaintext lookups or transforms."""

import pytest
from django.core.exceptions import FieldError
from django.db import connection
from django.db.models import Field, Lookup
from django.test.utils import register_lookup

from . import models


@pytest.mark.parametrize(
    "model, lookup, value",
    [
        (models.EncryptedExtended, "payload__has_key", "secret"),
        (models.EncryptedExtended, "payload__has_keys", ["secret"]),
        (models.EncryptedExtended, "payload__secret", "value"),
        (models.EncryptedExtended, "payload__secret__isnull", True),
        (models.EncryptedDate, "value__year", 2026),
        (models.EncryptedDateTime, "value__date", "2026-09-05"),
        (models.DeterministicEncryptedExtended, "day__year", 2026),
        (models.DeterministicEncryptedExtended, "moment__date", "2026-09-05"),
    ],
)
def test_plaintext_lookups_and_transforms_are_rejected(model, lookup, value):
    with pytest.raises(FieldError, match="does not support lookups"):
        model.objects.filter(**{lookup: value})


@pytest.mark.parametrize("lookup", ["payload__secret", "payload__secret__nested"])
def test_json_projection_transforms_are_rejected(lookup):
    with pytest.raises(FieldError, match="Cannot resolve keyword"):
        models.EncryptedExtended.objects.values(lookup)


@pytest.mark.parametrize("model", [models.EncryptedText, models.DeterministicEncryptedText])
def test_late_registered_lookup_cannot_bypass_encryption_guards(model):
    class PlaintextLookup(Lookup):
        lookup_name = "plaintext_probe"

        def as_sql(self, compiler, connection):
            return "1 = 1", []

    with register_lookup(Field, PlaintextLookup), pytest.raises(FieldError, match="does not support lookups"):
        model.objects.filter(value__plaintext_probe="secret")


@pytest.mark.django_db
@pytest.mark.parametrize("model", [models.EncryptedNullable, models.DeterministicEncryptedTextNullable])
def test_null_lookups_keep_sql_null_semantics(model):
    instance = model.objects.create(value=None)
    assert model.objects.get(value=None).pk == instance.pk
    assert model.objects.get(value__isnull=True).pk == instance.pk
    assert not model.objects.filter(value__isnull=False).exists()
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT value FROM {model._meta.db_table} WHERE id = %s", [instance.pk])
        assert cursor.fetchone()[0] is None
