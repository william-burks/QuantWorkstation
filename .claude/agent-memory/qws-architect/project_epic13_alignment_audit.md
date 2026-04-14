---
name: Epic 13 alignment audit
description: Epic 13 Agent Design full audit — 2026-04-13 re-validated; ALL ALIGNED; 5 minor/info findings; zero must-fix
type: project
---

Epic 13 re-validated 2026-04-13 against current doc state (post bce9929). ALL ALIGNED.

**5 findings (zero must-fix):**
- F1 (minor): `queued` property missing from BACKLOG_ALIGNMENT NYI Properties table — add during QWS-1301
- F2 (minor): `queued_hypotheses` missing from BACKLOG_ALIGNMENT NYI MCP Tools table — add during QWS-1301
- F3 (info): QWS-1302 AC implies whitelist Bash scoping but guard is blacklist — resolve during implementation
- F4 (info): QWS-1303 trial_base.py extraction is same-story prereq — monitor scope creep
- F5 (info): QWS-1304 "manual session run" blocker is soft, no formal criteria — Will decides

**Why:** All findings are implementation-time resolutions, not design misalignment.

**How to apply:** Sequence 1301->1302->1303->1304 is only valid order. No parallelization. Schema: one bool (`queued`), one preset (`queued_hypotheses`). No new nodes/edges. All touchpoint files verified to exist.
