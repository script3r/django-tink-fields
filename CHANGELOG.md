# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-09-05

### Fixed

- Reject inherited JSON/date transforms and late-registered plaintext lookups on encrypted columns; preserve deterministic exact and SQL null lookups.
- Restore the database timezone when decrypting naive datetime representations under `USE_TZ=True`, preventing new read/re-save shifts without changing ciphertext serialization.
- Encrypt binary buffer contents before driver adaptation, fixing PostgreSQL writes that encrypted the string representation of a `psycopg.Binary` adapter.
- Synchronize primitive construction/publication with `clear_keyset_cache()` so an in-flight load cannot republish a stale primitive after invalidation returns.
- Validate resolved positional and keyword database options; default randomized slug fields to `db_index=False`.
- Expand user-relative keyset paths before validation and report invalid paths, non-UTF-8 files, invalid master primitives, and incompatible AEAD keysets as configuration errors.

### Changed

- Share AEAD/DAEAD primitives across fields using the same cached keyset, reducing repeated construction while retaining weak manager tracking and a bounded shared lookup cache.
- Load existing JSON keysets with Tink's `json_proto_keyset_format` APIs and typed handles, retaining empty encrypted-keyset AAD.
- Document explicit model validation, actual backend test coverage, deterministic representation/rotation limits, and historical data recovery. Add operations, upgrade, and example-project guides.

### Added

- Coverage for all eight advertised Python/Django combinations and a separate Tink 1.13.0 environment in CI and tox. Runtime dependency bounds are unchanged.
- Behavioral regression tests for lookups, timezone round trips, psycopg adaptation, field options, concurrent invalidation, rotation, and configuration errors; 137 library and 6 example tests at release preparation.
- A reproducible cache benchmark showing reduced initialization work and the small warm-call cost of synchronization.

### Upgrade notes

- Inspect existing encrypted slug indexes. Historical migrations may omit the former default, so `makemigrations` can report no changes while an old index remains; a reviewed database-specific removal migration may be needed.
- Already-corrupted PostgreSQL binary values and previously shifted datetimes require application-specific recovery. Correctly stored ciphertext remains readable; this release does not rewrite data automatically.
- Configurations and queries that relied on validation/lookup bypasses now fail early. Deterministic key rotation still requires a coordinated migration for equality and plaintext uniqueness.
- Read the [0.5.0 upgrade guide](docs/upgrading-to-0.5.md) before deployment.

## [0.4.0] - 2026-08-01

### Added

- Exact and `isnull` query coverage for all deterministic field types.
- `db_index` and `unique` support for deterministic encrypted fields.
- Public `clear_keyset_cache()` API for adopting rotated keysets without restarting a process.
- Python 3.14 and Django 5.2 compatibility, with a six-environment CI matrix covering Python 3.10 through 3.14 and Django 5.2/6.0.
- Release, contribution, and security policies.

### Changed

- Keyset settings and files are now loaded lazily on first cryptographic operation, allowing model imports and migration serialization without access to production secrets.
- Keyset handles use a bounded, thread-safe cache keyed by file metadata and the master AEAD instead of an unbounded identity-based cache.
- Packaging now uses PEP 621/639 metadata, one version source, lean optional dependency groups, and excludes internal tests and test keysets from wheels.
- Development tooling now uses Ruff formatting/linting and meaningful Pyright basic type checking.
- Releases use PyPI trusted publishing and validate the version, distributions, and installed wheel before upload.

### Fixed

- Preserve custom `keyset` and `aad_callback` arguments in Django migrations and `Field.clone()`.
- Prepare deterministic lookup values with the same backend-specific conversion used for writes, fixing UUID exact lookups on SQLite and other representation-sensitive backends.
- Force ciphertext equality for deterministic Boolean lookups instead of Django's plaintext Boolean SQL shortcut.
- Serialize encrypted JSON before backend-specific adapters wrap it, fixing invalid round trips on PostgreSQL.
- Allow `field=None` to use `IS NULL` semantics on randomized encrypted fields.
- Reject database expressions and database defaults instead of encrypting their string representation.
- Report malformed keyset configuration and unreadable key material with actionable `ImproperlyConfigured` errors.

### Removed

- Redundant requirements files, legacy bumpversion configuration, and the release script that could publish from an unverified working tree.

## [0.3.2] - 2025-12-27

### Added
- Encrypted counterparts for common Django fields (JSON, UUID, Decimal, Boolean, URL, Slug, Float, PositiveInteger)
- Deterministic UUID and Boolean field support
- Example Django integration project and extended tests for new fields
- Python 3.12+ requirement aligned with Django 6.0

### Changed
- JSON field encryption now preserves structured payloads on round-trip
- Improved README clarity around easy Django field encryption

## [0.3.1] - 2025-09-14

### Added
- Cached keyset handles to reduce repeated keyset file reads
- Example Django project with integration tests covering ciphertext and tamper detection

### Changed
- Registered Tink primitives during direct field module imports
- Prepared deterministic lookup values before encryption for better consistency
- Updated dependency minimums to current releases

### Removed
- Retired legacy CHANGES.md in favor of this changelog

