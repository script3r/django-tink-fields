"""Tests for new features from PR #2 implementation."""

import tempfile
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, models
from django.test import TestCase

import pytest

from tink_fields.fields import (
    EncryptedBinaryField,
    DeterministicEncryptedField,
    DeterministicEncryptedTextField,
    DeterministicEncryptedCharField,
    DeterministicEncryptedEmailField,
    DeterministicEncryptedIntegerField,
    DeterministicEncryptedDateField,
    DeterministicEncryptedDateTimeField,
    DAEAD_AVAILABLE,
)


@pytest.mark.django_db
class TestEncryptedBinaryField:
    """Test cases for EncryptedBinaryField."""

    def test_binary_field_encryption(self):
        """Test that binary data is encrypted and decrypted correctly."""
        # Create a test model with binary field
        class TestModel(models.Model):
            data = EncryptedBinaryField()

            class Meta:
                app_label = "test"

        # Test data
        test_data = b"binary data \x00\x01\x02\x03"

        # Create and save
        obj = TestModel.objects.create(data=test_data)
        obj.refresh_from_db()

        # Verify decryption
        assert obj.data == test_data

        # Verify encryption in database
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT data FROM {TestModel._meta.db_table} WHERE id = %s", [obj.id])
            encrypted_data = cursor.fetchone()[0]

        # Should be encrypted (not equal to original)
        assert encrypted_data != test_data

    def test_binary_field_none_value(self):
        """Test that None values are handled correctly."""
        class TestModel(models.Model):
            data = EncryptedBinaryField(null=True)

            class Meta:
                app_label = "test"

        obj = TestModel.objects.create(data=None)
        obj.refresh_from_db()
        assert obj.data is None


@pytest.mark.django_db
class TestDeterministicEncryption:
    """Test cases for deterministic encryption fields."""

    def test_deterministic_text_field(self):
        """Test deterministic text field encryption."""
        from tink_fields.test.models import DeterministicEncryptedText
        from django.db import connection

        test_value = "test value"

        # Create two objects with same value
        obj1 = DeterministicEncryptedText.objects.create(value=test_value)
        obj2 = DeterministicEncryptedText.objects.create(value=test_value)

        # Both should decrypt to same value
        assert obj1.value == test_value
        assert obj2.value == test_value

        # But encrypted values should be identical (deterministic)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT value FROM {DeterministicEncryptedText._meta.db_table} WHERE id = %s", [obj1.id])
            encrypted1 = cursor.fetchone()[0]
            cursor.execute(f"SELECT value FROM {DeterministicEncryptedText._meta.db_table} WHERE id = %s", [obj2.id])
            encrypted2 = cursor.fetchone()[0]

        assert encrypted1 == encrypted2

    def test_deterministic_char_field(self):
        """Test deterministic char field encryption."""
        class TestModel(models.Model):
            char = DeterministicEncryptedCharField(max_length=100, keyset="deterministic")

            class Meta:
                app_label = "test"

        test_value = "test char"

        obj1 = TestModel.objects.create(char=test_value)
        obj2 = TestModel.objects.create(char=test_value)

        assert obj1.char == test_value
        assert obj2.char == test_value

        # Verify deterministic encryption
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT char FROM {TestModel._meta.db_table} WHERE id = %s", [obj1.id])
            encrypted1 = cursor.fetchone()[0]
            cursor.execute(f"SELECT char FROM {TestModel._meta.db_table} WHERE id = %s", [obj2.id])
            encrypted2 = cursor.fetchone()[0]

        assert encrypted1 == encrypted2

    def test_deterministic_integer_field(self):
        """Test deterministic integer field encryption."""
        class TestModel(models.Model):
            integer = DeterministicEncryptedIntegerField(keyset="deterministic")

            class Meta:
                app_label = "test"

        test_value = 42

        obj1 = TestModel.objects.create(integer=test_value)
        obj2 = TestModel.objects.create(integer=test_value)

        assert obj1.integer == test_value
        assert obj2.integer == test_value

        # Verify deterministic encryption
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT integer FROM {TestModel._meta.db_table} WHERE id = %s", [obj1.id])
            encrypted1 = cursor.fetchone()[0]
            cursor.execute(f"SELECT integer FROM {TestModel._meta.db_table} WHERE id = %s", [obj2.id])
            encrypted2 = cursor.fetchone()[0]

        assert encrypted1 == encrypted2

    def test_deterministic_email_field(self):
        """Test deterministic email field encryption."""
        class TestModel(models.Model):
            email = DeterministicEncryptedEmailField(keyset="deterministic")

            class Meta:
                app_label = "test"

        test_value = "test@example.com"

        obj1 = TestModel.objects.create(email=test_value)
        obj2 = TestModel.objects.create(email=test_value)

        assert obj1.email == test_value
        assert obj2.email == test_value

        # Verify deterministic encryption
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT email FROM {TestModel._meta.db_table} WHERE id = %s", [obj1.id])
            encrypted1 = cursor.fetchone()[0]
            cursor.execute(f"SELECT email FROM {TestModel._meta.db_table} WHERE id = %s", [obj2.id])
            encrypted2 = cursor.fetchone()[0]

        assert encrypted1 == encrypted2


