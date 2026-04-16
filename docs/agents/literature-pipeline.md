# Literature Pipeline (qws_researcher)

**Not an agent** — a CLI-driven pipeline. Feeds the extract library that quant-strategist reads.

---

## Pipeline Steps

```
ingest → store → extract_structured → data/extracts/*.md
```

Quant-strategist reads `qws_researcher/data/extracts/` directly. Run extraction after ingesting
new papers; the next strategist session picks them up automatically.

---

## Step 1 — Ingest Papers

```bash
# Single paper by arXiv ID
python -m qws_researcher.ingest arxiv:<arxiv-id>

# Batch from ID list
python qws_researcher/ingest_library.sh
```

Papers land in `qws_researcher/data/papers/` (PDF) and `qws_researcher/data/ingested/`.

---

## Step 2 — Extract Structured Fields

```bash
# Extract one paper
python -m qws_researcher.extract_structured <paper_id>

# Batch extract all unprocessed (uses Claude Haiku, skips existing)
python -m qws_researcher.batch_extract --data-dir qws_researcher/data --limit 20
```

Each extract writes `qws_researcher/data/extracts/<paper_id>.md` with frontmatter:

```yaml
---
signal_type: momentum | mean-reversion | regime | volatility | cross-sectional | ...
instrument_class: crypto | futures | equity | multi-asset
timeframe: intraday | daily | weekly
key_finding: <one sentence>
sample_period: <date range>
failure_mode: <what breaks it>
replicated: yes | no | unknown
confidence: high | medium | low
---

[full structured extract body]
```

---

## Step 3 — Search

```bash
# Semantic search
python -m qws_researcher.server query "momentum decay after crowding" --limit 5

# Filter by instrument class
python -m qws_researcher.server query "volatility breakout" --filter instrument_class=futures
```

---

## Data Locations (all gitignored)

| Path | Contents |
|---|---|
| `qws_researcher/data/papers/` | Downloaded PDFs |
| `qws_researcher/data/text/` | Extracted plain text |
| `qws_researcher/data/extracts/` | Structured markdown extracts |
| `qws_researcher/data/research.db` | SQLite paper store |
| `qws_researcher/data/chroma/` | ChromaDB vector index |

---

## Getting Papers

arXiv papers can be fetched directly by ID. For papers behind paywalls (journal articles,
most SSRN), download the PDF manually and place it in `qws_researcher/data/inbox/` —
the ingest pipeline picks up files there.

University library access is the primary source for paywalled content.
