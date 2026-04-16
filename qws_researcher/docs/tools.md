# MCP Tools Reference

## papers-mcp

### Search & Fetch

| Tool                      | Purpose                                                                               | Key Args                             |
|---------------------------|---------------------------------------------------------------------------------------|--------------------------------------|
| `search_papers(query)`    | Search S2 and arXiv in parallel                                                       | `sources`, `max_per_source`, `save`  |
| `fetch_paper(paper_id)`   | Get full text; downloads PDF if needed                                                | `paper_id` e.g. `"arxiv:2301.00001"` |
| `read_paper(paper_id)`    | Load full text into context (50k char cap)                                            | `paper_id`                           |
| `read_abstract(paper_id)` | Return abstract + header only — no full text load; fetches metadata if not in library | `paper_id`                           |
| `fetch_ssrn(url)`         | Fetch SSRN paper metadata (Cloudflare-blocked — use ingest_pdf instead)               | `url`                                |

### Library Management

| Tool | Purpose | Key Args |
|------|---------|----------|
| `search_library(query)` | Semantic search across local papers only | `query`, `n` |
| `search_by_tag(tags)` | Exact tag filter — returns papers matching ALL tags | `tags: list[str]` |
| `list_library()` | List all stored papers | `source` (optional filter) |
| `get_paper_metadata(paper_id)` | Full paper state without loading 50k text; includes `has_full_text`, `campus_download_needed`, `doi_filename`, `github_repos` | `paper_id` |
| `library_stats()` | Count papers by source, vector chunks | — |
| `find_similar(paper_id)` | Vector similarity + S2 recommendations | `paper_id`, `n` |
| `get_citations(paper_id)` | Papers citing this one (via S2) | `paper_id` |
| `fix_metadata(dry_run)` | Scan library for papers with bad metadata (title missing or set to URL); `dry_run=True` (default) reports without changing | `dry_run` |

### Bookmarking & Campus Workflow

| Tool | Purpose | Key Args |
|------|---------|----------|
| `bookmark_paper(paper_id, reason, tags)` | Save paper to library; adds to campus trip list if no full text | `paper_id`, `reason`, `tags` |
| `bulk_bookmark(paper_ids, reason, tags)` | Bookmark multiple papers at once | `paper_ids`, `reason`, `tags` |
| `list_needed(tags)` | Papers on campus trip list, optional tag filter | `tags` (optional) |
| `campus_list_stats()` | Count of trip-list papers, split by DOI known/unknown | — |
| `export_campus_list()` | Write `research/notes/campus-trip-YYYY-MM-DD.md` — checklist split by DOI known vs unknown | — |
| `remove_from_campus_list(paper_id)` | Remove a paper from the campus trip list | `paper_id` |
| `ingest_pdf(file_path, paper_id)` | Manually ingest a single PDF | `file_path`, `paper_id`, `title`, `authors` |
| `ingest_folder()` | Process all PDFs in library/inbox/; clears ingested papers from campus list | — |

### Annotation & Organisation

| Tool | Purpose | Key Args |
|------|---------|----------|
| `add_note(paper_id, note)` | Append a research note to a paper | `paper_id`, `note` |
| `update_note(paper_id, note)` | Replace the research note entirely | `paper_id`, `note` |
| `tag_paper(paper_id, tags)` | Add tags to a paper (preserves existing) | `paper_id`, `tags: list[str]` |
| `remove_tag(paper_id, tags)` | Remove tags from a paper | `paper_id`, `tags: list[str]` |
| `add_repo(paper_id, repo, notes)` | Link a GitHub repo to a paper (e.g. reference implementation) | `paper_id`, `repo` e.g. `"owner/repo"`, `notes` (optional) |
| `reading_list()` | Papers tagged `to-read`, sorted by citation count desc | — |

### Discovery

| Tool | Purpose | Key Args |
|------|---------|----------|
| `get_related_papers(paper_id)` | Three-signal related paper list: vector similarity + S2 recommendations + shared tags | `paper_id`, `n` |
| `cite(paper_id, format)` | Generate citation from stored metadata. Formats: `bibtex`, `apa`, `chicago` | `paper_id`, `format` |

## quant-sandbox-mcp

