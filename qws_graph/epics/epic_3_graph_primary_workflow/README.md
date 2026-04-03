# Epic 3 — Graph Primary Workflow

## Objective
Move decision-state authority from files to graph in controlled steps after ingestion/index reliability is proven.

## Why it exists
Graph adoption only delivers full value when promotion/OOS readiness and lineage-driven decisions are graph-native.

## Scope
- Decision-state node/edge model
- Promotion and OOS state transitions
- Graph-to-file export for audit and continuity
- Cutover guardrails and rollback procedures

## Stories in execution order
1. `story_1_decision_state_model.md`
2. `story_2_promotion_and_oos_state_transitions.md`
3. `story_3_graph_to_file_exports.md`
4. `story_4_cutover_guardrails_and_rollback.md`

## Dependencies
- Epic 1 complete and stable
- Epic 2 read/query contracts complete
- Team agreement on cutover criteria

## Exit criteria
- Decision-state transitions are graph-native and test-backed
- File artifacts can be generated from graph state
- Rollback path to file-led operation is documented and tested

