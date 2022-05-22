from datetime import date, datetime

from django.db import connection, models as dj_models
from django.utils.encoding import force_bytes, force_str
import pytest

from . import models


@pytest.mark.parametrize(
    "model,vals",
    [
        (models.EncryptedText, ["foo", "bar"]),
        (models.EncryptedChar, ["one", "two"]),
        (models.EncryptedCharWithFixedAad, ["foo", "bar"]),
        (models.EncryptedEmail, ["a@example.com", "b@example.com"]),
        (models.EncryptedInt, [1, 2]),
        (models.EncryptedDate, [date(2015, 2, 5), date(2015, 2, 8)]),
        (
            models.EncryptedDateTime,
            [datetime(2015, 2, 5, 15), datetime(2015, 2, 8, 16)],
        ),
        (models.EncryptedCharWithAlternateKeyset, ["foo", "bar"]),
    ],
)
class TestEncryptedFieldQueries(object):
    def test_insert(self, db, model, vals):
        """Data stored in DB is actually encrypted."""
        field = model._meta.get_field("value")
        aad_callback = getattr(field, "_aad_callback")
        model.objects.create(value=vals[0])
        with connection.cursor() as cur:
            cur.execute("SELECT value FROM %s" % model._meta.db_table)
            data = [
                force_str(
                    field._get_aead_primitive().decrypt(
                        force_bytes(r[0]), aad_callback(field)
                    )
                )
                for r in cur.fetchall()
            ]

        assert list(map(field.to_python, data)) == [vals[0]]
