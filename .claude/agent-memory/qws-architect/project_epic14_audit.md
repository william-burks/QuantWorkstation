---
name: Epic 14 alignment audit
description: Findings from Epic 14 (Research Pipeline Hardening) architecture validation — 6 stories, all prior findings resolved, 1 new advisory
type: project
---

Epic 14 audit — Round 2 completed 2026-04-15. 6 stories validated against PROVENANCE_ENGINE, MANIFESTO, BACKLOG_ALIGNMENT.

**Prior findings (all RESOLVED):**
1. `degrade_reason` now in data_dictionary.yaml (line 699), PROVENANCE_ENGINE Not Yet Implemented, and story QWS-1405.
2. QWS-1405 traversal corrected to `Champion -> PIVOTED_FROM -> Run <- HAS_RUN <- Strategy <- TESTED_AS <- Hypothesis`.
3. Epic 14 fully present in BACKLOG_ALIGNMENT.md (Epic Status + Story->Capability Map + Not Yet Implemented).
4. QWS-1402 dual write path clarified: evaluator computes, bundle.json carries values, ingest reads from bundle.json (no recompute).

**New finding:**
- **ADVISORY: QWS-1404 illustrative Cypher doesn't match actual code.** Story shows `(h)-[:TESTED_AS]->(r1:Run)` but real buggy query (cypher.py:398) uses PRODUCED_CHAMPION/ABORTED/SEMANTICALLY_RELATED. No TESTED_AS in actual query. Implementer must read actual Cypher, not story illustrations.

**Overall verdict: ALIGNED.** All 6 stories advance the research loop. Sequence optimal. No schema drift. No circular deps.

**Why:** Tracking audit state prevents re-raising resolved findings and ensures new findings get addressed.
**How to apply:** QWS-1404 advisory is low-severity — implementer guidance only. Epic 14 is implementation-ready.
