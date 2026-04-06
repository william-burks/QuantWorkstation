# Story — Normalize Artifact Path Format

## Status
CLOSED — `_artifact_path_text(path, repo_root=None)` updated in `parsers.py` to normalize
to repo-relative POSIX path when `repo_root` is provided. `CSVParser` and
`ChampionMarkdownParser` both accept `repo_root` and pass it through. `_parse_artifact`
in `cli.py` passes `repo_root` to all three parse paths. Migration query documented below.

## Problem

Artifact paths stored on `:Run` and `:Champion` nodes exist in three different formats
depending on which ingest path wrote them:

| Source | Format seen | Example |
|--------|-------------|---------|
| Bundle ingest (`qw record --bundle`) | Absolute | `/Users/will/ClaudeProjects/QuantWorkstation/research/results/...` |
| Direct CSV ingest with relative path | Relative, no prefix | `results/futures/liquidity_sweep/runs/.../baseline_results.csv` |
| Some runners via `--source-file` | Relative with `research/` prefix | `research/results/futures/.../baseline_results.csv` |

`portfolio_alpha` and other queries that surface `artifact_path` return mixed formats.
Any downstream tool (file preview, MCP read tool) that tries to resolve a path must
special-case all three formats or break silently.

## Root Cause

The CLI (`cli.py`) has the repo root available at ingest time (used for `.qws/receipts/`
and for reading `bundle.json`). It does not normalize the path before writing it to Neo4j.

## Fix

At ingest time in `cli.py`, normalize every `artifact_path` to repo-relative format
(no leading slash, no `research/` prefix — relative to repo root) before passing to
`store.persist()`. Use the repo root already available in the CLI context.

Pseudocode:
```python
def _normalize_artifact_path(path: str, repo_root: Path) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            return str(p.relative_to(repo_root))
        except ValueError:
            return path  # not under repo root — leave as-is
    return path  # already relative
```

For existing nodes, a migration query can re-read all `:Run` nodes and strip the
repo root prefix where present:

```cypher
MATCH (r:Run) WHERE r.artifact_path STARTS WITH '/Users/will/ClaudeProjects/QuantWorkstation/'
SET r.artifact_path = substring(r.artifact_path, size('/Users/will/ClaudeProjects/QuantWorkstation/'))
```

Note: the hardcoded prefix in the migration query is acceptable for a one-shot
local migration; the normalization logic in `cli.py` must be repo-root-relative,
not path-prefix-hardcoded.

## Acceptance Criteria

- [x] All new `:Run` and `:Champion` nodes written after this story use repo-relative
  `artifact_path` (no leading slash, relative to repo root). (`_artifact_path_text` updated,
  both parsers and `_parse_artifact` pass `repo_root` through)
- [x] `MATCH (r:Run) WHERE r.artifact_path STARTS WITH '/' RETURN count(r)` returns 0
  after migration and a fresh pipeline run. — Verified on Neo4j/5.26.24 localhost:7687, count = 0.
- [x] Unit tests: `_artifact_path_text` normalization verified across absolute, relative,
  and outside-repo-root cases. (`TestArtifactPathNormalization`, 5 tests passing)
- [x] MCP read tool or any downstream resolver only needs one path-resolution strategy.
  (repo-relative is now the canonical format at write time)

## Scope
- `qws_graph/research/graph/cli.py` — normalize at ingest before `store.persist()`
- One-shot migration query (documented in story, run manually)
- Unit tests for normalization helper
