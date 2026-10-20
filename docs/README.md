# NOW documentation — how to find reliable information

There is **one released application (NOW), one separate Studio application, and one coordinating Suite repository**. This directory contains technical details, proposals, and historical operational notes. It is not an independent status tracker.

## Start here

| Want to understand... | Read |
| --- | --- |
| What NOW does, how to contribute, and the source map | [CONTRIBUTING](../CONTRIBUTING.md) |
| Released vs current code vs pending work | [CURRENT-STATUS](CURRENT-STATUS.md) |
| Current application boundaries and data formats | [Application design](application-design.md) |
| Package build, tag-only publishing, rollback gates | [Release process](RELEASE-PROCESS.md) |
| Installation with an **existing** server | [Server setup/reference-host notes](server-setup.md) |
| Wolf update/repair procedures, explicit operator actions | [Wolf maintenance](wolf-maintenance.md) |

- [MoonlightWeb maintenance](moonlightweb-maintenance.md): supported 1.14.0 manual updater, prerequisites and limits; production update not yet acceptance-tested.

## Planned, not shipped

- [NOW server manager and upstream-first Wolf strategy](UPSTREAM-FIRST-WOLF-INTEGRATION.md): installation/provisioning concept and supported ownership boundary.
- [Turnkey server onboarding + optional NOW account/Tailscale discovery](SERVER-ONBOARDING-AND-TAILSCALE.md): proposed fresh-server and new-client login flow; website registry is optional, not a shipped account service.
- [Persistent multi-user desktop feasibility](MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md): streaming authorization and profile/session acceptance requirements.

These are proposals only. None is a released, tested fresh-server wizard, hosted NOW account service, or commercial multi-tenant security capability.

## Historical or environment-specific information

- [Operator inventory (2026-10-16)](operations-handoff.md): useful observations, **not** current live server truth.
- [Former next-session note](next-session.md): archived session directions and pointer to the current sources.
- [Earlier browser synth proposal](archive/2026-10-16-studio-synth-design.md): former idea also called Studio, **not** the currently released native OptiPlex Studio product.
- [Archived old session handoff](archive/2026-10-19-next-session.md).
- [Remote tmux guidance](remote-development-tmux.md): developer workflow, not a product runtime guarantee.

When source and documents conflict, verify implementation/tests in the owning app, then correct its CURRENT-STATUS and README. Suite only points to the authoritative owner; do not copy state lists back and forth.
