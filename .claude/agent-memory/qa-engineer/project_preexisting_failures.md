---
name: pre-existing test failures in tests/unit/
description: ibkr_futures_collector tests now pass — baseline as of Epic 9HF is 733 passed, 0 failed
type: project
---

As of 2026-04-13 (Epic 9HF QA), `make test-all` runs clean: 576 qws_graph unit + 157 top-level = 733 passed, 0 failed.

Previous 9 ibkr_futures_collector failures are resolved (likely fixed in a prior epic; confirmed gone at Epic 9HF baseline).

**Why:** Tracking so future QA baselines know the expected clean state.

**How to apply:** If any tests fail at baseline, they are NEW regressions — investigate. Do not assume pre-existing.
