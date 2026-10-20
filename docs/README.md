# Documentation map

Read in this order when joining development or starting a new review.

| File | Authority |
| --- | --- |
| [Product direction](PRODUCT.md) | Vision, scope, phased requirements and exclusions |
| [Current status](CURRENT-STATUS.md) | What code, CI and device observations support today |
| [Beta acceptance](BETA-ACCEPTANCE.md) | Required end-to-end tester evidence |
| [Architecture](application-design.md) | Code ownership, protocols, data compatibility and safe boundaries |
| [Contributing](../CONTRIBUTING.md) | Build, test, PR discipline and code map |
| [Release process](RELEASE-PROCESS.md) | Immutable tags, artifact verification and rollback |
| [Wolf pairing contract](WOLF-PAIRING-HOST-CONTRACT.md) | Actual host API, client bridge, privilege model and unverified checks |
| [Wolf integration and fork policy](UPSTREAM-FIRST-WOLF-INTEGRATION.md) | Future host manager design and evidence gate for a fork |

## Specialized references

- [Current test host, services and backups](server-setup.md): environment-specific observations. Not a universal setup recipe.
- [Multi-user desktop feasibility](MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md): technical research, not a released feature.
- [Wolf driver maintenance](wolf-maintenance.md): opt-in existing-host procedure.
- [MoonlightWeb maintenance](moonlightweb-maintenance.md): opt-in update/rollback constraints for an existing deployment.
- [Remote development via tmux](remote-development-tmux.md): maintainer workflow, not a runtime dependency.

## Historical records

`archive/` retains dated proposals and old session notes for traceability. [October 16 operations inventory](archive/2026-10-16-operations-handoff.md) is historical, not authoritative current deployment status. Do not use old version claims, IPs, container identifiers or release instructions without checking the live machine and current code. An [old next-session handoff](archive/2026-10-19-next-session.md) remains archived.

**Rule:** Implementation is established by code and tests; release publication by GitHub Releases; working user flows by device tests. Plans belong in PRODUCT or tracked issues. Do not create another current-status or personal handoff document.
