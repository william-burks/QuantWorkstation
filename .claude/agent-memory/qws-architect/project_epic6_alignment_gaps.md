---
name: Epic 6 alignment gaps (2026-04-10 re-evaluation)
description: QWS-0601 now aligned with BACKLOG after rewrite; QWS-0604 has status casing issue and orphaned check_redundancy upgrade
type: project
---

QWS-0601 alignment gap RESOLVED. Story now delivers SUGGESTED, TESTED_AS, BRANCHED_FROM edges + all 4 MCP tools matching BACKLOG_ALIGNMENT. Previous HAS_EVIDENCE design replaced.

**Open issues (QWS-0604):**
1. Status field says "draft" — must be "DRAFT" per casing rule.
2. check_redundancy semantic upgrade is orphaned: 0601 ships string-match version, 0604 creates SEMANTICALLY_RELATED edges, but no story owns "check_redundancy reads those edges." Needs to be folded into 0604 or a new QWS-0605.
3. ResearchTarget conditional coupling (QWS-0408) should be removed — unnecessary complexity.

**Why:** These must be resolved before 0604 can promote to READY.

**How to apply:** When reviewing 0604 next, verify these three items are addressed. Do not approve for implementation until all resolved.
