"""Regression and public API tests for release-critical behavior."""

import io
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import IntegrityError, connection, transaction
from django.db import models as django_models
from django.db.migrations.writer import MigrationWriter
from django.test import override_settings
from tink import JsonKeysetWriter, TinkError, aead, new_keyset_handle

from tink_fields import (
    DeterministicEncryptedCharField,
    EncryptedCharField,
    EncryptedJSONField,
    EncryptedTextField,
    __version__,
    clear_keyset_cache,
)
from tink_fields.fields import KeysetConfig, KeysetManager

from . import models


def test_release_version() -> None:
    assert __version__ == "0.5.0"


def test_fields_are_constructible_without_configured_keysets() -> None:
    with override_settings(TINK_FIELDS_CONFIG=None):
        field = EncryptedCharField(max_length=12, keyset="future-key")
    assert field._keyset == "future-key"


def test_deconstruct_and_clone_preserve_encryption_options() -> None:
    field = models.EncryptedCharWithFixedAad._meta.get_field("value")
    _, _, _, kwargs = field.deconstruct()

    assert kwargs["aad_callback"] is models.sample_aad_provider
    assert field.clone()._aad_callback is models.sample_aad_provider

    alternate = models.EncryptedCharWithAlternateKeyset._meta.get_field("value")
    _, _, _, kwargs = alternate.deconstruct()
    assert kwargs["keyset"] == "alternate"
    assert alternate.clone()._keyset == "alternate"


def test_default_encryption_options_are_omitted_from_migrations() -> None:
    field = EncryptedCharField(max_length=12)
    _, _, _, kwargs = field.deconstruct()
    assert "keyset" not in kwargs
    assert "aad_callback" not in kwargs


def test_aad_callback_is_migration_serializable() -> None:
    field = models.EncryptedCharWithFixedAad._meta.get_field("value")
    serialized, imports = MigrationWriter.serialize(field)
    assert "sample_aad_provider" in serialized
    assert "import tink_fields.fields" in imports
    assert "import tink_fields.test.models" in imports


@pytest.mark.parametrize("property_name", ["primary_key", "db_index", "unique", "db_default"])
def test_randomized_fields_reject_unsafe_database_properties(property_name: str) -> None:
    with pytest.raises(ImproperlyConfigured, match=f"property `{property_name}`"):
        EncryptedTextField(**{property_name: True})


def test_explicit_false_database_properties_are_allowed() -> None:
    EncryptedTextField(primary_key=False, db_index=False, unique=False)


def test_database_defaults_are_rejected_even_when_none() -> None:
    with pytest.raises(ImproperlyConfigured, match="property `db_default`"):
        EncryptedTextField(db_default=None)


def test_deterministic_fields_allow_indexes_and_uniqueness() -> None:
    field = DeterministicEncryptedCharField(max_length=12, keyset="deterministic", db_index=True, unique=True)
    assert field.db_index is True
    assert field.unique is True


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"keyset": ""}, "non-empty string"),
        ({"keyset": 3}, "non-empty string"),
        ({"aad_callback": b"not-callable"}, "must be callable"),
    ],
)
def test_invalid_field_options_fail_early(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ImproperlyConfigured, match=message):
        EncryptedTextField(**kwargs)


def test_aad_callback_must_return_bytes() -> None:
    field = EncryptedTextField(aad_callback=lambda field: "not-bytes")
    with pytest.raises(ImproperlyConfigured, match="must return bytes"):
        field.get_db_prep_save("secret", connection)


def test_json_is_serialized_before_backend_adaptation() -> None:
    field = EncryptedJSONField()
    prepared = field._prepare_value_for_database({"backend-independent": [1, True, None]}, connection)
    assert json.loads(prepared) == {"backend-independent": [1, True, None]}


@pytest.mark.parametrize(
    "config, message",
    [
        ([], "must be a mapping"),
        ({"default": []}, "must be a mapping"),
        ({"default": {"unknown": True}}, "Invalid configuration"),
    ],
)
def test_malformed_settings_have_actionable_errors(config: object, message: str) -> None:
    with override_settings(TINK_FIELDS_CONFIG=config), pytest.raises(ImproperlyConfigured, match=message):
        _ = KeysetManager("default").aead_primitive


def test_keyset_config_rejects_directories_and_non_boolean_cleartext(tmp_path: Path) -> None:
    with pytest.raises(ImproperlyConfigured, match="readable file"):
        KeysetConfig(path=tmp_path, cleartext=True)

    keyset_path = tmp_path / "keyset.json"
    keyset_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ImproperlyConfigured, match="must be a boolean"):
        KeysetConfig(path=keyset_path, cleartext="yes")


def test_malformed_keyset_is_reported_as_configuration_error(tmp_path: Path) -> None:
    keyset_path = tmp_path / "keyset.json"
    keyset_path.write_text("not json", encoding="utf-8")
    config = {"default": {"path": keyset_path, "cleartext": True}}
    with (
        override_settings(TINK_FIELDS_CONFIG=config),
        pytest.raises(ImproperlyConfigured, match="Could not load keyset `default`"),
    ):
        _ = KeysetManager("default").aead_primitive


