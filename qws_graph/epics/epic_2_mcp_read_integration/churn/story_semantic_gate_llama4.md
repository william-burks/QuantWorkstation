# Story 2 — Semantic Gate: Llama 4 Scout Analyst

## Status
DRAFT

## Priority
P2 — Research Enhancement. Story 1's math gate is correct and ship-safe. This story adds
a second reasoning tier on top of it for richer curation. Implement after Story 1 is proven
stable in practice.

## Context
Story 1 introduced the significance gate: a math-only tier that selects top-N by Sharpe +
bottom-N by drawdown. This is safe and fast, but it's purely statistical. It cannot reason
about whether two high-Sharpe runs are actually *different* strategies (e.g., RSI 14 vs. RSI
15 with nearly identical equity curves), nor can it explain *why* a run was selected.

This story adds an optional **Semantic Tier** that runs after the math tier: a local Llama 4
Scout inference pass that evaluates the math candidates and produces a `curator_note` for each
selected run. The note is stored on the `Run` node in Neo4j and surfaced via `qw query`.

---

## Prerequisites (Not ACs — must be satisfied before implementation)

1. **llama-stack server running locally:**
   ```zsh
   pip install llama-stack-client
   llama model download --model-id Llama-4-Scout-17B-16E-Instruct
   llama stack build --template local --image-type conda
   llama stack run local --port 5001
   ```
2. **Env var set:** `QW_AI_ANALYST_ENDPOINT=http://localhost:5001`
3. **Story 1 stable:** `apply_significance_gate` in `curator.py` is the baseline.

---

## Design

### 1. Two-Tier Flow

```
grid_csv artifact (1,000 rows)
         │
         ▼
  [Math Tier — curator.py]
  top_n_sharpe=20 (semantic mode)
  bottom_n_drawdown=0 (LLM handles risk cases)
  → 20 candidates
         │
         ▼ (only when --analyze flag + QW_AI_ANALYST_ENDPOINT set)
  [Semantic Tier — analyst.py]
  Llama 4 Scout evaluates 20 candidates in one batch
  Returns: { run_id → {approved: bool, curator_note: str} }
         │
         ▼
  Selected runs (~7) with curator_note set
  + RunStatsSummary for remainder
         │
         ▼
  GraphStore.persist_artifact(selected, summary)
```

When `--analyze` is NOT passed, the math tier runs with Story 1 defaults (top-5 Sharpe +
bottom-2 drawdown) and no `curator_note` is set. No behaviour change for existing callers.

### 2. `apply_significance_gate` — Revised Signature

The existing signature from Story 1:
```python
def apply_significance_gate(
    artifact: ResearchArtifact,
    top_n_sharpe: int = 5,
    bottom_n_drawdown: int = 2,
    pinned_run_ids: set[str] | None = None,
) -> tuple[ResearchArtifact, RunStatsSummary]:
```

The semantic flag is **not** a parameter on `apply_significance_gate` directly. Instead,
`cmd_record` in `cli.py` orchestrates the two-tier call:

```python
# cli.py — cmd_record (semantic path)
if kind == "grid_csv" and args.analyze and endpoint:
    candidates, summary = apply_significance_gate(
        artifact, top_n_sharpe=20, bottom_n_drawdown=0
    )
    analyst = LlamaAnalyst.from_env()
    artifact = analyst.annotate(candidates)   # adds curator_note to selected runs
    # artifact now has ≤20 runs, each with curator_note
    # apply a final cap to keep only approved runs
    artifact = _keep_approved(artifact)
elif kind == "grid_csv" and not args.all:
    artifact, summary = apply_significance_gate(artifact)   # Story 1 defaults unchanged
```

`apply_significance_gate` itself is **not modified** by this story. Orchestration lives in
`cli.py`. The analyst module is a standalone pure function.

### 3. `research/graph/analyst.py` — New Module

```python
class LlamaAnalyst:
    """Thin llama-stack-client wrapper for grid-sweep semantic evaluation."""

    def __init__(self, endpoint: str, model_id: str, temperature: float = 0.1):
        ...

    @classmethod
    def from_env(cls) -> LlamaAnalyst:
        endpoint = os.getenv("QW_AI_ANALYST_ENDPOINT", "")
        model_id = os.getenv("QW_AI_ANALYST_MODEL", "Llama-4-Scout-17B-16E-Instruct")
        ...

    def annotate(self, artifact: ResearchArtifact) -> ResearchArtifact:
        """Evaluate all runs in *artifact* and return an annotated copy.

        Each run's curator_note is set based on the LLM response.
        Raises LlamaUnavailableError when the endpoint is unreachable.
        """
        ...
```

