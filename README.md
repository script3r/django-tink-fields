# Django Tink Fields

[![PyPI version](https://badge.fury.io/py/django-tink-fields.svg)](https://badge.fury.io/py/django-tink-fields)
[![Python Support](https://img.shields.io/pypi/pyversions/django-tink-fields.svg)](https://pypi.org/project/django-tink-fields/)
[![Django Support](https://img.shields.io/pypi/djversions/django-tink-fields.svg)](https://pypi.org/project/django-tink-fields/)
[![License](https://img.shields.io/pypi/l/django-tink-fields.svg)](https://pypi.org/project/django-tink-fields/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://github.com/script3r/django-tink-fields/workflows/Tests/badge.svg)](https://github.com/script3r/django-tink-fields/actions)

**Django Tink Fields** is a simple, production-ready way to encrypt Django model fields using the [Google Tink](https://developers.google.com/tink) cryptographic library. It offers drop-in encrypted field types for Django models, so you can protect sensitive data with minimal code changes.

Keywords: Django field encryption, encrypted model fields, Google Tink, AEAD, deterministic encryption.

## ✨ Features

- **🔐 Strong Encryption**: Uses Google Tink for state-of-the-art cryptographic operations
- **🛡️ AEAD Security**: Provides both confidentiality and integrity through Authenticated Encryption with Associated Data
- **🔧 Easy Integration**: Drop-in replacement for Django's standard field types
- **⚡ High Performance**: Optimized with caching and efficient key management
- **🔑 Flexible Key Management**: Support for both cleartext and encrypted keysets
- **☁️ Cloud Integration**: Works with AWS KMS, GCP KMS, and other key management systems
- **📊 Comprehensive Testing**: 97%+ test coverage with modern Python practices
- **🐍 Modern Python**: Supports Python 3.12+ with full type hints

## 🚀 Quick Start

### Installation

```bash
pip install django-tink-fields
```

### Basic Configuration

Add to your `settings.py`:

```python
TINK_FIELDS_CONFIG = {
    "default": {
        "cleartext": True,
        "path": "/path/to/your/keyset.json",
    }
}
```

### Create a Keyset

Generate a test keyset using `tinkey`:

```bash
tinkey create-keyset \
    --out-format json \
    --out keyset.json \
    --key-template AES128_GCM
```

### Use in Your Models

```python
from django.db import models
from tink_fields import EncryptedCharField, EncryptedTextField

class UserProfile(models.Model):
    name = EncryptedCharField(max_length=100)
    bio = EncryptedTextField()
    email = EncryptedEmailField()
    age = EncryptedIntegerField()
    created_at = EncryptedDateTimeField()
```

## 📖 Documentation

### Supported Field Types

| Field Type | Django Equivalent | Description |
|------------|-------------------|-------------|
| `EncryptedCharField` | `CharField` | Encrypted character field |
| `EncryptedTextField` | `TextField` | Encrypted text field |
| `EncryptedEmailField` | `EmailField` | Encrypted email field |
| `EncryptedBooleanField` | `BooleanField` | Encrypted boolean field |
| `EncryptedIntegerField` | `IntegerField` | Encrypted integer field |
| `EncryptedPositiveIntegerField` | `PositiveIntegerField` | Encrypted positive integer field |
| `EncryptedFloatField` | `FloatField` | Encrypted float field |
| `EncryptedDecimalField` | `DecimalField` | Encrypted decimal field |
| `EncryptedUUIDField` | `UUIDField` | Encrypted UUID field |
| `EncryptedJSONField` | `JSONField` | Encrypted JSON field |
| `EncryptedURLField` | `URLField` | Encrypted URL field |
| `EncryptedSlugField` | `SlugField` | Encrypted slug field |
| `EncryptedDateField` | `DateField` | Encrypted date field |
| `EncryptedDateTimeField` | `DateTimeField` | Encrypted datetime field |
| `EncryptedBinaryField` | `BinaryField` | Encrypted binary field |

### Deterministic Field Types

| Field Type | Django Equivalent | Description |
|------------|-------------------|-------------|
| `DeterministicEncryptedTextField` | `TextField` | Deterministic encrypted text field |
| `DeterministicEncryptedCharField` | `CharField` | Deterministic encrypted character field |
| `DeterministicEncryptedEmailField` | `EmailField` | Deterministic encrypted email field |
| `DeterministicEncryptedIntegerField` | `IntegerField` | Deterministic encrypted integer field |
| `DeterministicEncryptedUUIDField` | `UUIDField` | Deterministic encrypted UUID field |
| `DeterministicEncryptedBooleanField` | `BooleanField` | Deterministic encrypted boolean field |
| `DeterministicEncryptedDateField` | `DateField` | Deterministic encrypted date field |
| `DeterministicEncryptedDateTimeField` | `DateTimeField` | Deterministic encrypted datetime field |

### Configuration Options

#### Cleartext Keysets (Development/Testing)

```python
TINK_FIELDS_CONFIG = {
    "default": {
        "cleartext": True,
        "path": "/path/to/cleartext_keyset.json",
    }
}
```

#### Encrypted Keysets (Production)

```python
from tink.integration import gcpkms
from tink import aead

# Register AEAD primitives
aead.register()

# Configure GCP KMS
TINK_MASTER_KEY_URI = "gcp-kms://projects/your-project/locations/global/keyRings/your-keyring/cryptoKeys/your-key"
gcp_client = gcpkms.GcpKmsClient(TINK_MASTER_KEY_URI, "")
gcp_aead = gcp_client.get_aead(TINK_MASTER_KEY_URI)

TINK_FIELDS_CONFIG = {
    "default": {
        "cleartext": False,
        "path": "/path/to/encrypted_keyset.json",
        "master_key_aead": gcp_aead,
    }
}
```

#### Multiple Keysets

```python
TINK_FIELDS_CONFIG = {
    "default": {
        "cleartext": True,
        "path": "/path/to/default_keyset.json",
    },
    "sensitive": {
        "cleartext": False,
        "path": "/path/to/sensitive_keyset.json",
        "master_key_aead": sensitive_aead,
    }
}
```

### Advanced Usage

#### Custom Keyset per Field

```python
class SensitiveData(models.Model):
    # Uses the "sensitive" keyset
    secret = EncryptedCharField(max_length=100, keyset="sensitive")
    # Uses the default keyset
    public_data = EncryptedCharField(max_length=100)
```

#### Associated Authenticated Data (AAD)

Add additional context to your encryption for enhanced security:

```python
def get_aad_for_field(field):
    """Generate AAD based on field and model context."""
    return f"model_{field.model._meta.label}_{field.name}".encode()

class UserData(models.Model):
    # Each field gets unique AAD
    ssn = EncryptedCharField(
        max_length=11, 
        aad_callback=get_aad_for_field
    )
```

#### Field Validation

Encrypted fields support all standard Django field validators:

```python
class ValidatedModel(models.Model):
    email = EncryptedEmailField(unique=True)
    age = EncryptedIntegerField(validators=[MinValueValidator(18)])
    name = EncryptedCharField(max_length=50, blank=False)
```

### Key Management

#### Creating Keysets with tinkey

**Cleartext keyset (development):**
```bash
tinkey create-keyset \
    --out-format json \
    --out dev_keyset.json \
    --key-template AES128_GCM
```

**Encrypted keyset with GCP KMS:**
```bash
tinkey create-keyset \
    --out-format json \
    --out prod_keyset.json \
    --key-template AES256_GCM \
    --master-key-uri=gcp-kms://projects/my-project/locations/global/keyRings/my-keyring/cryptoKeys/my-key
```

**Encrypted keyset with AWS KMS:**
```bash
tinkey create-keyset \
    --out-format json \
    --out prod_keyset.json \
    --key-template AES256_GCM \
    --master-key-uri=aws-kms://arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
```

## 🔒 Security Considerations

### Best Practices

1. **Key Management**: Use encrypted keysets in production with proper key management systems
2. **Key Rotation**: Implement regular key rotation strategies
3. **Access Control**: Restrict access to keyset files and master keys
4. **AAD Usage**: Use AAD to bind encryption to specific contexts
5. **Field Selection**: Only encrypt truly sensitive data to maintain performance

### Limitations

- **No Database Queries**: Encrypted fields cannot be used in database queries (except `isnull`)
- **No Indexing**: Encrypted fields cannot be indexed or used as primary keys
- **Performance**: Encryption/decryption adds computational overhead
- **Key Management**: Requires careful key management and rotation

## 🧪 Testing

The package includes comprehensive tests with 97%+ coverage:

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=tink_fields --cov-report=html

# Run specific test categories
pytest tink_fields/test/test_fields.py  # Basic functionality
pytest tink_fields/test/test_coverage.py  # Edge cases
```

### Integration Test Harness

This repo ships a minimal Django project under `example_project/` that exercises
real model usage and verifies ciphertext at rest, tamper detection, deterministic
lookups, and AAD behavior:

```bash
pytest -c example_project/pytest.ini example_project/example_app/tests
```

## 🛠️ Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/script3r/django-tink-fields.git
cd django-tink-fields

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt

# Install package in development mode
pip install -e .
```

### Code Quality

The project uses modern Python tooling:

```bash
# Format code
black tink_fields/
isort tink_fields/

# Lint code
flake8 tink_fields/

# Type checking
mypy tink_fields/

# Run all quality checks
tox
```

## 📊 Performance

### Benchmarks

| Operation | Time (μs) | Memory (KB) |
|-----------|-----------|-------------|
| Encrypt 1KB | ~50 | ~2 |
| Decrypt 1KB | ~45 | ~2 |
| Field Creation | ~5 | ~1 |

*Benchmarks on Python 3.13, Django 5.2, with AES128_GCM*

### Optimization Tips

1. **Use appropriate field types** - `CharField` for short text, `TextField` for long content
2. **Cache keysets** - Keysets are automatically cached for performance
3. **Minimize AAD complexity** - Keep AAD callbacks simple and fast
4. **Batch operations** - Process multiple records together when possible

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📝 Changelog

### v0.3.2 (Latest)
- ✨ Modernized codebase with Python 3.10+ support
- 🔧 Updated dependencies to latest versions
- 📊 Improved test coverage to 97%+
- 🎨 Applied modern Python formatting and linting
- 📚 Enhanced documentation and examples

### v0.2.0
- 🐛 Fixed compatibility issues
- 📦 Updated package structure

## 📄 License

This project is licensed under the BSD License - see the [LICENSE.txt](LICENSE.txt) file for details.

## 🙏 Acknowledgments

- [Google Tink](https://github.com/google/tink) - The cryptographic library powering this package
- [Django Fernet Fields](https://github.com/orcasgit/django-fernet-fields) - Original inspiration for this project
- [Django Community](https://www.djangoproject.com/community/) - For the amazing framework

## 📞 Support

- 📖 [Documentation](https://github.com/script3r/django-tink-fields#readme)
- 🐛 [Issue Tracker](https://github.com/script3r/django-tink-fields/issues)
- 💬 [Discussions](https://github.com/script3r/django-tink-fields/discussions)

---

**Made with ❤️ for the Django community**
