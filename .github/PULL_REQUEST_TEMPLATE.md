## Problem / user-visible outcome
What exact NOW behavior or acceptance criterion is being fixed? Link the issue.

## Scope
What changed in client UI, config, Wolf/Moonlight integration or server-side helpers? What explicitly did not change?

## Verification
- [ ] `make check-process check-presets`
- [ ] `python3 -m unittest discover -s tests -v`
- [ ] `make package`
- [ ] Relevant live manual checks (or explicitly **not run**)

Include results; build success is not evidence of actual streaming or tray function.

## Compatibility and safety
- [ ] Existing settings, exports/backups, SSH/Moonlight pairing preserved
- [ ] No unnecessary changes to active Wolf, Tailscale, media or VPN services
- [ ] Any privileged server operations reviewed and gated
- [ ] Rollback and outstanding verification documented

## Reviewer acceptance
What should somebody independently observe to approve this change?
