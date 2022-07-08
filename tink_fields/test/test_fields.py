from datetime import date, datetime

from django.db import connection
from django.utils.encoding import force_bytes
import pytest
from tink import aead, daead

from . import models
from ..models import Keyset


@pytest.fixture(autouse=True)
def configured_db_keyset(db):
    for name, template in {
        "aead": aead.aead_key_templates.AES256_GCM,
        "daead": daead.deterministic_aead_key_templates.AES256_SIV,
    }.items():
        model = Keyset.create(name=name, key_template=template)
        model.save()


@pytest.mark.parametrize(
    "model,vals",
    [
        (models.EncryptedText, ["foo", "bar"]),
        (models.EncryptedChar, ["one", "two"]),
        (models.EncryptedCharWithFixedAad, ["foo", "bar"]),
        (models.EncryptedEmail, ["a@example.com", "b@example.com"]),
        (models.EncryptedInt, [1, 2]),
        (models.EncryptedDate, [date(2015, 2, 5), date(2015, 2, 8)]),
        (
            models.EncryptedDateTime,
            [datetime(2015, 2, 5, 15), datetime(2015, 2, 8, 16)],
        ),
        (models.EncryptedCharWithAlternateKeyset, ["foo", "bar"]),
        (models.EncryptedIntEnvelope, [1, 2]),
        (models.EncryptedBinary, [b"1234", b"asdf"]),
    ],
)
class TestEncryptedFieldQueries(object):
    def test_insert(self, db, model, vals):
        """Data stored in DB is actually encrypted."""
        field = model._meta.get_field("value")
        aad_callback = getattr(field, "_aad_callback")
        model.objects.create(value=vals[0])
        with connection.cursor() as cur:
            cur.execute("SELECT value FROM %s" % model._meta.db_table)
            data = [
                field.to_python_prepare(
                    field._aead_primitive.decrypt(
                        force_bytes(r[0]), aad_callback(field)
                    )
                )
                for r in cur.fetchall()
            ]

        if model is models.EncryptedBinary:
            assert list([bytes(field.to_python(item)) for item in data]) == [vals[0]]
        else:
            assert list(map(field.to_python, data)) == [vals[0]]


def test_encrypted_nullable(db):
    models.EncryptedNullable(value=None).save()
    assert models.EncryptedNullable.objects.get(value__isnull=True)


@pytest.mark.parametrize(
    "model,vals",
    [
        (models.DeterministicEncryptedChar, ["one", "two"]),
        (models.DeterministicEncryptedEmail, ["a@example.com", "b@example.com"]),
        (models.DeterministicEncryptedInt, [1, 2]),
        (models.DeterministicEncryptedIntEnvelope, [1, 2]),
    ],
)
class TestDeterministicEncryptedFieldQueries(object):
    def test_insert(self, db, model, vals):
        """Data stored in DB is actually encrypted."""
        field = model._meta.get_field("value")
        aad_callback = getattr(field, "_aad_callback")
        model.objects.create(value=vals[0])
        with connection.cursor() as cur:
            cur.execute("SELECT value FROM %s" % model._meta.db_table)
            data = [
                field.to_python_prepare(
                    field._daead_primitive.decrypt_deterministically(
                        force_bytes(r[0]), aad_callback(field)
                    )
                )
                for r in cur.fetchall()
            ]

        assert list(map(field.to_python, data)) == [vals[0]]

    def test_search(self, db, model, vals):
        model.objects.create(value=vals[0])
        model.objects.create(value=vals[1])
        out = model.objects.filter(value=vals[0])
        assert len(out) == 1
        assert out[0].value == vals[0]


def test_rotated_deterministic_field(db):
    value = 12345678

    models.DeterministicEncryptedIntEnvelope(value=value).save()
    assert (
        models.DeterministicEncryptedIntEnvelope.objects.filter(value=value).count()
        == 1
    )

    keyset = Keyset.objects.get(name="daead")
    new_key = keyset.generate_key(daead.deterministic_aead_key_templates.AES256_SIV)
    keyset.set_primary_key(new_key)

    value_2 = 23456789
    models.DeterministicEncryptedIntEnvelope(value=value_2).save()

    assert (
        models.DeterministicEncryptedIntEnvelope.objects.filter(value=value).count()
        == 1
    )
    assert (
        models.DeterministicEncryptedIntEnvelope.objects.filter(value=value_2).count()
        == 1
    )
