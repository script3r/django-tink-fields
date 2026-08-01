# Releasing

Releases are built from a published GitHub release and uploaded to PyPI using trusted publishing.

## One-time repository setup

1. Configure a PyPI trusted publisher for the `django-tink-fields` project, this GitHub repository, the `release.yml` workflow, and the `pypi` environment.
2. Protect the GitHub `pypi` environment as appropriate for the project.

No long-lived PyPI password or API token is required by the workflow.

## Release checklist

1. Choose a semantic version and update `tink_fields/_version.py` and `CHANGELOG.md`.
2. Run the complete local gates:

   ```bash
   tox
   ruff check .
   ruff format --check .
   pyright --pythonpath "$(command -v python)"
   python -m build
   twine check --strict dist/*
   ```

3. Confirm CI passes on the release commit.
4. Create and push a signed tag matching the package version:

   ```bash
   git tag -s v0.4.0 -m "Release 0.4.0"
   git push origin v0.4.0
   ```

5. Draft a GitHub release from that existing tag using the matching changelog section. Review it, then publish it.
6. Confirm the publish workflow succeeds and the wheel and source distribution appear on PyPI.
7. Install the exact version from PyPI into a clean environment and import `tink_fields`.

The workflow rejects a GitHub release whose tag does not match the package version, validates both distributions, smoke-tests the wheel in a clean environment, and only then publishes.