Key internal functions (private):

| Function | Purpose |
|---|---|
| `_build_prompt(strategy, runs)` | Constructs system + user prompt; injects compact CSV of run stats |
| `_parse_response(raw_json)` | Defensive JSON parser; returns `dict[run_id, AnnotationResult]` |

#### Prompt design

The prompt uses a compact CSV representation to minimise context:

```
System: You are a quantitative research analyst reviewing backtest results...

User:
Strategy: es-1h-bear-rsi-reversion | MeanReversion | bear
Candidates (run_id,sharpe,profit_factor,win_rate,max_drawdown,total_trades):
run-0001,1.82,1.34,0.52,-8.2,210
run-0002,1.79,1.29,0.51,-9.1,198
...

Task: For each run_id, return JSON:
[{"run_id": "...", "approved": true|false, "curator_note": "one sentence"}]
```

Temperature: `0.1` (analytical mode, not creative).
Context budget: 20 rows × ~60 tokens/row ≈ 1,200 input tokens, 
which is trivially small relative to Llama 4 Scout’s available context window; 
no “8k–16k context needed” constraint applies here.

#### `AnnotationResult` (internal dataclass)

```python
@dataclass(frozen=True)
class AnnotationResult:
    run_id: str
    approved: bool
    curator_note: str
```

#### Resilience

If `QW_AI_ANALYST_ENDPOINT` is unset or the server is unreachable:
- `LlamaAnalyst.from_env()` raises `LlamaUnavailableError` (a `RuntimeError` subclass)
- `cmd_record` catches it, logs `WARNING: AI analyst unavailable — falling back to math tier`
  to stderr, and continues with Story 1 defaults
- Zero blocking. The run succeeds.

### 4. Schema Change — `Run.curator_note`

`curator_note` is a property on the `Run` node in Neo4j (not on `RunStatsSummary`).
Only selected runs are persisted; unselected runs have no node to attach a note to.

Changes required:
- `research/graph/models.py`: `Run` gains `curator_note: str | None = None`
- `research/graph/cypher.py`: `CSV_INGEST_QUERY` sets `r.curator_note = row.run.curator_note`
- `research/graph/query_models.py`: `RunHistoryItemV1` gains `curator_note: str | None`
- `research/graph/query.py`: `GET_RUN_HISTORY_V1_CYPHER` returns `curator_note: r.curator_note`

### 5. CLI Surface

```zsh
# Math tier only (Story 1 default — unchanged)
qw record --file results/grid.csv --kind grid_csv

# Semantic tier
qw record --file results/grid.csv --kind grid_csv --analyze

# Semantic tier + all rows to math (bypass story 1 gate, then semantic)
qw record --file results/grid.csv --kind grid_csv --analyze --all
```

`--analyze` flag added to `qw record` subparser. Ignored for non-`grid_csv` kinds.

### 6. Query Surface for `curator_note`

`curator_note` is a run-level property. It is **not** surfaced via `strategy_summary`
(which returns strategy-level aggregate counts). The correct surface is run history.

A new `run_history` preset is added to `PRESET_CATALOG` in `query_presets.py`:

```zsh
qw query --name run_history --param strategy_id=es-1h-bear-rsi-reversion
```

Output includes `curator_note` per row (via the existing `RunHistoryItemV1` DTO once
updated). This is the correct query for inspecting per-run analyst notes.

---

## Acceptance Criteria

- [ ] `research/graph/analyst.py` exists with `LlamaAnalyst` class and `annotate()` method.
      `LlamaUnavailableError` is raised (not swallowed) when endpoint is unreachable; caller
      catches it.
- [ ] `qw record --kind grid_csv --analyze` invokes the semantic tier when
      `QW_AI_ANALYST_ENDPOINT` is set; falls back to Story 1 math-tier defaults with a
      `WARNING` on stderr when the endpoint is not set or unreachable.
