# Contributing

For suspected vulnerabilities, follow [SECURITY.md](SECURITY.md). Use synthetic
data and test-only keys in public issues and pull requests.

## Setup

Use a supported Python version in a repository checkout:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,test]" build twine pip-audit bandit tox
```

Python 3.10/3.11 use Django 5.2; Python 3.12–3.14 support Django 5.2 and 6.0.
The test extra installs psycopg for driver-adaptation tests, but no PostgreSQL
server is needed. Tests and fixture keysets are excluded from release packages;
run the suite from a checkout, not an unpacked wheel or source distribution.

## Checks

```bash
python -m pytest
python -m pytest -c example_project/pytest.ini example_project/example_app/tests
ruff check .
ruff format --check .
pyright --pythonpath "$(command -v python)"
pip-audit
bandit -r tink_fields -x tink_fields/test -ll
python -m build --outdir /tmp/django-tink-fields-build
twine check --strict /tmp/django-tink-fields-build/*
```

Use a fresh output directory for each package validation. Run `tox` for the eight
supported Python/Django combinations and the additional Python 3.10 / Django 5.2
/ Tink 1.13.0 environment. Install all five interpreters for a complete local
matrix. CI runs the same nine test environments plus a quality job.

Bug fixes should include a regression that fails before the fix. Changes to
persistence, lookups, AAD, or migration serialization should verify Python values
and raw database behavior. Include legacy ciphertext compatibility where
relevant. Coverage is a regression signal, not evidence that every backend or
security property has been tested.

Use `ruff format .` and `ruff check . --fix` for mechanical changes. Keep benchmarks
reproducible and report setup, sample method, and regressions as well as gains;
`python -m benchmarks.keyset_cache` is the current cache benchmark.

## Documentation and pull requests

Keep the README, [operations guide](docs/operations.md), upgrade guidance, and
changelog consistent with the public behavior. Check examples against the actual
API. Distinguish SQLite integration, psycopg driver tests, and untested database
server behavior. Preserve historical migration import paths when moving classes.

Describe the concrete behavior change, validation, compatibility limits, and any
data/schema migration. Keep unrelated fixes separate. For stacked PRs, verify the
base before every merge: a PR marked merged into another feature branch is not
necessarily in `main`. Retarget the next PR after its parent lands, and verify
commit ancestry before releasing. Squash/rebase merges may require rebuilding
the remaining stack.

See [RELEASING.md](RELEASING.md) for versioning, package validation, and publication.
