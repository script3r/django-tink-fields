"""Keyset parsing compatibility and actionable configuration errors."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from tink import aead, json_proto_keyset_format, new_keyset_handle

from tink_fields import clear_keyset_cache
from tink_fields.fields import KeysetConfig, KeysetManager


@pytest.fixture(autouse=True)
def empty_keyset_cache():
    clear_keyset_cache()
    yield
    clear_keyset_cache()


def test_user_relative_keyset_path_is_expanded_before_validation():
    source = Path(__file__).with_name("test_plaintext_keyset.json").read_text(encoding="utf-8")
    with TemporaryDirectory(prefix=".tink-fields-test-", dir=Path.home()) as directory:
        path = Path(directory) / "keys.json"
        path.write_text(source, encoding="utf-8")
        config = {"default": {"path": f"~/{Path(directory).name}/keys.json", "cleartext": True}}
        with override_settings(TINK_FIELDS_CONFIG=config):
            primitive = KeysetManager("default").aead_primitive
            ciphertext = primitive.encrypt(b"secret", b"context")
            assert primitive.decrypt(ciphertext, b"context") == b"secret"


def test_non_utf8_keyset_has_a_configuration_error(tmp_path):
    path = tmp_path / "keys.json"
    path.write_bytes(b"\xff\xfeinvalid")
    with (
        override_settings(TINK_FIELDS_CONFIG={"default": {"path": path, "cleartext": True}}),
        pytest.raises(ImproperlyConfigured, match="Could not load keyset `default`"),
    ):
        _ = KeysetManager("default").aead_primitive


def test_aead_field_with_deterministic_keyset_has_a_configuration_error():
    with pytest.raises(ImproperlyConfigured, match="does not support AEAD"):
        _ = KeysetManager("deterministic").aead_primitive


def test_invalid_master_key_has_a_configuration_error():
    with pytest.raises(ImproperlyConfigured, match="must be a Tink Aead"):
        KeysetConfig(path=Path(__file__).with_name("test_plaintext_keyset.json"), master_key_aead="invalid")


@pytest.mark.parametrize("path", [123, "invalid\x00path"])
def test_invalid_path_has_a_configuration_error(path):
    with pytest.raises(ImproperlyConfigured, match="readable file"):
        KeysetConfig(path=path, cleartext=True)


def test_unhashable_master_key_still_loads_encrypted_keysets(tmp_path):
    primitive = KeysetManager("default").aead_primitive

    class UnhashableAead(aead.Aead):
        def __eq__(self, other):
            return self is other

        def encrypt(self, plaintext, associated_data):
            return primitive.encrypt(plaintext, associated_data)

        def decrypt(self, ciphertext, associated_data):
            return primitive.decrypt(ciphertext, associated_data)

    master = UnhashableAead()
    path = tmp_path / "encrypted.json"
    serialized = json_proto_keyset_format.serialize_encrypted(
        new_keyset_handle(aead.aead_key_templates.AES128_GCM), master, b""
    )
    path.write_text(serialized, encoding="utf-8")
    config = {"encrypted": {"path": path, "master_key_aead": master, "cleartext": False}}
    with override_settings(TINK_FIELDS_CONFIG=config):
        first = KeysetManager("encrypted").aead_primitive
        second = KeysetManager("encrypted").aead_primitive
        ciphertext = first.encrypt(b"secret", b"context")
        assert second.decrypt(ciphertext, b"context") == b"secret"
