# QWS Knowledge Graph — Repository Alignment Review Rebuttal

## Repository Alignment Assessment

The plan is directionally compatible with the repository’s goals around structured research, validation, and preserving reasoning, but it is **not an incremental fit as written**.

Why:

- The current repo is a **Python trading research/execution workbench** with:
  - file-based outputs (`results/*.csv`, `research/results/champions/*.md`)
  - direct script execution
  - manual/markdown-driven research phases
  - selective Pydantic validation
- The proposed plan assumes the repo is ready to become a **Neo4j/MCP/CLI-centered knowledge graph platform**.
- That is a **major architectural expansion**, not a small extension of current patterns.

Bottom line:

- The problem framing is plausible for this repo.
- The implementation path in the plan conflicts with the current workflow and source-of-truth artifacts.
- This should be treated as a **layer on top of the existing research OS**, not a replacement for it.

## Confirmed Matches

Parts of the plan that are explicitly supported by the repo/docs:

- **Python 3.11+ is correct**
  - Confirmed in `pyproject.toml:8`.
- **Pydantic is already an accepted pattern**
  - `data/schemas/*.py` use `BaseModel`
  - `data/config.py:1-40` uses `pydantic-settings`
  - `research/candidate_validator.py:20-202` already validates structured research candidate JSON.
- **Research workflow is already formalized**
  - `docs/IS_RESEARCH_SOP.md` defines a five-phase research cycle.
  - `RESEARCH_CHECKLIST.md`, `README_ES_NQ_RESEARCH.md`, `research/es_nq_bear_sweep_tracker.md`, `PHASE2_*`, `PHASE3_*` show a strong process/documentation culture.
- **CLI/script-based workflow is real**
  - `strategies/bear_es_sweep_1h_baseline.py` and `strategies/bear_nq_sweep_1h_baseline.py` use `argparse`.
  - `research/run_es_nq_baseline.sh` and `research/run_es_phase2.sh` orchestrate runs with zsh scripts.
- **Structured experiment outputs already exist**
  - CSV results in `results/`
  - champion markdown in `research/results/champions/`
  - templates in `research/*_champion_template.md`
- **Local-first workflow is already the norm**
  - Local parquet/arctic data, local scripts, local docs.
- **Validation before promotion is already a repo concept**
  - `research/candidate_validator.py` is the closest existing analogue to “strict validation before accepting research artifacts.”
- **There is an existing place for research harness logic**
  - `research/experiments/sweep.py:40-124`
  - `research/runner.py:1-7` exists, though it is minimal/demo-like rather than the primary futures workflow.

## Detected Conflicts

Parts of the plan that conflict with current repo patterns or would create debt if implemented literally.

### Strategic conflicts

- **The repo is not currently a knowledge-graph system**
  - No Neo4j dependency in `pyproject.toml`
  - No Docker Compose for Neo4j
  - No Cypher client code
  - No MCP server/client implementation in the repo
  - No graph persistence layer
- **The current research source of truth is file-based, not graph-based**
  - Current process centers on:
    - strategy scripts
    - CSV result files
    - markdown trackers/templates/champion docs
  - The plan implicitly wants the graph to become the new system of record.
- **`research/runner.py` is not the primary execution surface for the current futures workflow**
  - `research/runner.py` is a tiny crypto/vectorbt example.
  - Actual ES/NQ workflow runs through:
    - `strategies/bear_es_sweep_1h_baseline.py`
    - `strategies/bear_nq_sweep_1h_baseline.py`
    - `research/run_es_nq_baseline.sh`
    - `research/run_es_phase2.sh`
- **The plan’s “Alpha” definition does not match current promotion gates**
  - Current repo/SOP gates emphasize:
    - sample size
    - win rate vs breakeven
    - Sharpe
    - profit factor
    - max drawdown
    - OOS pass counts
  - The plan introduces new top-level criteria:
    - exposure-normalized returns
    - `|beta| < 0.1`
    - `rho < 0.3`
  - These are not current repo requirements.
- **The benchmark choice conflicts with the active research domain**
  - Plan proposes a `70% BTC / 30% ETH` basket.
  - Current active research in attached docs/scripts is **ES/NQ futures**.
  - A crypto basket is not a justified default benchmark for ES/NQ futures research.
- **The plan expands into live infrastructure beyond current repo evidence**
  - `LiveInstance` mentions **IBKR/Binance**.
  - Repo supports Alpaca + IBKR in dependencies/docs.
  - Binance is not confirmed in current code/deps.
- **The plan claims “No assumptions remaining”**
  - This is false based on repo evidence.

### Implementation conflicts

