from django.db import models
from django.utils.encoding import force_bytes
import tink_fields as fields


class EncryptedText(models.Model):
    value = fields.EncryptedTextField()


class EncryptedChar(models.Model):
    value = fields.EncryptedCharField(max_length=25)


class EncryptedEmail(models.Model):
    value = fields.EncryptedEmailField()


class EncryptedInt(models.Model):
    value = fields.EncryptedIntegerField()


class EncryptedDate(models.Model):
    value = fields.EncryptedDateField()


class EncryptedDateTime(models.Model):
    value = fields.EncryptedDateTimeField()


class EncryptedNullable(models.Model):
    value = fields.EncryptedIntegerField(null=True)


def sample_aad_provider(instance) -> bytes:
    return force_bytes(instance.__class__.__name__)


class EncryptedCharWithFixedAad(models.Model):
    value = fields.EncryptedCharField(max_length=25, aad_callback=sample_aad_provider)


class EncryptedCharWithAlternateKeyset(models.Model):
    value = fields.EncryptedCharField(max_length=25, keyset="alternate")
