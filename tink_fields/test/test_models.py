from tink import aead, daead
from tink_fields.models import Keyset

TEST_DATA = b"hello world"
ASSOC_DATA = b"ad"


def test_aead_encrypt(db):
    key_template = aead.aead_key_templates.AES256_GCM
    ks = Keyset.create("aead", key_template)

    ciphertext = ks.primitive.encrypt(TEST_DATA, ASSOC_DATA)

    assert ks.primitive.decrypt(ciphertext, ASSOC_DATA) == TEST_DATA


def test_aead_decrypt_non_primary(db):
    key_template = aead.aead_key_templates.AES256_GCM
    ks = Keyset.create("aead", key_template)

    ciphertext = ks.primitive.encrypt(TEST_DATA, ASSOC_DATA)

    secondary_key = ks.generate_key(key_template)
    ks.set_primary_key(secondary_key)
    secondary_key.refresh_from_db()
    assert secondary_key.is_primary

    assert ks.primitive.decrypt(ciphertext, ASSOC_DATA) == TEST_DATA


def test_daead_encrypt(db):
    key_template = daead.deterministic_aead_key_templates.AES256_SIV
    ks = Keyset.create("daead", key_template)

    ciphertext = ks.primitive.encrypt_deterministically(TEST_DATA, ASSOC_DATA)

    assert ks.primitive.encrypt_deterministically(TEST_DATA, ASSOC_DATA) == ciphertext
    assert ks.primitive.decrypt_deterministically(ciphertext, ASSOC_DATA) == TEST_DATA


def test_aead_decrypt_non_primary(db):
    key_template = daead.deterministic_aead_key_templates.AES256_SIV
    ks = Keyset.create("daead", key_template)

    ciphertext = ks.primitive.encrypt_deterministically(TEST_DATA, ASSOC_DATA)

    secondary_key = ks.generate_key(key_template)
    ks.set_primary_key(secondary_key)
    secondary_key.refresh_from_db()
    assert secondary_key.is_primary

    assert ks.primitive.encrypt_deterministically(TEST_DATA, ASSOC_DATA) != ciphertext
    assert ks.primitive.decrypt_deterministically(ciphertext, ASSOC_DATA) == TEST_DATA
