# Code review and landing plan — 2026-09-05

Reviewed the library, tests, example project, packaging, and CI from `main` at
`72c1661`. The original suite passed 76 library tests with 95.28% coverage, but
missed several value-conversion and ORM restriction failures. This stack adds
behavioral regressions instead of treating coverage percentage as proof of
correctness.

## Changes in this stack

| Priority | Finding and evidence | Resolution |
| --- | --- | --- |
| High | JSON key lookups, date transforms, and late-registered lookups bypassed the ciphertext restrictions. Twelve new cases failed to raise `FieldError`. | [PR #7](https://github.com/script3r/django-tink-fields/pull/7): explicit lookup allowlist and concrete equality classes. |
| High | With `USE_TZ=True`, SQLite datetime reads lost timezone information. Re-saving under a different default timezone could shift the instant. Six new cases failed. | [PR #8](https://github.com/script3r/django-tink-fields/pull/8): restore the database timezone after decrypting naive datetime representations, preserving serialization. |
| High | An in-flight `cached_property` getter could publish an old primitive after cache invalidation returned. | [PR #9](https://github.com/script3r/django-tink-fields/pull/9): synchronize construction/publication with invalidation; test concurrent loads and actual rotation for both primitive types. |
| Medium | One hundred fields sharing a keyset constructed 100 separate primitives. | PR #9: share one primitive per type per cached keyset, retaining bounded caching and weak manager references. |
| High | PostgreSQL binary writes encrypted the string representation of `psycopg.Binary`, corrupting the original contents. Four real-driver cases failed. | [PR #10](https://github.com/script3r/django-tink-fields/pull/10): convert buffer contents before encryption, and adapt only final ciphertext. |
| Medium | Positional database options bypassed validation; randomized slug fields silently inherited an index. | [PR #11](https://github.com/script3r/django-tink-fields/pull/11): validate resolved options and serialize `db_index=False` for encrypted slugs. |
| Medium | User-relative keyset paths were checked before expansion; invalid encodings and incompatible AEAD primitives escaped as low-level exceptions. | Final keyset-loading PR: normalize paths and improve configuration errors. |
| Medium | CI omitted two advertised Python/Django combinations and never pinned the minimum Tink version. | Final PR: add Python 3.13/3.14 with Django 5.2 and a Tink 1.13.0 job; keep tox aligned. |
| Low | Keyset loading used the older reader/handle API and untyped handles. | Final PR: use Tink's explicit JSON format API and `KeysetHandle` annotations, with legacy keyset interoperability coverage. |

## Performance evidence

Run `python -m benchmarks.keyset_cache` from the repository root. The script
reports the median of seven samples, with 20 initializations or 100,000 warm
encryptions per sample. On this Mac with Python 3.14, at the cache PR boundary:

| Operation | Before | After |
| --- | ---: | ---: |
| Initialize 100 managers sharing one keyset | 2.227 ms | 1.466 ms |
| Warm primitive access and encryption | 0.504 µs | 0.598 µs |
| Primitive constructions for 100 managers | 100 | 1 |

The improvement is in initialization and wrapper reuse. Locking adds a small
steady-state cost; these measurements do not establish application throughput
or performance under contention. Encryption itself occurs outside the cache
lock. Calls that obtained an old primitive can finish with it, and every worker
process must reload or restart after rotation.

## Landing and rollout

Land the PRs in dependency order. Each PR targets its predecessor so its diff
contains only that change. After a parent lands, retarget the next PR to `main`
if GitHub has not done so automatically. Merge commits preserve the stack's
ancestry; squash or rebase merges require rebasing the remaining branches onto
the new `main` before landing them.

- Existing correctly serialized ciphertext remains readable. No key or payload
  format migration is introduced by the lookup, timezone, cache, or loading PRs.
- For encrypted slug fields, generate and apply the index-removal migration.
  Positional configurations that violate documented restrictions now fail early.
- PostgreSQL binary rows already corrupted by adapter stringification require
  application-specific recovery. In particular, a stored memoryview description
  does not contain the original bytes and cannot be repaired by this patch.
- The final README corrects the validation claim: Django model `save()` does not
  automatically call `full_clean()`.

## Follow-up priorities and limits

1. **High — deterministic rotation needs an explicit migration design.** A new
   primary key produces different ciphertext. Retaining old enabled keys allows
   decryption but does not make new exact lookups match old rows. A unique index
   also cannot enforce plaintext uniqueness across key generations. The README
   now explains this limitation. A future implementation needs a coordinated
   rewrite, an explicit key-generation strategy, or a separately designed search
   index; simply clearing the cache is insufficient.

2. **High — define canonical deterministic representations before expanding
   backend guarantees.** With Django's PostgreSQL adapter, equal aware datetime
   instants expressed in Tokyo and UTC produce different encrypted bytes because
   the serialized strings retain different offsets. This was reproduced without
   a database server using the real PostgreSQL backend. Changing serialization
   silently would invalidate equality against existing rows, so it needs a
   versioned migration plan. UUID representations can also differ by backend.

3. **Medium — add real PostgreSQL and MySQL server CI.** This stack tests SQLite
   persistence and the real psycopg binary adapter, but does not claim server
   integration coverage for PostgreSQL, MySQL, or Oracle. Add service-backed
   tests for schema changes, constraints, datetime conversions, and binary
   persistence before strengthening the documented backend support.

4. **Medium — remove temporary field-type mutation during validator creation.**
   `EncryptedField.validators` temporarily changes `_internal_type` on a shared
   field instance. This is a potential concurrency hazard, not a reproduced
   failure in this review. A replacement should construct the concrete field's
   validators without changing shared metadata and retain backend range checks.

5. **Low — improve typing and test organization incrementally.** The older
   coverage-focused tests contain duplicate assertions and stale line-number
   comments. Consolidate them around observable behavior while retaining the
   new regression cases. Package a `py.typed` marker only after testing the
   public Django field annotations with downstream type checkers. Module splits
   should preserve public field import paths used in existing migrations.

## Validation

At the top of the stack, all **137 library tests** and **6 example integration
tests** pass locally on both Python 3.14 / Django 6.0 / Tink 1.16.1 and Python
3.10 / Django 5.2 / Tink 1.13.0. Library coverage is **97.62%**. Ruff lint/format
and Pyright pass. Distribution builds and strict Twine validation pass; the
tested environment has no known vulnerabilities reported by pip-audit, and
Bandit reports no medium/high findings. GitHub CI provides the remaining interpreter combinations;
consult each PR's checks for the status of its exact head commit.

The tests cover raw ciphertext/SQL NULL storage, tamper detection, migrations,
real driver adaptation, timezone round trips, keyset interoperability, real key
rotation, bounded caching, and concurrent invalidation. They do not establish
formal cryptographic correctness or recovery of previously corrupted data.

## Upstream references

Tink's [Python keyset example](https://developers.google.com/tink/generate-plaintext-keyset)
uses `json_proto_keyset_format` with explicit secret-key access. The loading
change retains the empty associated data used for existing encrypted keysets.
[Django's custom field documentation](https://docs.djangoproject.com/en/6.0/howto/custom-model-fields/)
describes the separation between database preparation and conversion on reads;
its [model validation documentation](https://docs.djangoproject.com/en/6.0/ref/models/instances/#validating-objects)
explains that `save()` does not call `full_clean()` automatically.
