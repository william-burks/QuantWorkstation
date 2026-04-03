# Story 0 — Infra Scaffold and Docker

## Status
ready

## Summary
Create the minimum infrastructure scaffold for Graph V1 before parser/CLI/store implementation starts.

## Problem
Without a stable Neo4j + config baseline, model/parser/CLI work gets blocked by environment and wiring issues.

## Goal
Stand up local Neo4j compose config and repository config wiring so later stories can focus on Python/Cypher behavior.

## Inputs
- `docs/graph_v1_contract.md`
- Existing settings pattern in `data/config.py`
- Existing environment template `env.example`
- Epic 1 objective and ordering

## Deliverable
- `docker-compose.neo4j.yml`
- Graph-related settings in `data/config.py`
- Graph-related env vars in `env.example`
- Optional quickstart notes in `qws_graph/README.md` or `docs/graph_v1_contract.md` reference section

## In Scope
- Local Neo4j service definition for dev usage
- Sensible defaults for URI/user/password/database/timeout
- Optional feature flag for graph enable/disable
- Connection timeout default aligned to contract (3 seconds)

## Out of Scope
- Cloud deployment
- Multi-node Neo4j setup
- MCP implementation
- Query/store/parser logic

## Repo Touchpoints
- `docker-compose.neo4j.yml`
- `data/config.py`
- `env.example`
- `qws_graph/epics/epic_1_ingestion_and_index/README.md`

## Implementation Notes
- Keep config additive; do not break existing runtime paths.
- Preserve existing execution behavior when Neo4j is unavailable.
- Use local-first defaults; do not assume external infra.

## Acceptance Criteria
- [ ] `docker-compose.neo4j.yml` exists and defines a local Neo4j service.
- [ ] `data/config.py` exposes graph settings via existing settings pattern.
- [ ] `env.example` includes graph variables with safe defaults/comments.
- [ ] Graph-disabled mode can run without Neo4j dependency.
- [ ] Timeout value is configurable and defaults to 3 seconds.

## Validation
- Start Neo4j from compose and verify service is reachable.
- Load settings with and without graph env vars.
- Confirm no regressions in existing non-graph scripts due to added config.

## Definition of Done
- [ ] Infra files merged and documented.
- [ ] Settings load path tested.
- [ ] Epic 1 story ordering updated to include Story 0 first.

## Open Questions
- None.

## Notes
This story intentionally front-loads plumbing so Story 3 (`qw record`) and Story 4 (store layer) can remain focused on core logic.