- **No `qw` CLI exists**
  - No console entry point in `pyproject.toml`
  - No package/module implementing `push-start`, `push-complete`, or `query`
- **No `schema.md` or `pydantic_models.py` exists as proposed canonical files**
  - Current schema/validation is distributed across:
    - `data/schemas/`
    - `research/candidate_validator.py`
    - docs/templates/checklists
- **No VS Code extension/HUD exists**
  - This is a separate product surface, not a low-risk repo change.
- **No current FastAPI route layer is active for this use case**
  - `fastapi` is in dependencies and `api/` exists, but no active `FastAPI`/`APIRouter` usage was surfaced in the repo scan.
  - The plan should not assume an existing app layer to attach this to.
- **Current scripts are intentionally explicit and manual**
  - The repo favors visible, direct commands and markdown checkpoints.
  - A large abstraction layer risks hiding the research process that is currently documented very explicitly.
- **Current outputs are summaries, not full graph-ready experiment objects**
  - Example: `results/es_bear_sweep_1h_grid_nypre_v1.csv`
  - Example: `research/results/champions/es_bear_sweep_1h_v1.md`
  - The plan assumes storage of richer node/edge structures than current scripts emit.

## Recommended Amendments

### Strategic

- **Reframe the graph as an adjunct metadata layer, not the new source of truth**
  - Preserve CSV/Markdown outputs and current research scripts.
  - Add graph capture after the fact.
- **Anchor the implementation to the existing 5-phase SOP**
  - The graph should model:
    - research references
    - experiment runs
    - champion freezes
    - OOS results
  - It should not redefine the research lifecycle.
- **Treat ES/NQ research as the first-class use case**
  - Do not default to crypto benchmarks for futures strategies.
- **Delay live-instance modeling**
  - Start with research artifacts only.
  - Live trading drift tracking is a later phase.
- **Delay MCP/VS Code HUD/tunneling**
  - These are not necessary to prove value.
  - They add scope without repo evidence of immediate need.
- **Do not replace manual research checkpoints**
  - The tracker, checklist, champion templates, and result CSVs are core workflow artifacts today.

### Implementation

- **Use existing validation patterns instead of inventing a new universal validation layer**
  - Extend the style of `research/candidate_validator.py` rather than creating an abstract `pydantic_models.py` catch-all immediately.
- **Hook commit/export logic into actual run surfaces, not just `research/runner.py`**
  - Primary hook points:
    - `research/experiments/sweep.py:40-124` → `sweep`
    - `strategies/bear_es_sweep_1h_baseline.py:543` → `run_backtest`
    - `strategies/bear_es_sweep_1h_baseline.py:830` → `run_grid_search`
    - `strategies/bear_es_sweep_1h_baseline.py:898-928` → CLI parse/main path
    - `strategies/bear_nq_sweep_1h_baseline.py:509` → `run_backtest`
    - `strategies/bear_nq_sweep_1h_baseline.py:798-819` → CLI parse/main path
    - `research/candidate_validator.py:175-202` → validation entry point for structured ingestion
- **Reuse `data/config.py` patterns for configuration**
  - If graph config is added, extend settings rather than creating a parallel config style.
- **Keep entrypoints consistent with current repo**
  - Current style is:
    - direct Python scripts
    - zsh wrappers
    - simple argparse CLIs
  - A new `qw` CLI should be optional and introduced only after the data model is proven.
- **Make graph commits optional**
  - `--commit-graph` or equivalent should never block baseline research unless explicitly enabled.
- **Prefer file-backed exports first**
  - A JSON sidecar export from existing results is a safer first step than immediate Neo4j dependency.
- **Document new schema alongside existing docs**
  - If a `schema.md` is introduced, it should supplement existing SOP/checklist/champion templates, not replace them.

## Preserve As-Is

Current workflow elements that should not be broken by this plan:

- The **five-phase IS research process** in `docs/IS_RESEARCH_SOP.md`
- Existing **manual baseline → isolation → grid → champion → OOS** progression
- Existing **script entrypoints**:
  - `strategies/bear_es_sweep_1h_baseline.py`
  - `strategies/bear_nq_sweep_1h_baseline.py`
- Existing **shell wrappers**:
  - `research/run_es_nq_baseline.sh`
  - `research/run_es_phase2.sh`
- Existing **artifact locations/patterns**:
  - `results/*.csv`
  - `research/results/champions/*.md`
  - tracker/checklist docs
- Existing **naming style**
  - snake_case modules
  - explicit script names tied to strategy and timeframe
- Existing **config pattern**
  - `data/config.py` + `.env`
- Existing **promotion gates**
  - sample size / Sharpe / PF / drawdown / OOS rules should remain unless explicitly re-decided
