# Release process (NOW)

Status: proposed workflow change in `cleanup/phase-1-release-safety`. This document governs future releases after that PR is reviewed and merged. It does not create a release.

## Normal development

- Pull requests and pushes to `main` run `Validate OptiPlex NOW`.
- CI compiles, runs unit tests and inspects the .deb; it does **not** publish a GitHub Release, change a host, or install an application.
- Treat passing tests as necessary, not proof of working Moonlight/Wolf playback or an on-device GTK tray.

## Publishing a new version

1. Review the changes and independently check the intended release scope.
2. Bump the package version in `package.py` and update current-version documentation. Keep the package metadata and filename consistent.
3. Merge the validated source to `main`. Do the relevant **manual device integration checks** (GTK launch, existing settings, Moonlight/Steam and Wolf desktop shortcut, reconnect and backout).
4. Create and push an annotated **new** `vX.Y.Z` tag pointing to the exact approved commit, for example `git tag -a v1.14.0 -m 'NOW 1.14.0'` followed by `git push origin v1.14.0`. Do not reuse or move published tags.
5. The tag-only workflow rebuilds and tests that commit, verifies the package version exactly matches the tag and creates new GitHub release assets plus `SHA256SUMS`. Existing releases are never overwritten.
6. Confirm GitHub Actions success, the release asset filenames and checksums, and the install result on one representative supported Linux desktop.

If the tag mismatches the package, publishing **must fail**. Fix source on a new commit and use a new approved tag; do not quietly replace a released binary.

## Non-goals

This phase does not change installation prerequisites, package format, application logic, Wolf configuration, or the current v1.13.0 release. The future turnkey server installer is tracked separately.
