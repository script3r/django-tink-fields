# Operations and limitations

## Configuration and key access

`TINK_FIELDS_CONFIG` maps keyset names to these options:

| Option | Requirement |
| --- | --- |
| `path` | Nonempty string or path-like object naming a readable Tink JSON keyset. `~` is expanded and the path is resolved on first use. |
| `cleartext` | Boolean, default `False`. `True` means the file contains the secret keys directly. |
| `master_key_aead` | A Tink `aead.Aead` instance, required when `cleartext=False`. Construct it with your KMS integration before using the field. |

Field options `keyset="default"` and `aad_callback=...` select the configuration
and authenticated context. The callback receives the **field**, not a model
instance, and must return bytes. The default AAD is empty. It therefore does not
bind ciphertext to a row, tenant, field, or model; applications needing stable
field context must supply a callback. The callback alone cannot provide
row-specific authorization or tenant isolation.

The package registers AEAD and deterministic AEAD primitives, but does not
provision KMS keys, discover credentials, or configure a KMS client. Encrypted
keyset loading uses empty keyset-encryption AAD; that is separate from the field's
payload AAD callback. A keyset encrypted with different keyset AAD needs an
appropriate external conversion before it can be loaded by this package.

Models and migrations can be imported without opening key files. Successful
loads remain cached; editing settings or replacing a file does not automatically
refresh every active field. There is no filesystem watcher or polling interval.
Errors in the config, key file, encoding, or primitive choice surface on first
use as `ImproperlyConfigured`. Payload authentication failures propagate as
Tink errors; do not turn a failed decrypt into a missing or empty value.

## Database behavior

The encrypted column uses Django's `BinaryField` database type. Conversion to a
Python value happens when Django loads the field, including `values()` and
`values_list()` of the field itself. These calls return plaintext to application
code; encryption does not protect logs, exports, caches, or responses containing
those values.

| Operation | Randomized | Deterministic |
| --- | --- | --- |
| `isnull`, `field=None` | Supported | Supported |
| Exact equality | Rejected | Supported for matching prepared bytes/key/AAD |
| `in`, range, substring, case-insensitive lookups | Rejected | Rejected |
| JSON key and date transforms | Rejected | Rejected |
| Field-level `db_index` and `unique` | Rejected | Supported, subject to representation and rotation limits |
| `primary_key`, `db_default` | Rejected | Rejected |
| `F()` or other expressions assigned to a field; `bulk_update()` | Rejected | Rejected |

Literal saves, `bulk_create()`, and literal `QuerySet.update()` encrypt values.
Django does not run `full_clean()` automatically for these operations. A model
form validates its included fields; call `full_clean()` yourself when required
for other write paths.

Lookup restrictions apply to the field's lookup/transform interface. They are
not a SQL sandbox: explicit SQL functions, casts, ordering, aggregates, joins,
custom constraints, and raw SQL can still operate on ciphertext and have no
implied plaintext semantics. `Meta.indexes` and `Meta.constraints` are not a
substitute for the field-level restrictions or a supported way to query
randomized ciphertext. Do not use database arithmetic or SQL transformations to
modify encrypted values.

Deterministic equality compares serialized bytes, not a plaintext database
collation or a normalized application identity. PostgreSQL datetime offsets and
backend-specific UUID representations are known examples where equivalent
application values can serialize differently. Changing backend, connection
timezone, normalization, keyset, or AAD may require a data migration. Full server
integration is currently tested only with SQLite; psycopg coverage exercises
actual driver adaptation without a PostgreSQL server. MySQL and Oracle server
behavior is not established by the suite.

## Cache behavior and performance

Keyset handles and their AEAD/DAEAD primitives are shared across managers for
matching paths, file metadata, cleartext mode, and hashable master AEAD values.
An unhashable master AEAD is supported but bypasses the shared lookup cache.
The shared lookup cache holds up to 32 entries. Active fields can retain entries
that were evicted from that shared cache, so this is not a hard process-wide
memory bound.

`clear_keyset_cache()` clears cached entries referenced by active managers and
waits for primitive construction/publication under the cache lock. Operations
that already obtained a primitive may finish with it. Encryption and decryption
happen outside that lock. Reloading one process does not reload another process
or update an independently retained primitive in application code.

Use `python -m benchmarks.keyset_cache` from a repository checkout to measure
shared-keyset initialization and warm encryption on your environment. The
[review measurements](code-review-2026-09.md#performance-evidence) show reduced
initialization work and a small warm-call synchronization cost, not a universal
throughput improvement.

## Rotation and data migration

For randomized encryption, a typical rotation adds a primary key while retaining
old enabled keys for decryption. Replace the keyset atomically and reload all
workers. Verify old-data reads and new-data writes before disabling an old key;
old backups may also need it. Retaining an old key does not rewrite old rows.

For deterministic encryption, a new primary key changes the ciphertext produced
for the same prepared value. Exact lookups then miss old ciphertext, and a
unique ciphertext index can admit a plaintext duplicate across generations.
There is no automatic multi-generation lookup or rotation migration API.
Coordinate writes, rewrite affected rows under the chosen generation, and verify
plaintext uniqueness and recovery as part of an application-specific migration.
Do not treat a process restart as that migration.

Likewise, converting a plaintext column to an encrypted field is not an in-place
schema-only change. Use a staged migration with separate storage, controlled
copying through the Python encryption path, verification, and a planned cutover.
Do not discard the original column or keys until recovery has been verified.

See the [0.5.0 upgrade guide](upgrading-to-0.5.md) for known historical data and
index issues, and [SECURITY.md](../SECURITY.md) for reporting defects.
