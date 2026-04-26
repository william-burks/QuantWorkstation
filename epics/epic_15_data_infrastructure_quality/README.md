# Epic 15 — Data Infrastructure Quality & Provenance

**Status:** PLANNED — insert before Epic 12 ML Research
**Inspiration:** Two Sigma "Treating Data as Code" (Effie Baram, Head of Foundational Data Engineering)
**Sequence:** **Epic 15a** (start now) → QWS-1304 (prereq for 15b ingest path) → **Epic 15b** → Epic 12

---

## Phase Split

### Phase A — Data Health (Epic 15a)

Pre-condition for Phase B: provenance tooling is only meaningful over clean, verified data.

Stories: QWS-1501, QWS-1502 (DEFERRED), QWS-1503, QWS-1504, QWS-1505, QWS-1510

### Phase B — Provenance Layer (Epic 15b)

Depends on 15a complete. Records what data a trial consumed, in what environment, and when.

Stories: QWS-1506a, QWS-1506b, QWS-1507, QWS-1508, QWS-1509

---

## Dependency Graph

```
Phase A:
  QWS-1501 ∥ QWS-1504               — no shared files; parallel-safe
  QWS-1503 → QWS-1505               — both modify ibkr_futures.py; sequential
  QWS-1510                           — blocked on QWS-1501 + QWS-1504
  QWS-1502 (DEFERRED)                — post-MVP; crypto not the MVP market

Phase B (requires QWS-1304 CLOSED — ingest path must be stable before _cmd_bundle() extensions):
  QWS-1506a                          — no deps within Phase B; first
  QWS-1506b                          — blocked on QWS-1506a + QWS-1304
  QWS-1507                           — blocked on QWS-1304; sequential before QWS-1508
  QWS-1508                           — blocked on QWS-1507 (shared files)
  QWS-1509                           — blocked on QWS-1506a + QWS-1304
```

---

## Story List

| ID | Title | Phase | Status | Blocked On |
|---|---|---|---|---|
| QWS-1501 | ArcticDB Bar Health Report | 15a | PLANNED | None |
| QWS-1502 | Vendor Schema Contract: Alpaca | 15a | DEFERRED | None |
| QWS-1503 | CONTFUT Revision Detection | 15a | PLANNED | None |
| QWS-1504 | Collector Delivery Monitor | 15a | PLANNED | None |
| QWS-1505 | IBKR Roll Anomaly Alert | 15a | PLANNED | QWS-1503 |
| QWS-1510 | Data Steward Agent | 15a | PLANNED | QWS-1501, QWS-1504 |
| QWS-1506a | DataSnapshot Node + Hash | 15b | PLANNED | None |
| QWS-1506b | CONSUMED_DATA Edge + run_data_lineage Preset | 15b | PLANNED | QWS-1506a, QWS-1304 |
| QWS-1507 | Strategy Input Contract | 15b | PLANNED | QWS-1304 |
| QWS-1508 | Environment Fingerprint on Run | 15b | PLANNED | QWS-1507, QWS-1304 |
| QWS-1509 | Bitemporal as_of on Runs | 15b | PLANNED | QWS-1506a, QWS-1304 |