| Tool | Purpose | Key Args |
|------|---------|----------|
| `run_python(code)` | Execute Python in Docker sandbox | `timeout` |
| `list_session_vars()` | Show persistent session variables | — |
| `get_session_info()` | Container status and resource usage | — |
| `install_package(package)` | Install pip package in sandbox | — |
| `reset_session()` | Clear all session state | — |
| `log_sandbox_result(title, hypothesis, conclusion, experiment_type)` | Bridge tool: captures last run_python execution and pre-fills log_experiment payload | `experiment_type`, `paper_id`, `tags` |

## Paper ID Formats

| Prefix | Example | Source |
|--------|---------|--------|
| `arxiv:` | `arxiv:2301.00001` | arXiv |
| `s2:` | `s2:abc123def456` | Semantic Scholar |
| `pmid:` | `pmid:12345678` | PubMed |
| `ssrn:` | `ssrn:4567890` | SSRN |
| `local:` | `local:paper_stem` | Manually ingested, no ID |

## experiment-mcp

### Experiments

| Tool | Purpose | Key Args |
|------|---------|----------|
| `log_experiment(title, dataset, hypothesis, code, results, conclusion)` | Log a completed experiment with metrics; validates results against schema | `paper_id`, `github_repo`, `parameters`, `tags`, `experiment_type` |
| `update_experiment(experiment_id)` | Update conclusion, results, status, or tags on an existing experiment | `conclusion`, `results`, `status`, `tags` |
| `get_experiment(experiment_id)` | Full experiment detail including code | — |
| `list_experiments()` | List experiments with optional filters | `paper_id`, `status`, `tag`, `min_sharpe` |
| `search_experiments(query)` | Semantic search across hypotheses and conclusions | `query`, `n` |
| `experiment_stats()` | Total count, breakdown by status, best Sharpe per dataset, tag distribution, type-specific aggregations | `experiment_type` (optional filter) |
| `list_incomplete_experiments()` | List experiments with missing key metrics (schema warnings) | — |

### Hypotheses

| Tool | Purpose | Key Args |
|------|---------|----------|
| `log_hypothesis(title, description)` | Log a new research hypothesis for future testing | `paper_ids`, `tags` |
| `update_hypothesis(hypothesis_id)` | Update status, link experiments, or update description | `status`, `experiment_ids`, `description` |
| `list_hypotheses()` | List hypotheses with optional status filter | `status` |

### Graph

| Tool | Purpose | Key Args |
|------|---------|----------|
| `link_entities(from_id, from_type, to_id, to_type, relationship)` | Create directed relationship between entities | `relationship`: informed, implements, tested, supports, contradicts, extends, replicates, cites |
| `get_connections(entity_id, direction, relationship)` | Get all graph relationships for an entity | `direction`: out/in/both |
| `get_research_trail(from_id, to_id)` | Find paths between two entities | `max_depth` |
| `get_neighborhood(entity_id, depth)` | Local subgraph around an entity | `depth` |

### Experiment Status Values

`"running"` → `"complete"` | `"failed"` | `"abandoned"`

### Hypothesis Status Values

`"open"` → `"testing"` → `"confirmed"` | `"rejected"` | `"abandoned"`

## search-mcp

### Unified Search

| Tool | Purpose | Key Args |
|------|---------|----------|
| `unified_search(query)` | Semantic search across papers, experiments, hypotheses, notes | `query`, `entity_types`, `n` |
| `search_all_notes(query)` | FTS5 keyword search across all notes | `query` |
| `research_summary()` | High-level counts and recent activity across all artifacts | — |
| `find_connections(entity_id)` | Find semantically related items across all entity types | `entity_id`, `n` |
| `graph_summary()` | Overview of knowledge graph — relationship counts, most connected entities | — |

## Paper Data Model — Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `doi` | `str \| None` | Set from S2 metadata; enriched via Crossref if missing at bookmark time |
| `tags` | `list[str]` | User-managed; used by `search_by_tag`, `reading_list` |
| `notes` | `str \| None` | Free-text research notes; `add_note` appends, `update_note` replaces |
| `github_repos` | `list[str]` | Linked GitHub repos in `"owner/repo"` format; managed via `add_repo` |
| `text_extractor` | `str \| None` | `"pymupdf4llm"`, `"nougat"`, `"nougat-low-confidence"`, or `None` |
| `has_full_text` | computed | `True` if `full_text` or `text_path` present (returned by `get_paper_metadata`) |
