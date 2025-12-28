from django.db import models
from django.utils.encoding import force_bytes

from tink_fields import (
    DeterministicEncryptedEmailField,
    DeterministicEncryptedIntegerField,
    DeterministicEncryptedTextField,
    DeterministicEncryptedUUIDField,
    EncryptedBooleanField,
    EncryptedBinaryField,
    EncryptedCharField,
    EncryptedDateField,
    EncryptedDateTimeField,
    EncryptedDecimalField,
    EncryptedEmailField,
    EncryptedFloatField,
    EncryptedIntegerField,
    EncryptedJSONField,
    EncryptedTextField,
    EncryptedURLField,
    EncryptedUUIDField,
)


def aad_for_field(field: models.Field) -> bytes:
    return force_bytes(f"{field.model._meta.label}:{field.name}")


class EncryptedSample(models.Model):
    name = EncryptedCharField(max_length=50)
    bio = EncryptedTextField()
    email = EncryptedEmailField()
    count = EncryptedIntegerField()
    birth_date = EncryptedDateField()
    created_at = EncryptedDateTimeField()
    payload = EncryptedBinaryField(null=True)


class EncryptedWithAad(models.Model):
    secret = EncryptedCharField(max_length=50, aad_callback=aad_for_field)


class DeterministicSample(models.Model):
    keyword = DeterministicEncryptedTextField(keyset="deterministic")
    email = DeterministicEncryptedEmailField(keyset="deterministic")
    count = DeterministicEncryptedIntegerField(keyset="deterministic")


class ExtendedEncryptedSample(models.Model):
    flag = EncryptedBooleanField()
    ratio = EncryptedFloatField()
    amount = EncryptedDecimalField(max_digits=8, decimal_places=2)
    token = EncryptedUUIDField()
    payload = EncryptedJSONField()
    url = EncryptedURLField()


class DeterministicExtendedSample(models.Model):
    token = DeterministicEncryptedUUIDField(keyset="deterministic")