- Existing **manual interpretability**
  - reports and docs are meant to be readable without infrastructure

## Affected Files / Modules / Workflows

Most likely impact areas if the plan is implemented in repo-aligned form.

### Modify

- `pyproject.toml`
  - only if adding optional graph dependencies / CLI entry points
- `data/config.py`
  - if adding graph connection/config settings
- `research/experiments/sweep.py`
  - optional export/commit hook after sweep completion
- `research/runner.py`
  - only if kept as example/demo path; not primary hook
- `strategies/bear_es_sweep_1h_baseline.py`
  - optional graph/export commit in baseline/grid flow
- `strategies/bear_nq_sweep_1h_baseline.py`
  - same as above
- `README.md`
  - architecture/runbook updates
- `docs/IS_RESEARCH_SOP.md`
  - if graph capture becomes part of the documented process
- `RESEARCH_CHECKLIST.md`
  - if graph commit/export becomes an explicit step
- `README_ES_NQ_RESEARCH.md`
  - only if ES/NQ workflow changes materially

### Create

- Likely better under `research/` than as a repo-wide abstraction from day one:
  - `research/graph/models.py`
  - `research/graph/export.py`
  - `research/graph/store.py`
  - `research/graph/cli.py` or `research/graph/__main__.py`
- Optional docs:
  - `docs/schema.md`
  - `docs/graph_workflow.md`
- Optional infrastructure later:
  - `docker-compose.neo4j.yml`

### Workflows affected

- Research artifact creation
- Experiment result persistence
- Champion freeze documentation
- OOS preparation and archive trail
- Possibly candidate JSON handoff validation

## Proposed Execution Order

A repo-aligned implementation sequence:

1. **Freeze vocabulary and scope**
   - Define exactly which existing artifacts become graph entities first:
     - references
     - experiments
     - champions
     - OOS runs
2. **Adopt current workflow as canonical**
   - Write down that CSV/Markdown remain source-of-truth outputs in v1.
3. **Define minimal Pydantic graph/export models**
   - Start from existing repo concepts, not abstract platform concepts.
4. **Add file-based structured export from current research runs**
   - Example: JSON sidecar for experiment metadata next to current CSV outputs.
5. **Hook export into actual strategy scripts**
   - Add optional export/commit in ES/NQ baseline/grid flows.
6. **Add read/query utilities**
   - Only after data is being emitted consistently.
7. **Introduce Neo4j as an optional backend**
   - After the data model is stable.
8. **Only then evaluate**
   - MCP integration
   - browser push flow
   - editor HUD / CodeLens
   - live-instance drift graphing

## Smallest Viable Next Step

The best low-risk starting task today:

- **Define a minimal repo-aligned experiment artifact schema and emit it from one existing strategy script as an optional sidecar JSON, without changing current CSV/Markdown outputs.**

Why this is the right first move:

- It tests whether the graph model maps cleanly to current research artifacts.
- It avoids premature Neo4j/MCP/extension work.
- It uses the repo’s existing strengths:
  - Pydantic validation
  - direct scripts
  - explicit outputs
- It reveals whether the proposed node types are grounded in actual experiment data.

## Risks / Unknowns / Assumptions

### Confirmed from Repo

- Python baseline is `>=3.11`.
- Pydantic is already accepted and used.
- Current active workflow is script + CSV + markdown based.
- ES/NQ futures research is a real current workflow.
- `research/runner.py` is not the operational center of the attached ES/NQ workflow.
- Current docs define a formal five-phase research SOP.
- Current repo already values explicit process and validation.

### Assumed by the Plan, but not confirmed from Repo

- Neo4j is the correct first storage layer.
- MCP integration is required now.
- A repo-wide `qw` CLI should become the primary interface.
- `runner.py` and `sweep.py` are the sole or primary backtest entry points.
- `BTC/ETH` benchmark is the right market-independence reference for ES/NQ.
- VS Code CodeLens/HUD is needed now.
- Secure tunneling/browser access is part of the current workflow.
- Live bot graphing should be included in the initial scope.
- All node types listed are needed before a first useful implementation exists.

### Unknowns that block a clean final implementation artifact

- Whether the graph is intended to be:
  - canonical storage
  - mirror/archive
  - query index over existing artifacts
- Whether current markdown templates/checklists remain canonical after graph adoption
- Whether experiment artifacts should store:
  - summary stats only
  - full trade logs
  - equity curves
  - parameter grids
- Whether “Alpha” criteria should replace or supplement current SOP gates
- Whether cross-asset beta/correlation is a real requirement for futures research in this repo
- Whether the user actually wants a CLI-first product, or just structured persistence around the current workflow

