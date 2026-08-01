# Contributing

Contributions are welcome. For security-sensitive reports, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Setup

Use any supported Python version and install the project in an isolated environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,test]" build twine pip-audit bandit tox
```

## Checks

Run the same checks used by CI:

```bash
python -m pytest
python -m pytest -c example_project/pytest.ini example_project/example_app/tests
ruff check .
ruff format --check .
pyright --pythonpath "$(command -v python)"
python -m build
twine check --strict dist/*
```

Run `tox` to exercise the supported Python and Django combinations available on your machine.

Bug fixes should include a regression test. Changes to field persistence, lookup preparation, AAD, or migration serialization should test both the Python round trip and raw database behavior. Never commit real key material; the repository keysets are test-only fixtures.

Use `ruff format .` and `ruff check . --fix` for mechanical formatting and safe lint fixes. Keep public behavior and security tradeoffs documented in the README and changelog.

## Pull requests

Describe the user-visible behavior, compatibility implications, and commands used to verify the change. Keep unrelated changes separate. A maintainer will review cryptographic API changes, data migration implications, and release notes particularly carefully.
