# Releasing

A published GitHub release triggers `.github/workflows/release.yml`, which builds
and uploads the wheel and source distribution to PyPI with trusted publishing.
Creating a draft does not publish packages. Publication is a separate action from
merging a PR or pushing a tag.

## Repository setup

Configure a PyPI trusted publisher for this repository, the `release.yml`
workflow, and the `pypi` environment. Apply the repository's intended environment
protections. No long-lived PyPI password or API token is needed by the workflow.
Use an authenticated maintainer session to create the GitHub release.

## Prepare the release

1. Choose an unused semantic version. A change to accepted field definitions or
   behavior requiring upgrade guidance can justify a minor release while the
   package is pre-1.0; do not call such changes transparent patch upgrades.
2. Update `tink_fields/_version.py`, the version regression, and `CHANGELOG.md`.
   Date the changelog entry for publication. Keep prior historical entries intact
   unless a correction is explicitly explained.
3. Audit README examples, support claims, security policy, operations/upgrade
   guides, example-project instructions, and the release notes. Describe known
   limits and recovery requirements. Check local Markdown links and the contents
   of the source distribution; linked guides must not disappear from packaging.
4. Run the release gates from a clean checkout, with all supported interpreters
   installed:

   ```bash
   tox
   ruff check .
   ruff format --check .
   pyright --pythonpath "$(command -v python)"
   pip-audit
   bandit -r tink_fields -x tink_fields/test -ll
   release_dist=$(mktemp -d /tmp/django-tink-fields-dist.XXXXXX)
   python -m build --outdir "$release_dist"
   twine check --strict "$release_dist"/*
   ```

   Inspect the wheel and source distribution. Tests and fixture keysets must
   remain excluded. Use a fresh directory so old distributions cannot be
   mistaken for this release. Smoke-test the built wheel in a clean environment.
5. Merge the release preparation PR into `main` after CI passes. Fetch `main`,
   verify that every intended feature commit is an ancestor, and confirm CI
   passes for the **exact commit to be tagged**. A merged stacked PR may only be
   in a feature branch, so PR status alone is insufficient.

## Tag and publish

Create an annotated tag pointing at the verified commit, not an implicit latest
branch tip. Sign it with `git tag -s` when a trusted signing identity is configured.
Otherwise use `git tag -a`; an unsigned annotated tag must not be described as a
signed or identity-verified tag. Do not create an untrusted signing key solely to
make a release appear signed.

For a 0.5.0 release, after choosing the verified commit:

```bash
release_version=0.5.0
release_tag="v${release_version}"
release_commit=$(git rev-parse origin/main)
git tag -a "$release_tag" "$release_commit" -m "Release ${release_version}"
git push origin "$release_tag"
```

The commands assume `origin/main` still identifies the commit whose CI was
checked. Recheck if the branch moved. Never move or replace an existing release
tag to publish different code.

Create a draft from that existing tag and the reviewed release notes:

```bash
gh release create "$release_tag" --verify-tag --draft \
  --title "$release_tag" --notes-file /path/to/release-notes.md
gh release view "$release_tag"
```

Verify the version, target commit, migration instructions, and links in the
draft, then publish it:

```bash
gh release edit "$release_tag" --draft=false --latest
```

The workflow checks that the tag matches the package version, builds and
validates both distributions, and smoke-tests the wheel before publishing. It
does not itself rerun the full test matrix; checking CI on the tagged commit is
a release responsibility.

## Verify publication

1. Confirm the `Publish release` workflow succeeds.
2. Check PyPI's version-specific JSON metadata for both the wheel and source
   distribution, including the version, upload records, and SHA-256 digests.
3. Install the exact version from PyPI in a fresh environment and run an isolated
   import (`python -I`) so an editable checkout cannot mask a bad wheel. Verify
   `tink_fields.__version__` and an encryption/decryption round trip.
4. Check the published README and upgrade links. Report the GitHub release and
   PyPI version URLs, and distinguish publication from an unverified draft.

If publishing fails, inspect the workflow logs and whether any files already
reached PyPI before retrying. PyPI versions/files cannot be overwritten. Do not
move a released tag or upload different bytes under an existing filename; if a
published artifact is wrong, prepare a new version with explicit release notes.
