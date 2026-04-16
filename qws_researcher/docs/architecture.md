# QuantResearcher Architecture

## Overview

Four MCP servers + one shared data layer + one execution environment.

## MCP Servers

| Server | Purpose | Tools |
|--------|---------|-------|
| papers-mcp | Academic literature — search, fetch, store, campus workflow | 30 tools |
| quant-sandbox-mcp | Python execution in isolated Docker container | 6 tools (run_python, list_session_vars, reset_session, get_session_info, install_package, log_sandbox_result) |
| experiment-mcp | Research findings — log, query, search experiments, hypotheses, graph links | 14 tools (9 core + 4 graph + list_incomplete_experiments) |
| search-mcp | Unified semantic search across all research artifacts | 5 tools (unified_search, search_all_notes, research_summary, find_connections, graph_summary) |
| github (official) | GitHub repo search and code reading | external |

## Shared Data Layer — research_core

All MCP servers (except sandbox and github) read from and write to a single shared store:

- **SQLite database**: `~/ClaudeProjects/QuantResearcher/core/data/research.db`
  - Tables: papers, experiments, hypotheses, notes
  - WAL mode enabled, FTS5 for full-text search on notes
- **ChromaDB vector index**: `~/ClaudeProjects/QuantResearcher/core/data/chroma/`
  - Single collection: "research"
  - Entity types indexed: paper, experiment, hypothesis, note
  - Embeddings model: all-MiniLM-L6-v2
- **ResearchGraph** — directed knowledge graph stored in `relationships` table in research.db
  - Valid relationships: informed, implements, tested, supports, contradicts, extends, replicates, cites
  - Path finding via BFS (max 4 hops), neighborhood queries

## Data Flow

```
search_papers() → papers-mcp → research_core → research.db + chroma/
log_experiment() → experiment-mcp → research_core → research.db + chroma/
unified_search() → search-mcp → research_core → chroma/ → research.db
```

## Directory Structure

```
QuantResearcher/
├── core/                          # shared data layer
│   ├── research_core/             # Python package
│   │   ├── models.py              # Paper, Experiment, Hypothesis, ResearchNote
│   │   ├── store.py               # SQLite operations
│   │   ├── vector.py              # ChromaDB operations
│   │   └── graph.py               # Knowledge graph (Phase 3C)
│   ├── data/                      # runtime data (gitignored)
│   │   ├── research.db
│   │   └── chroma/
│   └── migrate_papers.py
├── mcp/
│   ├── papers-mcp/               # literature layer
│   ├── quant-sandbox-mcp/        # execution layer
│   ├── experiment-mcp/           # findings layer
│   └── search-mcp/               # unified search layer (Phase 3B)
├── library/                       # campus download workflow
│   ├── inbox/
│   ├── ingested/
│   └── unmatched/
├── jobs/                          # scheduled maintenance
│   ├── nougat_upgrade.py
│   ├── nougat_upgrade.sh
│   └── com.quantresearcher.nougat.plist
├── research/                      # research outputs
│   ├── hypotheses/
│   ├── experiments/
│   ├── notes/
│   └── reports/
└── info/                          # project documentation
```

## Environment Variables

| Variable | Default | Used by |
|----------|---------|---------|
| `RESEARCH_DATA_DIR` | `~/ClaudeProjects/QuantResearcher/core/data` | papers-mcp, experiment-mcp, search-mcp |
| `SEMANTIC_SCHOLAR_API_KEY` | none | papers-mcp |
| `PUBMED_EMAIL` | none | papers-mcp |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | none | github MCP |
