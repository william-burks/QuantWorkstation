# Research Workflow

The end-to-end loop from idea to logged result.

---

## 1. Explore

Search and evaluate papers before committing to them.

```
search_papers("price impact Kyle model")
read_abstract("s2:xxxx")          # quick eval without loading full text
get_paper_metadata("s2:xxxx")     # check has_full_text, citations, existing tags
```

If the abstract is promising:

```
bookmark_paper("s2:xxxx", reason="Test Kyle lambda on MGC data", tags=["microstructure", "to-implement"])
```

`bookmark_paper` handles everything:
- Saves metadata to library if not already there
- Applies tags and reason note
- Adds to campus trip list automatically if no full text

---

## 2. Campus Trip

**Before you leave:**

```
list_needed()                     # see your full trip list with filename hints
export_campus_list()              # writes research/notes/campus-trip-YYYY-MM-DD.md
```

Open the generated markdown file on your phone. It shows:
- Papers with DOI known → exact filename to save as (`10.1016_j.jfineco.2026.001.pdf`)
- Papers without DOI → search by title, download manually

**On campus (OSU library):**
1. Download each PDF
2. Rename to DOI format: `{doi_with_slashes_replaced_by_underscore}.pdf`
3. Copy to `~/ClaudeProjects/QuantResearcher/library/inbox/`

**When you get home:**

```bash
~/ClaudeProjects/QuantResearcher/library/ingest.sh
```

Output shows what was ingested, what landed in `unmatched/`, and what (if anything) failed.
Campus trip list auto-clears for all successfully ingested papers.

---

## 3. Read & Implement

```
read_paper("s2:xxxx")            # loads full text into context (50k chars)
get_related_papers("s2:xxxx")    # find adjacent work before implementing
```

Run the model in the sandbox against your futures/crypto data:

```
run_python("""
import pandas as pd
df = pd.read_parquet('/workspace/data/futures/ES_1D.parquet')
# implement here
""")
```

---

## 4. Log Results

```
add_note("s2:xxxx", "Kyle lambda on MGC: 0.23, Sharpe 1.1 vol-timed. See experiments/2026-03-28-kyle-mgc.md")
tag_paper("s2:xxxx", ["implemented"])
remove_tag("s2:xxxx", ["to-implement"])
```

### Experiment Recording — Preferred Path (experiment-mcp)

Use `log_experiment()` via the experiment-mcp tool. Results are stored in `research.db`, indexed in ChromaDB, and queryable via `search_experiments()` and `experiment_stats()`.

```
run_python("""...""")
log_sandbox_result(
    title="Kyle Lambda on MGC",
    hypothesis="Kyle lambda predicts short-term price impact on MGC",
    conclusion="Lambda: 0.23. Sharpe 1.1 (vol-timed entry). Not significant vs. baseline.",
    experiment_type="signal_research",
    paper_id="s2:xxxx"
)
# Review the pre-filled payload, then:
log_experiment(
    title="Kyle Lambda on MGC",
    dataset="MGC_continuous_1H 2024-01-01 to 2026-03-28",
    hypothesis="...",
    code="...",
    results={"sharpe": 1.1, "kyle_lambda": 0.23},
    conclusion="...",
    experiment_type="signal_research",
    paper_id="s2:xxxx",
    tags=["microstructure", "price-impact"]
)
```

### Experiment Recording — Legacy Path (manual markdown)

Write to `research/experiments/YYYY-MM-DD-<slug>.md`. Not machine-queryable — use only when the MCP tool is unavailable.

```markdown
# Experiment: Kyle Lambda on MGC

**Date:** 2026-03-28
**Paper:** s2:xxxx — Kyle (1985)

## Result
Kyle lambda: 0.23. Sharpe 1.1 (vol-timed entry). Not significant vs. baseline.

## Conclusion
Inconclusive. Try conditioning on order flow imbalance.
```

---

## Weekly Maintenance

The nougat equation upgrade runs automatically every Sunday at 2 AM (once launchd is loaded):

```bash
# Load once:
cp ~/ClaudeProjects/QuantResearcher/jobs/com.quantresearcher.nougat.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.quantresearcher.nougat.plist

# Or trigger manually:
~/ClaudeProjects/QuantResearcher/jobs/nougat_upgrade.sh
```

Papers upgraded to nougat extraction show `text_extractor: "nougat"` in `get_paper_metadata()`.
Papers with `nougat-low-confidence` have > 10 `[MISSING]` markers — verify equations before using.

---

## Quick Reference

| Situation | Tool |
|-----------|------|
| Exploring a new area | `search_papers` → `read_abstract` → `bookmark_paper` |
| Check if paper is worth fetching | `get_paper_metadata` |
| See what needs downloading | `list_needed()` or `export_campus_list()` |
| Paper dropped in inbox | `ingest.sh` or `ingest_folder()` |
| Find papers like one you like | `get_related_papers` |
| Browse by topic | `search_by_tag(["microstructure"])` |
| Prioritize reading | `reading_list()` — to-read, citation-sorted |
| Generate citation | `cite("s2:xxxx", "bibtex")` |
