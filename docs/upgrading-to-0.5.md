# Upgrading to 0.5.0

Version 0.5.0 fixes persistence and query errors without changing the Tink keyset
format or deliberately rewriting existing ciphertext. It also enforces field
restrictions that older versions sometimes accepted. Review this guide before
upgrading a deployed application from 0.4.x or earlier.

## Before deployment

1. Back up the database and the keysets needed to decrypt it, and verify recovery
   in a protected environment. Keep keys separate from database backups.
2. Upgrade a staging copy with `python -m pip install django-tink-fields==0.5.0`.
   Exercise reads, writes, forms, migrations, and deterministic lookups using
   your production database backend and timezone settings.
3. Review the cases below. Install the release on every worker and restart the
   workers together with the planned application/schema changes.

Do not rotate keys or change database/timezone settings as an incidental part
of this upgrade. Those changes need their own data migration plan.

## Encrypted slug indexes

`EncryptedSlugField` now defaults to `db_index=False`. Earlier releases inherited
Django's plaintext slug index even though randomized encryption cannot use it
for equality searches.

Run `makemigrations` and inspect the actual database indexes. **An empty migration
plan does not prove that the old index is gone.** Old migration files can contain
`EncryptedSlugField()` without `db_index=True`; loading those migrations with
0.5.0 uses the new default, so Django may see no state change to migrate.

Use your database's index inspection tools, or Django's
`connection.introspection.get_constraints(cursor, table_name)`, to identify the
old index. If it remains, create and review a backend-specific database migration
to remove that particular index. Preserve primary-key, unique, composite, and
application-defined indexes. An `AlterField` that changes `False` to `False`
will not reliably remove a physical index absent from Django's migration state.

Existing rows remain readable while the unused index exists; removing it avoids
unnecessary storage and write overhead. Restoring the old application version
requires separately reviewing whether its expected index should be restored.

## PostgreSQL binary data

Older `EncryptedBinaryField` writes using psycopg could encrypt an adapter's text
representation instead of the original buffer. For example, a read could return
bytes describing `Binary(b'...')`; a memoryview could be represented only by an
object description.

New writes encrypt the original bytes. Correctly stored old ciphertext remains
readable, but this release cannot automatically reconstruct corrupted values.
Validate suspect data against an authoritative source and recover it through an
application-specific migration or backup. Do not use `eval()` on recovered text
or assume every adapter-looking value is corrupt: legitimate payloads may
contain that text too. A memory address does not retain the original contents.

## Datetimes

Under `USE_TZ=True`, decrypted naive datetime representations now regain the
**database connection timezone**, matching the timezone used when they were
prepared for storage. This fixes timezone loss on SQLite and prevents subsequent
re-saves from shifting otherwise-correct values. Existing explicit UTC offsets
are preserved; `USE_TZ=False` keeps naive datetime behavior.

The fix cannot detect timestamps already shifted by earlier read/save cycles.
Compare those values with an authoritative source if the application was
exposed to that behavior. Keep `USE_TZ` and the database connection's `TIME_ZONE`
consistent with the settings used to write existing data.

Deterministic datetime equality still depends on the serialized representation.
In the PostgreSQL backend, equal instants with different UTC offsets can produce
different ciphertext. Normalize new application values consistently, and design
a migration for existing values before changing the representation policy.
This release does not introduce backend-independent canonical serialization.

## Queries and field options

- JSON key lookups, JSON projections such as `values("payload__key")`, date
  transforms, and late-registered custom lookups now fail early. Randomized
  fields support `isnull` and `field=None`; deterministic fields additionally
  support exact equality.
- Positional `primary_key`, `unique`, `db_index`, and `db_default` arguments now
  receive the same restrictions as keyword arguments. Review model definitions
  and historical migrations that relied on a bypass. Primary keys and database
  defaults are unsupported on all encrypted fields; only deterministic fields
  allow field-level uniqueness and indexes.
- Database expressions, including the `CASE` expressions used by `bulk_update()`,
  are unsupported for encrypted assignments. Use per-instance `save()` or a
  literal `QuerySet.update()` as appropriate. Neither calls `full_clean()`.

## Keysets and rotation

Cleartext and encrypted JSON keysets remain compatible. `master_key_aead` must
be a Tink `Aead` instance for an encrypted keyset; a key URI or raw bytes alone
are not enough. User-relative paths are expanded before validation, and invalid
configuration is reported when the keyset is first needed.

Primitive construction and cache invalidation are synchronized. An operation
that already obtained an old primitive can still finish with it. Invalidation is
local to one process: restart or explicitly reload every worker.

Promoting a deterministic primary key changes lookup ciphertext. Retaining old
enabled keys preserves decryption, but exact lookups and plaintext uniqueness do
not span old and new ciphertext generations automatically. A coordinated data
migration is required; `clear_keyset_cache()` alone is insufficient. See
[operations and limitations](operations.md).

## Older upgrades

When upgrading from 0.3.x or earlier, also review the
[0.4.0 migration notes](../CHANGELOG.md#upgrading-from-03x-to-040). Older migrations
may have omitted custom `keyset` and `aad_callback` options. Correcting migration
state does not itself re-encrypt stored rows.