### Missing acceptance criteria

A task is not “done” unless the plan specifies:

- which current scripts must emit graph-ready artifacts
- whether current CSV/Markdown outputs remain unchanged
- what minimum node set must be stored in v1
- what exact query/use case justifies Neo4j in v1
- how success is measured:
  - one strategy ingested?
  - one experiment searchable?
  - champion traceability?
  - full end-to-end browser push?
- what failure mode is acceptable if graph commit fails during research execution

## Final Verdict

**3. Accept with Major Amendments**

The high-level intent is usable, but the implementation path is not aligned enough with the current repository to proceed as written.

The repo-aware version should:

- preserve the existing research OS,
- treat the graph as a thin metadata layer first,
- hook into the actual ES/NQ strategy scripts and existing artifacts,
- defer Neo4j/MCP/HUD/live-instance scope until the minimal data model proves value.

# Updated Copilot Position On Graph Transition

## 1. What’s Now Fixed As Strategic Direction

The following are now treated as approved architectural direction, not open debate:

- The repository is moving toward a **Knowledge Graph–centric architecture**.
- The migration pattern is explicitly **Sidecar → Index → Primary**.
- `CSV` and `Markdown` remain important, but as **raw/log/export artifacts**, not the long-term decision system.
- The graph is intended to become the **primary source of truth for relationships, pivots, benchmark logic, cross-strategy analysis, and promotion decisions**.
- A unified **`qw` CLI** is a desired standardization direction, even if the repo currently uses:
  - `zsh` wrappers such as `research/run_es_nq_baseline.sh` and `research/run_es_phase2.sh`
  - `argparse` entrypoints in `strategies/bear_es_sweep_1h_baseline.py` and `strategies/bear_nq_sweep_1h_baseline.py`
- Running **Dockerized Neo4j** locally on the dev machine is an acceptable infrastructure cost.
- Validation should move toward the **graph entry points**, using the existing repo preference for **Pydantic-backed validation**.
- Benchmarking is intended to become **dynamic and context-aware**, not hard-coded to a single benchmark across all strategies.
- The migration is expected to be **incremental and non-disruptive**, not a big-bang rewrite.

What this changes in my prior position:

- My earlier objection that the graph should remain only an adjunct reporting layer is **superseded**.
- My earlier concern that a unified CLI was misaligned with current workflows is **partially superseded**: standardization is now a requirement, but it must be introduced with migration discipline.
- My earlier concern that Neo4j implied unjustified scope is **superseded at the strategic level**. The remaining question is not whether Neo4j is allowed, but how to adopt it safely in this repo.

## 2. Concerns That Still Stand (Repo-Aware)

These concerns still stand, but now as migration and implementation constraints rather than arguments against the graph.

### Migration risk

- The current ES/NQ research loop is not centered on `research/runner.py`; it is centered on:
  - `strategies/bear_es_sweep_1h_baseline.py`
  - `strategies/bear_nq_sweep_1h_baseline.py`
  - `research/run_es_nq_baseline.sh`
  - `research/run_es_phase2.sh`
- A graph transition that ignores those real entry points will create a parallel system that operators do not actually use.
- Current artifacts already encode meaningful state:
  - `results/*.csv`
  - `research/results/champions/*.md`
  - `research/results/registry.json`
  - `research/es_nq_bear_sweep_tracker.md`
- If graph ingestion is not deterministic and idempotent, the graph will drift from these artifacts during migration.

### Complexity / ergonomics

- Current workflows are explicit and operator-readable.
- If `qw` is introduced too aggressively, it can hide research steps that are currently obvious in shell commands and Markdown templates.
- Adding graph behavior directly into the strategy scripts too early risks turning already-large research scripts into infrastructure scripts.

### Observability

- Once the graph starts affecting decisions, failures become more serious than “export failed.”
- The repo does not currently have graph-specific observability, replay tooling, or ingestion audit trails.
- Without ingestion receipts and reconciliation, users will not know whether the graph matches the artifacts.

### Testing / validation requirements

- The repo already uses Pydantic in `data/schemas/`, `data/config.py`, and `research/candidate_validator.py`; graph ingestion should match that standard.
- Markdown and CSV are partially structured but not fully normalized; parsers will need tests against real repo fixtures.
- Promotion logic currently lives across docs/templates/scripts. If graph logic becomes authoritative, the validation boundary must be explicit.

### Operational / infra constraints

- Local Docker Neo4j is acceptable, but the repo still needs:
  - connection config
  - startup assumptions
  - failure modes when Neo4j is unavailable
  - local/offline behavior for read-only research runs
