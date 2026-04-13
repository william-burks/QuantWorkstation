# Epic 9HF — Bugs & Hotfixes

## Objective
Fix silent data integrity bugs discovered during Epic 9 research sessions — provenance chain
breaks, phantom IDs, CLI ordering bugs. All stories are independent and can be implemented
in parallel.

## Why it exists
Epic 9 first research session (CL liquidity sweep walk-forward) surfaced gaps in the
provenance chain: hypothesis→strategy links not auto-wired on bundle ingest, phantom
champion IDs printed before Neo4j write completes. These are blocking issues for the
research workflow — fix before next research session.

## Stories

| ID | Name | File | Status | Blocked On |
|---|---|---|---|---|
| QWS-HF-001 | Bundle hypothesis autolink | `QWS-HF-001_bundle_hypothesis_autolink.md` | READY | — |
| QWS-0904 | Phantom champion ID fix | `QWS-0904_phantom_champion_id_fix.md` | READY | — |
