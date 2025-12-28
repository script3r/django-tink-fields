from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.db import connection
from django.utils.encoding import force_bytes

import pytest

from example_app import models


def _fetch_raw_bytes(model_cls, field_name, pk):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {field_name} FROM {model_cls._meta.db_table} WHERE id = %s",
            [pk],
        )
        value = cursor.fetchone()[0]
    return bytes(value)


def _update_raw_bytes(model_cls, field_name, pk, raw_bytes):
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {model_cls._meta.db_table} SET {field_name} = %s WHERE id = %s",
            [raw_bytes, pk],
        )


@pytest.mark.django_db
def test_round_trip_and_ciphertext_at_rest():
    payload = b"binary payload \x00\x01\x02"
    instance = models.EncryptedSample.objects.create(
        name="Alice",
        bio="Encrypted bio",
        email="alice@example.com",
        count=42,
        birth_date=date(1990, 1, 1),
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        payload=payload,
    )
    instance.refresh_from_db()

    assert instance.name == "Alice"
    assert instance.bio == "Encrypted bio"
    assert instance.email == "alice@example.com"
    assert instance.count == 42
    assert instance.birth_date == date(1990, 1, 1)
    assert instance.created_at == datetime(2024, 1, 1, 12, 0, 0)
    assert instance.payload == payload

    raw_name = _fetch_raw_bytes(models.EncryptedSample, "name", instance.id)
    raw_payload = _fetch_raw_bytes(models.EncryptedSample, "payload", instance.id)
    assert raw_name != force_bytes("Alice")
    assert raw_payload != payload


@pytest.mark.django_db
def test_tamper_detection():
    instance = models.EncryptedSample.objects.create(
        name="Tamper",
        bio="Test",
        email="tamper@example.com",
        count=7,
        birth_date=date(2000, 2, 2),
        created_at=datetime(2024, 2, 2, 10, 0, 0),
    )
    raw_name = _fetch_raw_bytes(models.EncryptedSample, "name", instance.id)
    tampered = bytearray(raw_name)
    tampered[0] = (tampered[0] + 1) % 256
    _update_raw_bytes(models.EncryptedSample, "name", instance.id, bytes(tampered))

    with pytest.raises(Exception):
        instance.refresh_from_db()


@pytest.mark.django_db
def test_deterministic_ciphertext_and_lookup():
    first = models.DeterministicSample.objects.create(
        keyword="repeat",
        email="first@example.com",
        count=5,
    )
    second = models.DeterministicSample.objects.create(
        keyword="repeat",
        email="second@example.com",
        count=5,
    )
    raw_first = _fetch_raw_bytes(models.DeterministicSample, "keyword", first.id)
    raw_second = _fetch_raw_bytes(models.DeterministicSample, "keyword", second.id)
    assert raw_first == raw_second

    matches = models.DeterministicSample.objects.filter(keyword="repeat")
    assert matches.count() == 2


@pytest.mark.django_db
def test_aad_enforced():
    instance = models.EncryptedWithAad.objects.create(secret="aad-secret")
    raw_secret = _fetch_raw_bytes(models.EncryptedWithAad, "secret", instance.id)

    field = models.EncryptedWithAad._meta.get_field("secret")
    with pytest.raises(Exception):
        field._keyset_manager.aead_primitive.decrypt(raw_secret, b"wrong-aad")


@pytest.mark.django_db
def test_extended_fields_round_trip():
    token = uuid4()
    payload = {"alpha": 1, "beta": {"gamma": "delta"}, "items": [1, 2, 3]}
    instance = models.ExtendedEncryptedSample.objects.create(
        flag=True,
        ratio=3.14,
        amount=Decimal("1234.50"),
        token=token,
        payload=payload,
        url="https://example.com/alpha",
    )
    instance.refresh_from_db()

    assert instance.flag is True
    assert instance.ratio == 3.14
    assert instance.amount == Decimal("1234.50")
    assert instance.token == token
    assert instance.payload == payload
    assert instance.url == "https://example.com/alpha"

    raw_payload = _fetch_raw_bytes(models.ExtendedEncryptedSample, "payload", instance.id)
    assert raw_payload != force_bytes(payload)


@pytest.mark.django_db
def test_deterministic_uuid_ciphertext():
    token = uuid4()
    first = models.DeterministicExtendedSample.objects.create(token=token)
    second = models.DeterministicExtendedSample.objects.create(token=token)

    raw_first = _fetch_raw_bytes(models.DeterministicExtendedSample, "token", first.id)
    raw_second = _fetch_raw_bytes(models.DeterministicExtendedSample, "token", second.id)
    assert raw_first == raw_second
