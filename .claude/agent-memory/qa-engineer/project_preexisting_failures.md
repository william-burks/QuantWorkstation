---
name: pre-existing test failures in tests/unit/
description: 9 ibkr_futures_collector tests fail in tests/unit/ — pre-existing, not epic-6 caused
type: project
---

As of 2026-04-11, `tests/unit/test_ibkr_futures_collector.py` has 9 failing tests. These are pre-existing and not caused by Epic 6 stories. Confirmed still present after Epic 6 QA complete (148 passing, same 9 failing, no regressions).

**Why:** ibkr_futures_collector tests likely need IB Gateway or have a module-level import issue. Not related to qws_graph work.

**How to apply:** When running baseline for QA, note these as pre-existing. Do not investigate unless they appear in qws_graph/ scope.
