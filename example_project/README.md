# Example integration project

This is a test harness for model persistence, not a deployable service. Its
in-memory SQLite database, fixed secret key, cleartext test keysets, and
`USE_TZ=False` settings are for tests only. The library's separate datetime suite
also exercises `USE_TZ=True` and non-UTC connection timezones.

From the repository root, install the test extra and run:

```bash
python -m pip install -e ".[test]"
python -m pytest -c example_project/pytest.ini example_project/example_app/tests
```

The six tests cover field round trips, raw ciphertext, tamper rejection, stable
AAD, and deterministic lookup behavior. They do not test PostgreSQL, MySQL, or
Oracle servers. The library suite contains additional psycopg adapter tests that
do not need a running server.

The example app disables migrations so pytest creates its tables directly. For
an application, configure persistent storage, your own secret key and keysets,
and normal Django migrations; review [operations](../docs/operations.md) and the
[upgrade guide](../docs/upgrading-to-0.5.md) before using existing data.
