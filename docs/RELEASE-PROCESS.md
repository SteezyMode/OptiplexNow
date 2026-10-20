# Release process

**Only explicit new version tags publish installers.** Changes merged into `main` trigger validation but never publish a release automatically.

## Validation and publication

1. Choose the exact code to ship. Update the Debian package version in `package.py`, release notes, and any current-status references.
2. Run PR CI; merge approved code into `main`. CI runs build, C/Python tests, GTK smoke checks, package metadata checks and installed-package validation.
3. Perform manual device testing for changed UI, networking or streaming behavior. Record any untested flows in [Beta acceptance](BETA-ACCEPTANCE.md).
4. Create a **new** `vX.Y.Z` Git tag at the intended `main` commit, using local `git tag` and `git push` or the authenticated GitHub CLI/API. Never repoint an existing release tag.
5. `.github/workflows/release.yml` rebuilds the tagged source, verifies that tag/version/package match, and publishes immutable GitHub assets:
   - `OptiPlex-Now_X.Y.Z_amd64.deb`
   - `OptiPlex-Now_amd64.deb`
   - `SHA256SUMS`
6. Verify [GitHub Releases](https://github.com/SteezyMode/OptiplexNow/releases), workflow success, SHA256SUMS, package metadata and real installation. Only then call a version published.

An absent tag means no release, even when code is merged. A matching tag with a failed workflow also does not produce an accepted release. New fixes get a new patch version; do not overwrite past artifacts.

## Safety and rollback

- CI is not a streaming acceptance test. A green workflow does not prove login, Moonlight certificate exchange, host connectivity or user data preservation.
- The release pipeline must not touch the owner's server or deployed containers.
- Reversion is installing an older versioned `.deb` while preserving compatible settings and identity; verify migrations before relying on rollback.
- No workflow may publish from a PR or ordinary `main` push. Do not add a manual publisher without a deliberate release-control review.

See [Contributing](../CONTRIBUTING.md) and [Current status](CURRENT-STATUS.md).
