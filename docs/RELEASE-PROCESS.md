# Release process

**Default rule: only explicit new version tags publish installers.** Ordinary changes merged into `main` trigger validation but do not publish a release.

**Completed one-time exception for v1.20.0:** The GitHub Actions publisher recognized the PR #184 main-branch squash merge *only* if it changes `docs/releases/v1.20.0.md` and the merge commit contains the exact marker `[publish-v1.20.0]`. The job checks that `package.py` says 1.20.0, builds/validates that source and explicitly creates tag `v1.20.0` at that exact commit before publishing. No other main push or version can use this exception. Its purpose is to publish the specifically requested closed beta without interactive tag access; the regular future release path remains explicit tags.

## Validation and publication

1. Choose the exact code to ship. Update the Debian package version in `package.py`, release notes, and any current-status references.
2. Run PR CI; merge approved code into `main`. CI runs build, C/Python tests, GTK smoke checks, package metadata checks and installed-package validation.
3. For a **closed-beta prerelease intended for device testing**, finish CI and document every untested live flow in [Beta acceptance](BETA-ACCEPTANCE.md); do not call the beta accepted. For any release described as validated, first perform manual device tests of changed UI, networking, and streaming behavior.
4. Add curated notes in `docs/releases/vX.Y.Z.md`. Normally create a **new** `vX.Y.Z` Git tag at the intended `main` commit using local `git tag` and `git push` or authenticated GitHub CLI/API. Never repoint an existing release tag. The specifically named v1.20.0 exception above creates that tag in its isolated, version-checked CI job.
5. `.github/workflows/release.yml` rebuilds the tagged source, verifies that tag/version/package match, and publishes immutable GitHub assets:
   - `OptiPlex-Now_X.Y.Z_amd64.deb`
   - `OptiPlex-Now_amd64.deb`
   - `SHA256SUMS`
6. Verify [GitHub Releases](https://github.com/SteezyMode/OptiplexNow/releases), workflow success, prerelease status, SHA256SUMS and package metadata. This establishes a **published beta**, not accepted behavior; record real installation and onboarding results separately before calling Beta 1 validated.

Tag-triggered publishing uses `--prerelease --latest=false` so the unvalidated beta never replaces the previous release's `Latest` link. A future broadly validated release needs an explicit release-channel review and workflow change. An absent tag means no release, even when code is merged. A matching tag with a failed workflow also does not produce an accepted release. New fixes get a new patch version; do not overwrite past artifacts.

## Safety and rollback

- CI is not a streaming acceptance test. A green workflow does not prove login, Moonlight certificate exchange, host connectivity or user data preservation.
- The release pipeline must not touch the owner's server or deployed containers.
- Reversion is installing an older versioned `.deb` while preserving compatible settings and identity; verify migrations before relying on rollback.
- No workflow may publish from a PR or ordinary `main` push. The one-time exact-marker v1.20.0 release is a deliberate approved exception; remove its inert branch trigger at the next routine release to return to tags only.

See [Contributing](../CONTRIBUTING.md) and [Current status](CURRENT-STATUS.md).
