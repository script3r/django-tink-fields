from tink import aead, daead
from tink_fields.models import Keyset

TEST_DATA = b"hello world"
ASSOC_DATA = b"ad"


def test_aead_encrypt(db):
    key_template = aead.aead_key_templates.AES256_GCM
    ks = Keyset.create("aead", key_template)
    primitive = ks.primitive(aead.Aead)

    ciphertext = primitive.encrypt(TEST_DATA, ASSOC_DATA)

    assert primitive.decrypt(ciphertext, ASSOC_DATA) == TEST_DATA


def test_aead_decrypt_non_primary(db):
    key_template = aead.aead_key_templates.AES256_GCM
    ks = Keyset.create("aead", key_template)

    ciphertext = ks.primitive(aead.Aead).encrypt(TEST_DATA, ASSOC_DATA)

    secondary_key = ks.generate_key(key_template)
    ks.set_primary_key(secondary_key)
    ks.refresh_from_db()
    assert ks.primary_key == secondary_key

    assert ks.primitive(aead.Aead).decrypt(ciphertext, ASSOC_DATA) == TEST_DATA


def test_daead_encrypt(db):
    key_template = daead.deterministic_aead_key_templates.AES256_SIV
    ks = Keyset.create("daead", key_template)
    primitive = ks.primitive(daead.DeterministicAead)

    ciphertext = primitive.encrypt_deterministically(TEST_DATA, ASSOC_DATA)

    assert primitive.encrypt_deterministically(TEST_DATA, ASSOC_DATA) == ciphertext
    assert primitive.decrypt_deterministically(ciphertext, ASSOC_DATA) == TEST_DATA


def test_aead_decrypt_non_primary(db):
    key_template = daead.deterministic_aead_key_templates.AES256_SIV
    ks = Keyset.create("daead", key_template)

    primitive = ks.primitive(daead.DeterministicAead)
    ciphertext = primitive.encrypt_deterministically(TEST_DATA, ASSOC_DATA)

    secondary_key = ks.generate_key(key_template)
    ks.set_primary_key(secondary_key)
    ks.refresh_from_db()
    assert ks.primary_key == secondary_key

    primitive = ks.primitive(daead.DeterministicAead)
    assert primitive.encrypt_deterministically(TEST_DATA, ASSOC_DATA) != ciphertext
    assert primitive.decrypt_deterministically(ciphertext, ASSOC_DATA) == TEST_DATA


def test_multiple_key_templates(db):
    ks = Keyset.create("aead", aead.aead_key_templates.AES256_GCM)
    primitive = ks.primitive(aead.Aead)
    ciphertext = primitive.encrypt(TEST_DATA, ASSOC_DATA)

    key_2 = ks.generate_key(aead.aead_key_templates.AES128_CTR_HMAC_SHA256)
    ks.set_primary_key(key_2)
    ciphertext2 = primitive.encrypt(TEST_DATA, ASSOC_DATA)

    assert len(ciphertext) != len(ciphertext2)

    ks = Keyset.objects.get(name="aead")
    primitive = ks.primitive(aead.Aead)
    assert primitive.decrypt(ciphertext, ASSOC_DATA) == TEST_DATA
    assert primitive.decrypt(ciphertext2, ASSOC_DATA) == TEST_DATA
