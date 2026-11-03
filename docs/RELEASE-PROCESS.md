# Release process

**Default rule: only explicit new version tags publish installers.** Ordinary changes merged into `main` trigger validation but do not publish a release.

**Completed one-time exception for v1.20.0:** The GitHub Actions publisher recognized the PR #184 main-branch squash merge *only* if it changes `docs/releases/v1.20.0.md` and the merge commit contains the exact marker `[publish-v1.20.0]`. The job checks that `package.py` says 1.20.0, builds/validates that source and explicitly creates tag `v1.20.0` at that exact commit before publishing. No other main push or version can use this exception. Its purpose is to publish the specifically requested closed beta without interactive tag access; the regular future release path remains explicit tags.

**Authorized v1.21.15 exception (PR #245):** The owner explicitly requested the tested Music build become the new official main .deb. The publish workflow may create exactly one immutable `v1.21.15` tag from a CI-verified main merge only when `docs/releases/v1.21.15.md` is part of that merge, `package.py` declares `1.21.15`, and the merge commit includes `[publish-v1.21.15]`. An ordinary main push, other version or unmarked merge cannot publish. This matches the exact-version guard used for prior official alpha releases; do not reuse the marker for later versions.

**Authorized v1.21.16 exception (PR #253):** The owner physically tested the dual-index Downloads build on the OptiPlex host and both Linux clients, declared the Downloads UI locked for now, and explicitly requested promotion to the official main `.deb`. Permit one marked `main` release merge containing `docs/releases/v1.21.16.md`, declaring `DEFAULT_VERSION = "1.21.16"` and including `[publish-v1.21.16]` in its merge commit. The workflow rebuilds the package, verifies all tests and creates immutable v1.21.16 assets with the `OptiPlex-Now_amd64.deb` Latest alias. An ordinary commit cannot publish it. The already published v1.21.15 tag remains unchanged.

## Validation and publication

1. Choose the exact code to ship. Update the Debian package version in `package.py`, release notes, and any current-status references.
2. Run PR CI; merge approved code into `main`. CI runs build, C/Python tests, GTK smoke checks, package metadata checks and installed-package validation.
3. For a **closed-beta prerelease intended for device testing**, finish CI and document every untested live flow in [Beta acceptance](BETA-ACCEPTANCE.md); do not call the beta accepted. For any release described as validated, first perform manual device tests of changed UI, networking, and streaming behavior.
4. Add curated notes in `docs/releases/vX.Y.Z.md`. Normally create a **new** `vX.Y.Z` Git tag at the intended `main` commit using local `git tag` and `git push` or authenticated GitHub CLI/API. Never repoint an existing release tag. The specifically named main-merge exceptions above create their tags in isolated, version-checked CI jobs.
5. `.github/workflows/release.yml` rebuilds the tagged source, verifies that tag/version/package match, and publishes immutable GitHub assets:
   - `OptiPlex-Now_X.Y.Z_amd64.deb`
   - `OptiPlex-Now_amd64.deb`
   - `SHA256SUMS`
6. Verify [GitHub Releases](https://github.com/SteezyMode/OptiplexNow/releases), workflow success, prerelease status, SHA256SUMS and package metadata. This establishes a **published beta**, not accepted behavior; record real installation and onboarding results separately before calling Beta 1 validated.

The current publisher uses `--latest` for explicitly approved Current Alpha releases; normal unmarked main pushes do not publish. A future broader release needs a separate release-channel review. An absent tag means no normal release, even when code is merged, except the specific one-time marked main-merge exceptions above. A tag or merge with a failed workflow does not produce an accepted release. New fixes get a new patch version; do not overwrite past artifacts.

## Safety and rollback

- CI is not a streaming acceptance test. A green workflow does not prove login, Moonlight certificate exchange, host connectivity or user data preservation.
- The release pipeline must not touch the owner's server or deployed containers.
- Reversion is installing an older versioned `.deb` while preserving compatible settings and identity; verify migrations before relying on rollback.
- No workflow may publish from a PR or ordinary `main` push. A named, approved, exact-marker main merge is an exception only for its stated immutable version; return to tag-only triggering after v1.21.16.

See [Contributing](../CONTRIBUTING.md) and [Current status](CURRENT-STATUS.md).