## [0.3.0] - 2025-09-13

### Added
- ✨ Modern Python 3.10+ support
- 🔧 Comprehensive type hints throughout codebase
- 📊 Enhanced test coverage to 97%+
- 🎨 Modern code formatting with Black and isort
- 📚 Comprehensive documentation with examples
- 🛡️ Improved error handling and validation
- ⚡ Performance optimizations with better caching
- 🔑 Enhanced keyset configuration validation

### Changed
- 🔄 Upgraded Django support to 5.2.6+
- 🔄 Upgraded Tink library to 1.12.0+
- 🔄 Upgraded Protobuf to 6.32.1+
- 🔄 Modernized super() calls throughout codebase
- 🔄 Improved string formatting with f-strings
- 🔄 Enhanced dataclass implementation with validation
- 🔄 Better import organization and structure

### Fixed
- 🐛 Fixed compatibility issues with modern Python versions
- 🐛 Improved error messages and exception handling
- 🐛 Enhanced test reliability and coverage

### Removed
- 🗑️ Removed support for Python 3.7-3.9
- 🗑️ Cleaned up legacy code patterns
- 🗑️ Removed unnecessary files and dependencies

## [0.2.0] - 2022-05-28

### Added
- Initial release with basic encrypted field support
- Support for CharField, TextField, EmailField, IntegerField, DateField, DateTimeField
- Cleartext and encrypted keyset support
- Associated Authenticated Data (AAD) support
- Basic test suite

### Changed
- Improved error handling
- Enhanced documentation

### Fixed
- Various bug fixes and improvements

## [0.1.0] - 2022-05-22

### Added
- Initial development release
- Basic encrypted field implementation
- Google Tink integration
- Django field compatibility

---

## Migration Guide

### Upgrading to 0.5.0

See the [0.5.0 upgrade guide](docs/upgrading-to-0.5.md) for required index inspection, stricter field/query restrictions, and historical data recovery limits.

### Upgrading from 0.3.x to 0.4.0

- Run `makemigrations --check`. Models using non-default `keyset` or `aad_callback` options may now produce a corrective `AlterField` migration because older releases omitted those options from migration state.
- Existing ciphertext and keyset files remain compatible. Keeping old keys enabled preserves decryption during rotation, but deterministic exact lookups and plaintext uniqueness do not automatically span key generations; see the [operations guide](docs/operations.md#rotation-and-data-migration).
- Randomized field definitions are intended to reject indexes and uniqueness, but 0.4.0 still has positional-argument and implicit slug-index bypasses fixed in 0.5.0. Deterministic fields accept indexes and uniqueness, subject to schema migration and equality-leakage tradeoffs.
- Configuration errors now occur on the first encrypt/decrypt operation rather than during model import.
- Python 3.10/3.11 and Django 5.2 are supported again; Django 6.0 still requires Python 3.12 or newer.

### Upgrading from 0.2.x to 0.3.0

#### Python Version Requirements
- **Breaking Change**: Python 3.10+ is now required
- Update your Python version or use a virtual environment

#### Dependency Updates
- Django 5.2.6+ (was 3.2.13+)
- Tink 1.12.0+ (was 1.6.1+)
- Protobuf 6.32.1+ (was 3.20.1+)

#### Configuration Changes
No breaking changes to configuration, but consider:
- Updating to use modern Python features
- Taking advantage of improved error messages
- Using new type hints for better IDE support

#### Code Changes
- No breaking changes to field usage
- All existing code should work without modification
- Consider updating to use new features like enhanced AAD support

### Upgrading from 0.1.x to 0.2.x

#### Configuration
- Update `TINK_FIELDS_CONFIG` if using encrypted keysets
- Ensure proper key management setup

#### Field Usage
- No breaking changes to field definitions
- Enhanced error messages may reveal configuration issues

---

## Security Advisories

### 2025-09-13
- **Dependency Updates**: Dependency versions were updated; this historical entry is not a guarantee that those versions remain vulnerability-free.
- **Key Management**: Enhanced keyset validation and error handling
- **Encryption**: No changes to encryption algorithms or security model

---

## Contributors

Thank you to all contributors who have helped improve Django Tink Fields!

### 0.3.0
- [@script3r](https://github.com/script3r) - Major modernization and improvements

### 0.2.0
- [@script3r](https://github.com/script3r) - Initial development and maintenance

---

## Links

- [GitHub Repository](https://github.com/script3r/django-tink-fields)
- [PyPI Package](https://pypi.org/project/django-tink-fields/)
- [Documentation](https://github.com/script3r/django-tink-fields#readme)
- [Issue Tracker](https://github.com/script3r/django-tink-fields/issues)

[Unreleased]: https://github.com/script3r/django-tink-fields/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/script3r/django-tink-fields/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/script3r/django-tink-fields/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/script3r/django-tink-fields/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/script3r/django-tink-fields/compare/v0.2.0...v0.3.1
[0.3.0]: https://github.com/script3r/django-tink-fields/compare/v0.2.0...b53e165
[0.2.0]: https://github.com/script3r/django-tink-fields/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/script3r/django-tink-fields/releases/tag/v0.1.0
