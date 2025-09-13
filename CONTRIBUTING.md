# Contributing to Django Tink Fields

Thank you for your interest in contributing to Django Tink Fields! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Django 5.2 or higher
- Git
- Virtual environment (recommended)

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/django-tink-fields.git
   cd django-tink-fields
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements-dev.txt
   pip install -e .
   ```

4. **Run Tests**
   ```bash
   pytest
   ```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tink_fields --cov-report=html

# Run specific test files
pytest tink_fields/test/test_fields.py
pytest tink_fields/test/test_coverage.py

# Run with verbose output
pytest -v

# Run tests for specific Python versions
tox
```

### Test Coverage

We maintain high test coverage (97%+). When adding new features:

1. Write comprehensive tests
2. Ensure edge cases are covered
3. Test error conditions
4. Verify backward compatibility

### Test Structure

```
tink_fields/test/
├── test_fields.py          # Basic functionality tests
├── test_coverage.py        # Edge cases and error conditions
├── models.py               # Test models
└── settings/               # Test settings
    ├── base.py
    └── sqlite.py
```

## 📝 Code Style

### Formatting

We use modern Python tooling for consistent code style:

```bash
# Format code with Black
black tink_fields/

# Sort imports with isort
isort tink_fields/

# Run both
black tink_fields/ && isort tink_fields/
```

### Linting

```bash
# Run flake8
flake8 tink_fields/

# Run mypy for type checking
mypy tink_fields/
```

### Code Standards

- **Type Hints**: Use type hints for all functions and methods
- **Docstrings**: Follow Google-style docstrings
- **Error Handling**: Use specific exception types
- **Constants**: Use UPPER_CASE for module-level constants
- **Imports**: Group imports (standard library, third-party, local)

## 🔧 Development Guidelines

### Adding New Features

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Write Tests First**
   - Add tests for new functionality
   - Ensure existing tests still pass
   - Aim for 100% coverage of new code

3. **Implement the Feature**
   - Follow existing code patterns
   - Add comprehensive docstrings
   - Include type hints

4. **Update Documentation**
   - Update README.md if needed
   - Add docstring examples
   - Update any relevant comments

### Bug Fixes

1. **Reproduce the Bug**
   - Create a test that demonstrates the issue
   - Ensure the test fails before your fix

2. **Fix the Bug**
   - Implement the minimal fix
   - Ensure all tests pass

3. **Update Tests**
   - Add regression tests
   - Verify the fix works

### Code Review Process

1. **Self Review**
   - Run all tests locally
   - Check code style and formatting
   - Verify documentation is updated

2. **Pull Request**
   - Provide clear description of changes
   - Reference any related issues
   - Include test results

3. **Review Feedback**
   - Address reviewer comments
   - Update code as needed
   - Re-run tests after changes

## 📋 Pull Request Guidelines

### Before Submitting

- [ ] All tests pass
- [ ] Code is formatted with Black and isort
- [ ] No linting errors (flake8, mypy)
- [ ] Documentation is updated
- [ ] Commit messages are clear and descriptive

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] All existing tests still pass

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
```

## 🐛 Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Environment Information**
   - Python version
   - Django version
   - Package version
   - Operating system

2. **Reproduction Steps**
   - Clear steps to reproduce
   - Minimal code example
   - Expected vs actual behavior

3. **Error Information**
   - Full error traceback
   - Log messages
   - Screenshots if applicable

### Feature Requests

For feature requests, please include:

1. **Use Case**
   - Why is this feature needed?
   - How would it be used?

2. **Proposed Solution**
   - How should it work?
   - Any implementation ideas?

3. **Alternatives**
   - Other ways to solve the problem?
   - Workarounds currently used?

## 📚 Documentation

### Code Documentation

- Use Google-style docstrings
- Include type hints
- Provide examples in docstrings
- Document all public APIs

### README Updates

- Keep installation instructions current
- Update examples for new features
- Maintain clear structure
- Use consistent formatting

## 🔄 Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] Version number incremented
- [ ] CHANGELOG.md updated
- [ ] Release notes prepared

## 🤝 Community Guidelines

### Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow Django's code of conduct

### Getting Help

- Check existing issues and discussions
- Ask questions in GitHub discussions
- Join Django community forums
- Read the documentation

## 📞 Contact

- **Maintainer**: [@script3r](https://github.com/script3r)
- **Issues**: [GitHub Issues](https://github.com/script3r/django-tink-fields/issues)
- **Discussions**: [GitHub Discussions](https://github.com/script3r/django-tink-fields/discussions)

Thank you for contributing to Django Tink Fields! 🎉