- The repo currently has no Neo4j dependency, no compose file, and no graph initialization path.
- MCP, browser push UX, HUD/CodeLens, and remote tunnel access are still real scope multipliers even if they remain desirable long term.

## 3. Reframed Guardrails And Constraints

These are the concrete guardrails I would now enforce.

### Migration / data integrity guardrails

- Graph writes must be **idempotent** against existing CSV/Markdown artifacts.
- Every graph node created from a file artifact must retain a **source artifact reference**:
  - file path
  - content hash or timestamp
  - ingestion time
  - schema version
- Phase 1 graph ingestion must be **append-safe and replay-safe**.
- Graph identifiers for experiments, champions, OOS windows, and strategies must be **deterministic**, not runtime-random.
- The graph layer must support **rebuild from artifacts** during Sidecar and Index phases.

### CLI / workflow guardrails

- **No changes to existing runner scripts’ public CLI flags in Phase 1**.
- Existing commands such as:
  - `python strategies/bear_es_sweep_1h_baseline.py`
  - `python strategies/bear_nq_sweep_1h_baseline.py`
  - `./research/run_es_nq_baseline.sh`
  must remain valid while the graph layer is introduced.
- `qw` should begin by **wrapping or recording** existing workflows, not replacing them outright.
- In early phases, the most conservative hook is:
  - `qw record --artifact <path>` after script completion, or
  - a post-run call at the end of the existing `zsh` wrappers.

### Failure isolation guardrails

- In Phase 1, graph failures must **not invalidate a completed backtest run**.
- In Phase 2, graph failures may block graph-dependent queries, but must not corrupt raw outputs.
- Only in Phase 3 should graph validation begin to gate higher-level decision workflows.
- A failed graph write must produce:
  - a non-zero status for the graph step,
  - a readable error,
  - no partial duplicate state if retried.

### Validation guardrails

- All graph entry points must use **Pydantic validation** before persistence.
- Validation should sit at:
  - artifact parser boundary
  - graph write boundary
  - `qw push` / `qw record` command boundary
- Markdown-derived entities must be parsed into explicit structured models before writing to Neo4j.
- Promotion-related logic must not silently move from docs into Cypher or Python without tests proving parity.

### Observability guardrails

- Every `qw record` or ingestion command must emit an **ingestion receipt** with:
  - input artifact(s)
  - entities written/updated
  - dedupe/upsert outcome
  - validation failures
- A `qw reconcile` or equivalent command should compare graph state against the artifact set.
- Early graph queries must be traceable back to artifact provenance.

### Operational guardrails

- Neo4j access must be **fully optional for read-only workflows in early phases**.
- Configuration should extend the existing `data/config.py` / `.env` pattern rather than inventing a parallel config mechanism.
- The repo should support a **clean disable path**:
  - env flag off
  - CLI `--no-graph`
  - skip post-run hook
- MCP / HUD / remote access must stay behind the core ingestion-and-query milestone.

## 4. Phased Migration Plan (Aligned With Repo)

### Phase 1 — Sidecar

Goal: mirror existing artifacts into validated graph-ready records with minimal disruption.

#### Where new code would live

- `research/graph/models.py`
- `research/graph/parsers.py`
- `research/graph/export.py`
- `research/graph/store.py`
- `research/graph/cli.py`
- optional config additions in `data/config.py`
- optional infra file: `docker-compose.neo4j.yml`

#### How it hooks into existing scripts/runners

Primary non-invasive hook points:

- Add `qw record` calls at the end of:
  - `research/run_es_nq_baseline.sh`
  - `research/run_es_phase2.sh`
- Add optional post-run export hooks in:
  - `strategies/bear_es_sweep_1h_baseline.py` after `run_backtest(...)` / `run_grid_search(...)`
  - `strategies/bear_nq_sweep_1h_baseline.py` after `run_backtest(...)`
- Keep direct Python execution intact; users can still run the scripts without `qw`.

Suggested low-risk hook shape:

- Shell scripts continue to run the existing Python commands.
- After a successful run, they call something like:
  - `qw record --artifact results/es_bear_baseline.csv`
  - `qw record --artifact results/nq_bear_baseline.csv`
- Champion freeze remains manual in Markdown, followed by:
  - `qw record --artifact research/results/champions/es_bear_sweep_1h_v1.md`

#### What data flows into the graph

Start with artifact mirroring from real repo outputs:

- baseline result CSVs in `results/`
- grid search CSVs in `results/`
- champion docs in `research/results/champions/`
- registry state in `research/results/registry.json`
- optional candidate JSON validated by `research/candidate_validator.py`

#### Tests and validation gates required