def test_encrypted_keyset_round_trip(tmp_path: Path) -> None:
    master_aead = KeysetManager("default").aead_primitive
    serialized = io.StringIO()
    new_keyset_handle(aead.aead_key_templates.AES128_GCM).write(JsonKeysetWriter(serialized), master_aead)
    keyset_path = tmp_path / "encrypted-keyset.json"
    keyset_path.write_text(serialized.getvalue(), encoding="utf-8")

    config = {"encrypted": {"path": keyset_path, "cleartext": False, "master_key_aead": master_aead}}
    with override_settings(TINK_FIELDS_CONFIG=config):
        primitive = KeysetManager("encrypted").aead_primitive
        ciphertext = primitive.encrypt(b"protected", b"context")
        assert primitive.decrypt(ciphertext, b"context") == b"protected"


def test_clear_keyset_cache_reloads_active_field_primitives() -> None:
    field = models.EncryptedText._meta.get_field("value")
    original = field._keyset_manager.aead_primitive
    clear_keyset_cache()
    replacement = field._keyset_manager.aead_primitive
    assert replacement is not original


@pytest.mark.django_db
def test_extended_randomized_fields_round_trip() -> None:
    token = uuid4()
    payload = {"nested": {"values": [1, True, None]}, "text": "hello"}
    instance = models.EncryptedExtended.objects.create(
        flag=True,
        positive=7,
        ratio=3.25,
        amount=Decimal("1234.50"),
        token=token,
        payload=payload,
        url="https://example.com/path",
        slug="encrypted-slug",
    )
    instance.refresh_from_db()
    assert instance.flag is True
    assert instance.positive == 7
    assert instance.ratio == 3.25
    assert instance.amount == Decimal("1234.50")
    assert instance.token == token
    assert instance.payload == payload
    assert instance.url == "https://example.com/path"
    assert instance.slug == "encrypted-slug"


@pytest.mark.django_db
def test_regular_exact_none_uses_isnull_semantics() -> None:
    models.EncryptedNullable.objects.create(value=None)
    models.EncryptedNullable.objects.create(value=1)
    assert models.EncryptedNullable.objects.filter(value=None).count() == 1


@pytest.mark.django_db
def test_deterministic_uuid_lookup_uses_database_representation() -> None:
    token = uuid4()
    expected = models.DeterministicEncryptedExtended.objects.create(
        token=token,
        flag=True,
        day=date(2026, 8, 1),
        moment=datetime(2026, 8, 1, 12, 30),
    )
    models.DeterministicEncryptedExtended.objects.create(
        token=uuid4(),
        flag=False,
        day=date(2026, 8, 2),
        moment=datetime(2026, 8, 2, 12, 30),
    )
    assert models.DeterministicEncryptedExtended.objects.get(token=token).pk == expected.pk


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("flag", True),
        ("day", date(2026, 8, 1)),
        ("moment", datetime(2026, 8, 1, 12, 30)),
    ],
)
def test_deterministic_extended_exact_lookups(field_name: str, value: object) -> None:
    instance = models.DeterministicEncryptedExtended.objects.create(
        token=uuid4(),
        flag=True,
        day=date(2026, 8, 1),
        moment=datetime(2026, 8, 1, 12, 30),
    )
    assert models.DeterministicEncryptedExtended.objects.get(**{field_name: value}).pk == instance.pk


@pytest.mark.django_db
def test_deterministic_unique_constraint_is_enforced() -> None:
    models.DeterministicEncryptedUnique.objects.create(value="duplicate")
    with pytest.raises(IntegrityError), transaction.atomic():
        models.DeterministicEncryptedUnique.objects.create(value="duplicate")


@pytest.mark.django_db
def test_database_expressions_are_rejected() -> None:
    instance = models.EncryptedText.objects.create(value="secret")
    with transaction.atomic(), pytest.raises(FieldError, match="does not support database expressions"):
        models.EncryptedText.objects.filter(pk=instance.pk).update(value=django_models.F("value"))

    deterministic = models.DeterministicEncryptedText.objects.create(value="searchable")
    with pytest.raises(FieldError, match="do not support database expressions"):
        models.DeterministicEncryptedText.objects.filter(value=django_models.F("value")).get(pk=deterministic.pk)


@pytest.mark.django_db
def test_ciphertext_tampering_raises_tink_error() -> None:
    instance = models.EncryptedText.objects.create(value="secret")
    table = models.EncryptedText._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT value FROM {table} WHERE id = %s", [instance.pk])
        ciphertext = bytearray(cursor.fetchone()[0])
        ciphertext[-1] ^= 1
        cursor.execute(f"UPDATE {table} SET value = %s WHERE id = %s", [bytes(ciphertext), instance.pk])

    with pytest.raises(TinkError):
        instance.refresh_from_db()
