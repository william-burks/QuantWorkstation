---
name: Epic 6 alignment gaps — ALL RESOLVED
description: All 3 hard-fails and 1 medium gap from 2026-04-10 audits confirmed fixed as of third-round patch validation
type: project
---

**All issues resolved as of 2026-04-10 third-round validation:**
- QWS-0601: FormerChampion forward-dep fixed — check_redundancy defers FormerChampion to QWS-0801.
- QWS-0603: `qw promote` references removed — replaced with `qw record --bundle` auto-promote path.
- QWS-0603: "Out of Scope: Graph schema changes" contradiction removed.
- QWS-0603: IS/OOS drift flag (`is_oos_drift`) added to In Scope (L82), AC (L119), and DoD (L126). Medium gap closed.

**Sprint order recommendation:** 0601 first (core mission), 0602+0603 parallel, 0604 last (blocked on 0601).

**Doc drift (low, cosmetic):** BACKLOG L24 (Epic 5 "PLANNED") should say COMPLETE.

**Why:** Tracked to prevent implementers building to wrong spec.

**How to apply:** Epic 6 stories are implementation-ready. No architectural blockers remain.
