# Data Sources

## arXiv

- **What:** Preprints in quantitative finance, statistics, machine learning, physics
- **Best for:** HAR models, realized volatility, ML methods, econophysics
- **Coverage:** Free, open access, full PDF always available
- **Rate limit:** No key required; be polite
- **Categories useful for quant:** `q-fin.ST` (statistical finance), `q-fin.TR` (trading), `stat.ML`, `econ.EM`

## Semantic Scholar (S2)

- **What:** Broad academic coverage with citation data and OA PDF links
- **Best for:** Finding high-citation papers, citation networks, recommendations
- **Coverage:** Finance, economics, mathematics, statistics, physics
- **Rate limit:** 100 req/hour unauthenticated; ~10x higher with API key
- **Env var:** `SEMANTIC_SCHOLAR_API_KEY` (optional but recommended)
- **Notes:** Uses bulk search endpoint (`/graph/v1/paper/search/bulk`). 1.1s sleep between calls.

## PubMed

- **What:** Biomedical literature — narrow use for quant finance
- **Best for:** Econophysics crossover papers
- **Coverage:** Only useful with econophysics filter appended automatically
- **Rate limit:** No key required for modest usage
- **Env var:** None

## Unpaywall

- **What:** Finds legal open-access PDF URLs for papers with a DOI
- **Best for:** Fallback when S2 has no OA PDF
- **Coverage:** Author manuscripts, institutional repos, PMC, some publisher OA
- **Rate limit:** Polite use; requires email for identification
- **Env var:** `UNPAYWALL_EMAIL` (required — set to `burks.113@buckeyemail.osu.edu`)
- **Notes:** Most paywalled Elsevier/Wiley finance journals return `is_oa: false`. Very new papers (2025-2026) rarely have DOIs indexed in S2 yet.

## SSRN

- **What:** Social Science Research Network — finance working papers
- **Status:** BLOCKED — Cloudflare bot protection returns 403 on all programmatic access
- **Workaround:** Use `fetch_ssrn(url)` with the direct URL; metadata fetched, PDF download silently fails
- **Manual option:** Download from browser, use `ingest_pdf()` or `ingest_folder()`

## OSU Library (Manual)

- **What:** Full institutional access to Elsevier, Wiley, Taylor & Francis, etc.
- **Access:** Campus network or OSU VPN required
- **Workflow:** See `library/inbox/README.md` — download PDF, name by DOI, run ingest.sh
