# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive contributing guidelines
- Detailed development setup instructions
- Performance benchmarks section
- Security best practices guide

## [0.3.2] - 2025-12-27

### Added
- Encrypted counterparts for common Django fields (JSON, UUID, Decimal, Boolean, URL, Slug, Float, PositiveInteger)
- Deterministic UUID and Boolean field support
- Example Django integration project and extended tests for new fields

### Changed
- JSON field encryption now preserves structured payloads on round-trip
- Improved README clarity around easy Django field encryption

## [0.3.1] - 2025-12-27

### Added
- Cached keyset handles to reduce repeated keyset file reads
- Example Django project with integration tests covering ciphertext and tamper detection

### Changed
- Registered Tink primitives during direct field module imports
- Prepared deterministic lookup values before encryption for better consistency
- Updated dependency minimums to current releases

### Removed
- Retired legacy CHANGES.md in favor of this changelog

## [0.3.0] - 2024-12-19

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

## [0.2.0] - 2023-XX-XX

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

## [0.1.0] - 2023-XX-XX

### Added
- Initial development release
- Basic encrypted field implementation
- Google Tink integration
- Django field compatibility

---

## Migration Guide

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

### 2024-12-19
- **Dependency Updates**: Updated all dependencies to latest secure versions
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