@pytest.mark.django_db
class TestDeterministicLookups:
    """Test cases for deterministic field lookups."""

    def test_deterministic_exact_lookup(self):
        """Test that exact lookups work with deterministic fields."""
        class TestModel(models.Model):
            text = DeterministicEncryptedTextField(keyset="deterministic")

            class Meta:
                app_label = "test"

        # Create test data
        TestModel.objects.create(text="value1")
        TestModel.objects.create(text="value2")
        TestModel.objects.create(text="value1")  # Duplicate

        # Test exact lookup
        results = TestModel.objects.filter(text="value1")
        assert results.count() == 2

        # Test exact lookup with different value
        results = TestModel.objects.filter(text="value2")
        assert results.count() == 1

    def test_deterministic_isnull_lookup(self):
        """Test that isnull lookups work with deterministic fields."""
        class TestModel(models.Model):
            text = DeterministicEncryptedTextField(null=True, keyset="deterministic")

            class Meta:
                app_label = "test"

        # Create test data
        TestModel.objects.create(text="value1")
        TestModel.objects.create(text=None)

        # Test isnull lookup
        results = TestModel.objects.filter(text__isnull=True)
        assert results.count() == 1

        results = TestModel.objects.filter(text__isnull=False)
        assert results.count() == 1

    def test_deterministic_unsupported_lookup_raises_error(self):
        """Test that unsupported lookups raise FieldError."""
        class TestModel(models.Model):
            text = DeterministicEncryptedTextField(keyset="deterministic")

            class Meta:
                app_label = "test"

        TestModel.objects.create(text="value1")

        # Test that unsupported lookups raise FieldError
        with pytest.raises(Exception):  # FieldError or similar
            TestModel.objects.filter(text__contains="value").count()


@pytest.mark.django_db
class TestKeysetManager:
    """Test cases for KeysetManager functionality."""

    def test_keyset_manager_validation(self):
        """Test that KeysetManager validates configuration on init."""
        from tink_fields.fields import KeysetManager

        # Test missing TINK_FIELDS_CONFIG
        with patch.object(settings, "TINK_FIELDS_CONFIG", None):
            with pytest.raises(ImproperlyConfigured):
                KeysetManager("default", lambda x: b"")

        # Test missing keyset in config
        with patch.object(settings, "TINK_FIELDS_CONFIG", {}):
            with pytest.raises(ImproperlyConfigured):
                KeysetManager("nonexistent", lambda x: b"")

    def test_keyset_manager_caching(self):
        """Test that KeysetManager properly caches primitives."""
        from tink_fields.fields import KeysetManager

        manager = KeysetManager("default", lambda x: b"")

        # Get primitive multiple times
        primitive1 = manager.aead_primitive
        primitive2 = manager.aead_primitive

        # Should be the same instance (cached)
        assert primitive1 is primitive2

        # Test deterministic primitive caching (if available)
        if DAEAD_AVAILABLE:
            daead1 = manager.daead_primitive
            daead2 = manager.daead_primitive
            assert daead1 is daead2
        else:
            # Should raise ImproperlyConfigured when not available
            with pytest.raises(ImproperlyConfigured):
                manager.daead_primitive


@pytest.mark.django_db
class TestMemoryLeakFix:
    """Test cases for memory leak fixes."""

    def test_cached_property_usage(self):
        """Test that cached_property is used instead of lru_cache."""
        field = DeterministicEncryptedTextField()

        # Get validators multiple times
        validators1 = field.validators
        validators2 = field.validators

        # Should be the same instance (cached)
        assert validators1 is validators2

    def test_keyset_manager_cached_properties(self):
        """Test that KeysetManager uses cached_property correctly."""
        from tink_fields.fields import KeysetManager

        manager = KeysetManager("default", lambda x: b"")

        # Test that properties are cached
        aead1 = manager.aead_primitive
        aead2 = manager.aead_primitive
        assert aead1 is aead2

        # Test deterministic primitive - should raise ImproperlyConfigured
        # because current keyset doesn't support deterministic AEAD
        with pytest.raises(ImproperlyConfigured):
            manager.daead_primitive