- Pydantic unit tests for graph models
- parser tests against real repo fixtures:
  - champion markdown
  - grid CSV
  - baseline CSV
  - registry JSON
- idempotent upsert tests
- “artifact missing / malformed / partial” tests
- dry-run CLI mode tests for `qw record`

#### Rollback / disable path

- skip `qw` call in shell wrappers
- `QW_GRAPH_ENABLED=0`
- `qw record --dry-run`
- local file export without Neo4j persistence

### Phase 2 — Index

Goal: make the graph the working index for cross-artifact queries while files remain the raw evidence.

#### Where new code would live

- expand `research/graph/store.py` into actual Neo4j upsert/query implementation
- add `research/graph/query.py`
- add CLI query surfaces in `research/graph/cli.py`
- add docs:
  - `docs/schema.md`
  - `docs/graph_workflow.md`

#### How it hooks into existing scripts/runners

- Existing scripts continue unchanged from an operator perspective.
- `qw` gains higher-level commands that reference existing artifact-producing workflows rather than replacing them:
  - `qw record ...`
  - `qw query ...`
  - `qw reconcile`
- Optional wrapper commands can be introduced later:
  - `qw run es-baseline -- <existing args>`
  but only after direct parity with current Python entrypoints is proven.

#### What data flows into the graph

In addition to Phase 1 artifacts:

- relationships among experiments, champions, backup configs, OOS windows
- benchmark assignment metadata
- tags / asset class / strategy family metadata
- lineage relationships such as:
  - experiment produced champion
  - champion backed by grid row
  - OOS window evaluated champion
  - strategy belongs to research phase/state

This is the phase where the graph begins to justify its presence by answering questions the files cannot.

#### Tests and validation gates required

- query correctness tests against seeded Neo4j fixtures
- parity tests between graph-derived registry/champion state and source artifacts
- benchmark routing tests by asset tags / instrument family
- reconciliation tests that detect drift between files and graph index

#### Rollback / disable path

- keep file artifacts authoritative for manual workflow if graph index fails
- disable `qw query` while continuing to produce artifacts
- rebuild graph from artifacts after failures

### Phase 3 — Primary

Goal: shift decision state and relationship truth into the graph while continuing to emit human-readable artifacts.

#### Where new code would live

- graph modules from prior phases remain primary
- add report/export generators from graph state:
  - graph → markdown champion export
  - graph → registry export
  - graph → summaries for strategy status / OOS readiness

#### How it hooks into existing scripts/runners

- Existing research scripts still execute the backtests.
- `qw` becomes the preferred orchestration layer for:
  - record
  - promote
  - freeze
  - query
  - benchmark resolution
- Manual Markdown trackers become generated or secondary once parity is proven.

#### What data flows into the graph

At this point, the graph becomes authoritative for:

- strategy state
- champion status
- OOS status and pass/fail progression
- benchmark assignment logic
- lineage and pivot relationships
- cross-strategy comparability

Files remain as:

- raw run outputs
- exported reports
- audit-friendly artifacts

#### Tests and validation gates required

- graph-as-primary parity tests before deprecating manual trackers
- export generation tests for champion/report files
- decision-rule tests for promotion / rejection / OOS progression
- migration tests to ensure old artifact sets can still be imported

#### Rollback / disable path

- export current graph state back into file artifacts
- rebuild Markdown/registry snapshots from graph
- temporarily revert operator workflow to artifact-driven decisions while preserving graph history

## 5. Required Graph/Data Model Details

Below is the lowest-risk initial model that matches the current repo.

### Initial node types

#### `Strategy`
Useful because the repo already has stable strategy identities in files such as:

- `strategies/bear_es_sweep_1h_baseline.py`
- `strategies/bear_nq_sweep_1h_baseline.py`
- champion docs in `research/results/champions/`

Suggested properties:

- strategy_id
- instrument / instrument_family
- direction
- timeframe
- asset_class
- tags
- source_script

#### `ExperimentRun`
Maps to baseline or single-run backtest results.

Suggested sources:

- baseline CSV outputs
- optional structured sidecar JSON generated after `run_backtest(...)`

Suggested properties:

- run_id
- strategy_id
- config_hash
- phase
- date_range
- metrics summary
- artifact path

#### `GridSearchRun`
Maps to grid CSV outputs such as `results/es_bear_sweep_1h_grid_nypre_london_v1.csv`.

Suggested properties:

- grid_id
- strategy_id
- source_csv
- generated_at
- phase

#### `GridRow` or `ConfigurationResult`
Low-risk because each CSV row already represents a structured configuration outcome.

Suggested properties:

- config_id
- sessions
- target_r
- wick_mode
- atr_mult_stop
- n
- win_rate
- avg_r
- total_r
- profit_factor
- sharpe
- max_dd

#### `Champion`
Maps directly to champion Markdown docs such as `research/results/champions/es_bear_sweep_1h_v1.md`.

Suggested properties:

- champion_id
- strategy_id
- freeze_date
- status
- rationale
- fragilities
- source_markdown

#### `OOSWindow`
Maps to the OOS workflow documented in champion files and SOP docs.

Suggested properties:

- oos_id
- champion_id
- start_date
- end_date
- gates_passed
- artifact_path

#### `Artifact`
Needed from Phase 1 onward so the graph remains traceable to files.

Suggested properties:

- artifact_id
- file_path
- artifact_type
- content_hash
- created_at / ingested_at

#### `BenchmarkSpec`
Needed early because Gemini clarified dynamic benchmarking as a core requirement.

Suggested properties:

- benchmark_id
- benchmark_type
- asset_scope
- tag_rules
- expression / definition
- active_from

### Initial edge types

- `(:ExperimentRun)-[:USES_CONFIG]->(:ConfigurationResult)`
- `(:GridSearchRun)-[:HAS_RESULT]->(:ConfigurationResult)`
- `(:Champion)-[:PROMOTED_FROM]->(:ConfigurationResult)`
- `(:Champion)-[:BACKUP_IS]->(:ConfigurationResult)`
- `(:OOSWindow)-[:EVALUATES]->(:Champion)`
- `(:Artifact)-[:BACKS]->(:ExperimentRun | :GridSearchRun | :Champion | :OOSWindow)`
- `(:Strategy)-[:HAS_RUN]->(:ExperimentRun | :GridSearchRun)`
- `(:Strategy)-[:HAS_CHAMPION]->(:Champion)`
- `(:Strategy)-[:USES_BENCHMARK]->(:BenchmarkSpec)`

### How they map to existing CSV/Markdown structures

- Grid CSV rows already map naturally to `ConfigurationResult`.
- Champion Markdown already contains:
  - config
  - IS metrics
  - backup config
  - OOS command
  - OOS gates
  - freeze rationale
- `research/results/registry.json` can map to strategy lifecycle/status state.
- `research/es_nq_bear_sweep_tracker.md` can remain a raw operator artifact in Phase 1 and become a generated/exported summary later.

### Where Pydantic validation should sit

Pydantic should sit at four boundaries:

1. **Artifact parsing boundary**
   - CSV row → validated `ConfigurationResultModel`
   - Markdown champion → validated `ChampionModel`
   - registry entry → validated `StrategyStateModel`

2. **CLI boundary**
   - `qw record`
   - `qw push`
   - future `qw promote` / `qw freeze`

3. **Persistence boundary**
   - validated model → Neo4j upsert payload

4. **Decision boundary**
   - before promotion state changes or benchmark assignment logic is written

### Where dynamic benchmarking rules would plug in

Dynamic benchmarking should not be hard-coded into individual strategy scripts first.

Instead, introduce a `BenchmarkResolver` in the graph layer that uses properties such as:

- asset_class
- instrument_family
- tags (`#Futures`, `#Crypto`, `#Indices`, etc.)
- explicit benchmark override on strategy/champion/run

Repo-aligned implementation point:

- benchmark assignment belongs in `research/graph/` logic first
- only after the rule set stabilizes should optional backtest metrics include benchmark-derived fields

That allows:

- futures strategies to route toward futures-relevant benchmarks
- crypto strategies to route toward BTC/ETH-style baskets
- mixed or regime-specific benchmark logic later without rewriting the current research scripts first

## 6. Implementation To-Do List

