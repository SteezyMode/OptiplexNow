## Problem and observed evidence
<!-- Real device / Wolf version / exact failure, or label as offline-only hypothesis. -->

## Change, owner and touched files
<!-- Modules, API contracts and any current data migration. -->

## Decision and rejected shortcuts
<!-- Upstream references, mistaken previous assumptions, safety rationale. -->

## Tests performed
- [ ] Python/native unit tests (name commands and results)
- [ ] GitHub build/package CI (run link, passing/failing)
- [ ] Sanitizer diagnostics (run link, passing/failing)
- [ ] Physical acceptance (exact host/client build and result, or explicitly **not tested**)

## Security, privileges, data preservation
<!-- Device credentials, roles, Wolf direct-API bypass, concurrent sessions,
     exposed secrets, affected mounts; clarify untouched production services. -->

## Rollback and failure behavior
<!-- Bad upgrade, partial state, interrupted POST, restore steps; never assume success. -->

## Next-team handoff
<!-- Exact next executable action, prerequisites, blocked issues, expected evidence. -->

- [ ] Updated `docs/ENGINEERING-TRAIL.md` with dated evidence, failed attempts and
      why the next team should not repeat them.
- [ ] Updated `docs/CURRENT-STATUS.md` only for actual implementation/evidence changes.
- [ ] Tracked outstanding acceptance gates in the owning GitHub issue.
- [ ] Did not describe mocks/CI/source code as a verified deployment.
