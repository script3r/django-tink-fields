"""Integer conversion and validation for encrypted binary columns."""

import pytest
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import connection, models
from django.db.backends.postgresql.base import DatabaseWrapper

from tink_fields import DeterministicEncryptedIntegerField, EncryptedIntegerField, EncryptedPositiveIntegerField


@pytest.mark.parametrize(
    "field, value",
    [
        (EncryptedIntegerField(), -12),
        (EncryptedPositiveIntegerField(), 0),
        (DeterministicEncryptedIntegerField(keyset="deterministic"), 12),
    ],
)
def test_postgresql_integer_preparation(field, value):
    postgres = DatabaseWrapper({})

    adapted = field.get_db_prep_save(str(value), postgres)
    assert isinstance(adapted, postgres.Database.Binary)
    assert field.from_db_value(adapted.obj, None, postgres) == value
    assert field.get_db_prep_save(None, postgres) is None


@pytest.mark.parametrize(
    "field_class, django_field_class",
    [
        (EncryptedIntegerField, models.IntegerField),
        (EncryptedPositiveIntegerField, models.PositiveIntegerField),
        (DeterministicEncryptedIntegerField, models.IntegerField),
    ],
)
def test_integer_validators_preserve_binary_type_and_django_bounds(field_class, django_field_class):
    internal_type = django_field_class().get_internal_type()
    lower, upper = connection.ops.integer_field_range(internal_type)
    observed_types = []

    def custom_minimum():
        observed_types.append(field.get_internal_type())
        return lower + 1

    field = field_class(validators=[MinValueValidator(custom_minimum)])
    field_validators = field.validators
    assert observed_types == ["BinaryField"]
    assert field_validators is field.validators

    assert field.clean(lower + 1, None) == lower + 1
    assert field.clean(upper, None) == upper
    with pytest.raises(ValidationError) as too_small:
        field.clean(lower, None)
    assert too_small.value.error_list[0].code == "min_value"
    with pytest.raises(ValidationError) as too_large:
        field.clean(upper + 1, None)
    assert too_large.value.error_list[0].code == "max_value"
