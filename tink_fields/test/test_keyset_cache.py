"""Shared primitive construction, bounded storage, and concurrent invalidation."""

import gc
import json
import weakref
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch

import pytest
from django.test import override_settings
from tink import KeysetHandle, aead, daead, json_proto_keyset_format, new_keyset_handle, secret_key_access

from tink_fields import clear_keyset_cache
from tink_fields.fields import KeysetManager


@pytest.fixture(autouse=True)
def empty_keyset_cache():
    clear_keyset_cache()
    yield
    clear_keyset_cache()


@pytest.mark.parametrize("keyset, attribute", [("default", "aead_primitive"), ("deterministic", "daead_primitive")])
def test_managers_share_primitive_construction(keyset, attribute):
    managers = [KeysetManager(keyset) for _ in range(100)]
    original = KeysetHandle.primitive
    with patch.object(KeysetHandle, "primitive", autospec=True, side_effect=original) as construct:
        primitives = [getattr(manager, attribute) for manager in managers]
    assert construct.call_count == 1
    assert all(primitive is primitives[0] for primitive in primitives)


@pytest.mark.parametrize("keyset, attribute", [("default", "aead_primitive"), ("deterministic", "daead_primitive")])
def test_clear_cache_waits_for_inflight_primitive_construction(keyset, attribute):
    manager = KeysetManager(keyset)
    building = Event()
    release = Event()
    clearing = Event()
    cleared = Event()
    original = KeysetHandle.primitive

    def slow_primitive(handle, primitive_class):
        building.set()
        assert release.wait(5)
        return original(handle, primitive_class)

    def clear():
        clearing.set()
        clear_keyset_cache()
        cleared.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        with patch.object(KeysetHandle, "primitive", slow_primitive):
            constructing = pool.submit(getattr, manager, attribute)
            try:
                assert building.wait(5)
                invalidating = pool.submit(clear)
                assert clearing.wait(5)
                assert not cleared.wait(0.1), "cache cleared before the old primitive could finish publishing"
            finally:
                release.set()
            old = constructing.result(timeout=5)
            invalidating.result(timeout=5)
        assert getattr(manager, attribute) is not old


@pytest.mark.parametrize(
    "template, attribute, encrypt, decrypt",
    [
        (aead.aead_key_templates.AES128_GCM, "aead_primitive", "encrypt", "decrypt"),
        (
            daead.deterministic_aead_key_templates.AES256_SIV,
            "daead_primitive",
            "encrypt_deterministically",
            "decrypt_deterministically",
        ),
    ],
)
def test_rotation_reloads_all_active_managers(tmp_path, template, attribute, encrypt, decrypt):
    old_keyset = json.loads(json_proto_keyset_format.serialize(new_keyset_handle(template), secret_key_access.TOKEN))
    new_keyset = json.loads(json_proto_keyset_format.serialize(new_keyset_handle(template), secret_key_access.TOKEN))
    new_keyset["key"].extend(old_keyset["key"])
    path = tmp_path / "keys.json"
    path.write_text(json.dumps(old_keyset), encoding="utf-8")
    with override_settings(TINK_FIELDS_CONFIG={"default": {"path": path, "cleartext": True}}):
        managers = [KeysetManager("default") for _ in range(3)]
        before = [getattr(manager, attribute) for manager in managers]
        ciphertext = getattr(before[0], encrypt)(b"secret", b"aad")
        replacement = tmp_path / "replacement.json"
        replacement.write_text(json.dumps(new_keyset), encoding="utf-8")
        replacement.replace(path)
        clear_keyset_cache()
        for manager, old_primitive in zip(managers, before, strict=True):
            primitive = getattr(manager, attribute)
            assert primitive is not old_primitive
            assert getattr(primitive, decrypt)(ciphertext, b"aad") == b"secret"
            assert getattr(primitive, encrypt)(b"secret", b"aad")[1:5] == new_keyset["primaryKeyId"].to_bytes(4, "big")


def test_shared_cache_is_bounded_and_does_not_retain_managers(tmp_path):
    config = {}
    source = Path(__file__).with_name("test_plaintext_keyset.json").read_text(encoding="utf-8")
    for index in range(3):
        path = tmp_path / f"keys-{index}.json"
        path.write_text(source, encoding="utf-8")
        config[str(index)] = {"path": path, "cleartext": True}
    with override_settings(TINK_FIELDS_CONFIG=config), patch.object(KeysetManager, "_cache_size", 2):
        for name in config:
            manager = KeysetManager(name)
            _ = manager.aead_primitive
        assert len(KeysetManager._handle_cache) == 2
        reference = weakref.ref(manager)
        del manager
        gc.collect()
        assert reference() is None
