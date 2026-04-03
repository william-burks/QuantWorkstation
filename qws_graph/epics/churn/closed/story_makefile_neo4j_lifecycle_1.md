# Story: Makefile Local Neo4j Lifecycle

## Status
closed

## Problem
Local Neo4j lifecycle commands are currently run with direct `docker compose` invocations, which is easy to mistype and inconsistent across contributors.

## Goal
Provide a simple, repo-native `Makefile` workflow for managing the local Neo4j Docker service lifecycle.

## Deliverable
A root-level `Makefile` with clear Neo4j lifecycle targets and lightweight docs update that points users to those targets.

## Scope
- Add Make targets for local Neo4j lifecycle:
  - start/up
  - stop/down
  - restart
  - logs
  - status
- Keep commands bound to existing `docker-compose.neo4j.yml`.
- Keep behavior local-only and non-destructive by default.

## Out-of-Scope
- Any application/graph ingestion logic.
- Changes to Neo4j schema, credentials, or graph contract.
- CI/CD or deployment workflow expansion.

## Repo Touchpoints
- `Makefile` (new)
- `epics/epic_1_ingestion_and_index/README.md` (quickstart command updates)
- `epics/churn/closed/story_makefile_neo4j_lifecycle_1.md` (this story)

## Acceptance Criteria
1. Running `make neo4j-up` starts the local Neo4j service defined in `docker-compose.neo4j.yml`.
2. Running `make neo4j-down` stops and removes the service/container from that compose project.
3. Running `make neo4j-restart` performs down then up using the same compose file.
4. Running `make neo4j-logs` shows service logs.
5. Running `make neo4j-status` shows compose service/container status.
6. Documentation in Epic 1 quickstart references the new Make workflow.

## Validation
- Execute:
  - `make neo4j-status`
  - `make neo4j-up`
  - `make neo4j-status`
  - `make neo4j-logs`
  - `make neo4j-down`
- Confirm commands invoke `docker compose -f docker-compose.neo4j.yml ...`.

## Notes
- If host port `7474` is occupied, `make neo4j-up` will fail until the conflict is resolved or ports are remapped in compose.
