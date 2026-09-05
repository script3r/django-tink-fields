"""Validate field options after Django has resolved arguments and defaults."""

from inspect import signature

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models import Field

from tink_fields import DeterministicEncryptedCharField, EncryptedSlugField, EncryptedTextField

from . import models


@pytest.mark.parametrize(
    "args, option",
    [
        ((None, None, True), "primary_key"),
        ((None, None, False, None, True), "unique"),
        ((None, None, False, None, False, False, False, True), "db_index"),
    ],
)
def test_randomized_fields_reject_positional_database_options(args, option):
    with pytest.raises(ImproperlyConfigured, match=f"property `{option}`"):
        EncryptedTextField(*args)


def test_deterministic_fields_reject_positional_primary_keys():
    with pytest.raises(ImproperlyConfigured, match="property `primary_key`"):
        DeterministicEncryptedCharField(None, None, True, 25)


def test_deterministic_fields_keep_positional_indexes_and_uniqueness():
    field = DeterministicEncryptedCharField(None, None, False, 25, True, False, False, True)
    assert field.unique is True
    assert field.db_index is True


def test_randomized_slug_defaults_to_no_index_and_serializes_it():
    field = EncryptedSlugField()
    assert field.db_index is False
    assert field.clone().db_index is False
    assert field.deconstruct()[3]["db_index"] is False


def test_randomized_slug_still_rejects_explicit_indexes():
    with pytest.raises(ImproperlyConfigured, match="property `db_index`"):
        EncryptedSlugField(db_index=True)


@pytest.mark.django_db
def test_randomized_slug_has_no_database_index():
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, models.EncryptedExtended._meta.db_table)
    assert not any(constraint["index"] and constraint["columns"] == ["slug"] for constraint in constraints.values())


@pytest.mark.parametrize("field_cls", [EncryptedTextField, DeterministicEncryptedCharField])
def test_positional_database_defaults_are_rejected(field_cls):
    parameters = signature(Field).parameters
    arguments = [parameter.default for parameter in parameters.values()]
    arguments[list(parameters).index("db_default")] = None
    with pytest.raises(ImproperlyConfigured, match="property `db_default`"):
        field_cls(*arguments)