| Priority | Item | Likely files/modules to touch | Phase | Autonomous vs manual |
|---|---|---|---|---|
| 1 | Add graph config scaffolding using existing settings pattern | `data/config.py`, `env.example`, `pyproject.toml` | 1 | Safe to implement autonomously |
| 2 | Create Pydantic graph models for artifacts, experiment runs, grid rows, champions, registry state | `research/graph/models.py` | 1 | Safe to implement autonomously |
| 3 | Build parsers for grid CSV, champion markdown, registry JSON | `research/graph/parsers.py`, fixtures under `tests/` | 1 | Safe to implement autonomously |
| 4 | Add a `qw record` CLI that validates and emits dry-run receipts before any Neo4j write | `research/graph/cli.py`, `pyproject.toml` | 1 | Safe to implement autonomously |
| 5 | Add a Neo4j store/upsert layer with idempotent writes | `research/graph/store.py` | 1 | Needs light manual design on schema keys, then safe |
| 6 | Add `docker-compose.neo4j.yml` and minimal graph setup docs | repo root docs + compose file | 1 | Safe to implement autonomously |
| 7 | Hook `qw record` into `research/run_es_nq_baseline.sh` and `research/run_es_phase2.sh` after successful runs | `research/run_es_nq_baseline.sh`, `research/run_es_phase2.sh` | 1 | Safe to implement autonomously if hook behavior is agreed |
| 8 | Add optional post-run structured sidecar export in ES/NQ baseline scripts | `strategies/bear_es_sweep_1h_baseline.py`, `strategies/bear_nq_sweep_1h_baseline.py` | 1 | Needs manual design on output contract first |
| 9 | Add reconciliation command to compare graph state vs artifacts | `research/graph/cli.py`, `research/graph/reconcile.py` | 2 | Safe to implement autonomously |
| 10 | Add query surfaces for strategy lineage, champion lookup, uncorrelated candidate search | `research/graph/query.py`, `research/graph/cli.py` | 2 | Needs manual design on query semantics |
| 11 | Add benchmark resolver driven by asset/tags/overrides | `research/graph/benchmarks.py`, docs/schema | 2 | Needs manual design first |
| 12 | Add graph-backed promotion/freeze/OOS state transitions | `research/graph/workflow.py`, champion/registry integration | 3 | Requires manual design first |
| 13 | Generate markdown/registry exports from graph state | `research/graph/export.py` | 3 | Safe after models are stabilized |
| 14 | Add `qw run ...` wrappers that standardize current strategy entrypoints | `research/graph/cli.py` or package entrypoint | 3 | Needs manual design first |
| 15 | Evaluate MCP/HUD/browser push once ingestion/query value is proven | future `api/` / extension-specific modules | 3+ | Not safe to implement autonomously yet |

## 7. Points Of Continuing Disagreement

These are the areas where I still think Gemini’s pushback understates repo-specific risk. I am not arguing against the graph end state; I am arguing for a safer path to it.

### Disagreement 1: “Graph as source of truth” should not mean “graph stores every raw datum” immediately

#### Repo-specific issue

The repo already produces multiple raw artifact forms:

- CSV results in `results/`
- champion Markdown in `research/results/champions/`
- backtest logic embedded in large Python strategy scripts
- likely future OOS result files following the same pattern

Promoting the graph to primary too early for both relationships **and raw evidence** would increase ingestion complexity and duplicate storage concerns before query value is proven.

#### Compromise

Make the graph primary first for:

- relationships
- status transitions
- benchmark resolution
- lineage
- decision state

Keep raw numeric outputs and human-readable exports in files even in Phase 3.

This still honors the graph-centric strategy, but avoids turning Neo4j into an awkward store for every raw run artifact.

### Disagreement 2: A unified `qw` CLI should not replace direct script usage before parity is proven

#### Repo-specific issue

The actual working surfaces today are the existing scripts and shell wrappers, not `research/runner.py`.

If `qw` becomes mandatory too early, it introduces failure points into the exact workflows currently used for ES/NQ research.

#### Compromise

Phase the CLI as:

- Phase 1: `qw record` only
- Phase 2: `qw query`, `qw reconcile`
- Phase 3: optional `qw run ...` wrappers

Only once `qw run ...` can faithfully reproduce the existing strategy invocations should it become the preferred entrypoint.

### Disagreement 3: MCP / HUD / browser push are not part of the minimum viable graph transition

#### Repo-specific issue

The repo currently shows clear evidence of:

- script-driven research
- Markdown templates
- CSV outputs
- Pydantic validation

It does **not** show equivalent evidence of:

- active MCP plumbing
- editor extension infrastructure
- a browser-ingestion workflow already in regular use

#### Compromise

Treat these as post-ingestion enhancements:

- first prove `record -> index -> query -> decision` value
- then add browser push or HUD surfaces once the graph schema and CLI stabilize

That keeps the architecture aligned with long-term intent while avoiding premature interface sprawl.

### Disagreement 4: Dynamic benchmarking is correct strategically, but should not be forced into the strategy scripts first

#### Repo-specific issue

Current strategy scripts are already large and focused on research execution. Embedding benchmark-routing logic directly into `strategies/bear_es_sweep_1h_baseline.py` and `strategies/bear_nq_sweep_1h_baseline.py` would mix concerns and make those scripts harder to maintain.

#### Compromise

Implement benchmark routing in the graph layer first via:

- validated tags / asset classes
- benchmark resolver logic
- graph query layer

Then expose benchmark-derived metrics back into reports once stable.

That still supports the graph-as-decision-truth model without turning research scripts into graph/business-rule hubs.

