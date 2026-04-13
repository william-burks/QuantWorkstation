---
name: pre-existing test failures in tests/unit/
description: ibkr_futures_collector tests now pass — baseline as of Epic 9HF is 733 passed, 0 failed
type: project
---

As of 2026-04-13 (Epic 10 QA), `make test-all` runs clean: 647 qws_graph unit + 295 top-level = 942 passed, 0 failed.

Epic 10 added collectors (COT, FRED, EIA, BH, Google Trends, BDTI, EcoCal), store_series, validation, strategy_class, and Prefect flows — test count grew from 733 to 942.

**Why:** Tracking so future QA baselines know the expected clean state.

**How to apply:** If any tests fail at baseline, they are NEW regressions — investigate. Do not assume pre-existing.
