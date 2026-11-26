"""Encrypted JSON uses a Python codec and a binary database column."""

import json
from decimal import Decimal
from unittest.mock import patch

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection

from tink_fields import EncryptedJSONField

from . import models


class DecimalDecoder(json.JSONDecoder):
    def __init__(self, **kwargs):
        super().__init__(parse_float=Decimal, **kwargs)


def test_encrypted_json_does_not_require_database_json_support():
    field = models.EncryptedExtended._meta.get_field("payload")
    with patch.object(type(connection.features), "supports_json_field", False):
        assert field.check(databases=[connection.alias]) == []

    assert [error.id for error in EncryptedJSONField(default={}).check()] == ["fields.E010"]


def test_encrypted_json_preserves_custom_codecs_and_reads_existing_ciphertext():
    field = EncryptedJSONField(encoder=DjangoJSONEncoder, decoder=DecimalDecoder)
    prepared = field._prepare_value_for_database({"amount": Decimal("3.20")}, connection)
    assert json.loads(prepared) == {"amount": "3.20"}

    old_plaintext = b'{"ratio": 1.25, "text": "hello", "list": [true, null]}'
    old_ciphertext = field._get_aead_primitive().encrypt(old_plaintext, b"")
    value = field.from_db_value(old_ciphertext, None, connection)
    assert value == {"ratio": Decimal("1.25"), "text": "hello", "list": [True, None]}
    assert isinstance(value["ratio"], Decimal)


def test_encrypted_json_preserves_django_fallback_for_legacy_invalid_json():
    field = EncryptedJSONField()
    ciphertext = field._get_aead_primitive().encrypt(b"legacy text", b"")
    assert field.from_db_value(ciphertext, None, connection) == "legacy text"