- [ ] `Run` model gains `curator_note: str | None = None`. `CSV_INGEST_QUERY` persists it.
      `RunHistoryItemV1` DTO gains `curator_note: str | None`. `GET_RUN_HISTORY_V1_CYPHER`
      returns `r.curator_note`.
- [ ] A new `run_history` preset is added to `PRESET_CATALOG`. `qw query --name run_history
      --param strategy_id=<id>` returns run rows including `curator_note` (may be `null` for
      runs ingested without `--analyze`).
- [ ] Prompt uses compact CSV row format (no verbose JSON per row). Token count for a 20-run
      batch must be < 2,000 tokens (verifiable via `_estimate_prompt_tokens()` utility).
- [ ] Unit tests in `tests/unit/test_analyst.py` cover: successful annotation round-trip
      (mock client), partial LLM response (some run IDs missing), malformed JSON response
      (defensive parser returns math-tier fallback), and `LlamaUnavailableError` propagation.
- [ ] Existing tests (`test_curator.py`, `test_qw_query.py`, `test_mcp_adapter.py`,
      `test_lineage_queries.py`) remain green — `curator_note` defaults to `None` and no
      existing assertions break.

---

## Repo Touchpoints

| File | Change |
|---|---|
| `research/graph/analyst.py` | **New.** `LlamaAnalyst`, `LlamaUnavailableError`, `AnnotationResult` |
| `research/graph/models.py` | `Run.curator_note: str | None = None` |
| `research/graph/cypher.py` | `CSV_INGEST_QUERY` sets `r.curator_note` |
| `research/graph/query_models.py` | `RunHistoryItemV1.curator_note: str | None` |
| `research/graph/query.py` | `GET_RUN_HISTORY_V1_CYPHER` returns `curator_note`; `get_run_history_v1` constructs it |
| `research/graph/query_presets.py` | Add `run_history` preset to `PRESET_CATALOG` |
| `research/graph/cli.py` | Add `--analyze` to `qw record` subparser; orchestrate two-tier call in `cmd_record` |
| `tests/unit/test_analyst.py` | **New.** Analyst unit tests with mock client |
| `docs/graph_v1_contract.md` | `Run` node gains `curator_note` property; `run_history` preset documented |

`curator.py` and `apply_significance_gate` are **not modified** by this story.

---

## Definition of Done

- [ ] All new unit tests pass with a mock llama-stack client (no live LLM required for CI).
- [ ] `qw record --kind grid_csv --analyze` with a real llama-stack endpoint produces runs
      with non-null `curator_note` in Neo4j (manual smoke test).
- [ ] `qw query --name run_history --param strategy_id=<id>` shows `curator_note` per row.
- [ ] `qw record --kind grid_csv --analyze` with no endpoint set falls back cleanly and
      produces the same output as `qw record --kind grid_csv`.
- [ ] Story marked CLOSED after test suite passes.

---

## Dependencies

- **Depends on (CLOSED):** Story 1 — `apply_significance_gate`, `RunStatsSummary`, `Run`
  model, `curator.py` are all prerequisites.
- **Enables:** MCP can ask "why was this run selected?" and receive an analyst note rather
  than just a Sharpe rank position.

---

## Open Questions

1. **Approved vs. unapproved handling:** If Llama returns `approved: false` for a run that
   ranked in the math top-20, should it be excluded from the final ingest, or included with
   a `curator_note` flagging the concern? Recommend: exclude and log; the math tier's job
   was to produce candidates, not guarantees. Unapproved candidates roll into `RunStatsSummary`.

2. **`curator_note` length:** One sentence enforced in the prompt, but the LLM may ignore
   this. Should the parser truncate at 280 characters? Recommend yes — keeps Neo4j node size
   predictable.

3. **Caching:** If the same 20 runs are evaluated twice (re-ingest), should the LLM be
   called again or should existing `curator_note` values be preserved? Recommend: skip
   re-evaluation if `Run` node already has a non-null `curator_note` (MERGE + SET only on
   null). Implement in `cmd_record`, not in the analyst.

4. **Model swap:** Should `QW_AI_ANALYST_MODEL` be configurable to allow swapping
   Llama 4 Scout for a smaller/faster model during development? Recommend yes — already
   included in `LlamaAnalyst.from_env()` design above.
