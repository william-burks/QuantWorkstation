# Spec: `key_objects` — Named Construct Extraction (Tier 1)

**Status:** Draft
**Scope:** Prompt change, data model, one new API endpoint, UI wiring
**Depends on:** Tier 1 brief extraction (`batch_abstract`, `upload-tex` pipeline), `paper_equations` table populated by Tier 2

---

## Problem

After Tier 2 runs on a paper, the equations panel shows a flat list — often 50–200 entries with no ordering signal. You know from the brief what the paper is about, but you don't know which equations represent the core constructs vs. bookkeeping notation.

`key_objects` is the bridge. It names 3–5 constructs that are central to the paper — extracted at Tier 1 cost (abstract only, no full text) — and makes them clickable anchors that filter the equations panel to relevant formulas.

---

## What `key_objects` Is

A short list of named mathematical or conceptual objects that are central to the paper. Each entry is a human-readable string identifying a construct by name and space/type where applicable.

**Examples by paper type:**

| Paper | `key_objects` |
|---|---|
| Wavelets / Cuntz | `["compactly supported wavelets in L²(ℝ)", "spin vectors in ℂᴺ", "Cuntz operators Sⱼ", "multiresolution scaling function φ"]` |
| Deep learning asset pricing | `["conditional expected return", "IPCA latent factors", "instrumented principal components"]` |
| GARCH volatility | `["GARCH(p,q) variance process", "log-likelihood estimator", "QMLE consistency condition"]` |
| Fama-MacBeth | `["cross-sectional risk premium λ", "time-series beta estimation", "Shanken correction"]` |

**What it is not:**
- Not a keyword list (`["wavelets", "finance", "ML"]`)
- Not a claim list (`["paper finds significant alpha"]`)
- Not exhaustive — 3 items that anchor navigation beats 12 that don't

---

## Data Model

### `Paper` dataclass (`core/research_core/models.py`)

Add field alongside `brief` and `regime_tags`:

```python
key_objects: list[str] | None = None  # Named constructs for equation navigation
```

Add to `to_dict()`:
```python
"key_objects": self.key_objects,
```

Add to `from_dict()`:
```python
key_objects=data.get("key_objects"),
```

---

## Prompt Change

### Location
`tools/research-ui/src/research_ui/routes/intelligence.py` — `EXTRACTION_PROMPT` and `_generate_brief_and_tags()`.

### JSON schema addition

Extend the existing extraction JSON to include `key_objects`:

```json
{
  "brief": "...",
  "regime_tags": { ... },
  "key_objects": [
    "compactly supported wavelets in L²(ℝ)",
    "spin vectors in ℂᴺ",
    "Cuntz operators Sⱼ"
  ]
}
```

### Prompt instructions for `key_objects`

Add after the `regime_tags` rules block:

```
Rules for `key_objects`:
- Return a list of 3 to 5 strings. Never fewer than 1, never more than 5.
- Each string names a mathematical object, operator, space, procedure, or model
  that is central to the paper — something a reader would need to locate in the
  equations to understand the main result.
- Prefer names the authors use in the abstract or introduction, not generic terms.
- Include the ambient space or type where it disambiguates (e.g. "in L²(ℝ)" or
  "ℂᴺ" or "GARCH(1,1)" rather than just "the operator" or "the model").
- For empirical finance papers, name the estimator, test statistic, or signal
  construction (e.g. "Fama-MacBeth cross-sectional regression", "momentum signal
  from 12-1 returns") rather than abstract math objects.
- For purely theoretical or mathematical papers, name the primary objects and
  operators from which the main result is constructed.
- If the abstract gives no named constructs at all, return the 1–3 most
  specific descriptive phrases from the abstract (not generic filler).
- Do NOT return: journal names, author names, dataset names, or evaluation
  metrics that are not the paper's primary focus.
```

### `_generate_brief_and_tags()` change

After validation of `regime_tags`, extract and validate `key_objects`:

```python
raw_objects = result.get("key_objects")
if isinstance(raw_objects, list):
    # Keep strings only, strip whitespace, cap at 5
    result["key_objects"] = [
        s.strip() for s in raw_objects
        if isinstance(s, str) and s.strip()
    ][:5]
else:
    result["key_objects"] = []
```

### Saving

In both `_run_pipeline` (upload flow) and `_run_batch` (batch flow), after setting `paper.brief` and `paper.regime_tags`:

```python
paper.key_objects = extraction.get("key_objects") or []
```

---

## API

### Existing endpoint change: `GET /api/papers/{paper_id}`

`key_objects` is already in `paper.to_dict()` so it flows through automatically once the field is in the model. No endpoint change needed.

### New endpoint: `GET /api/equations/search`

Exposes the existing `store.search_equations()` FTS5 search to the UI.

```
GET /api/equations/search?q={query}&paper_id={optional}
```

**Parameters:**
- `q` — FTS5 query string (e.g. `"Cuntz"`, `"spin vector"`, `"S_j"`)
- `paper_id` — optional, restrict to one paper

**Response:**
```json
[
  {
    "equation_id": "uuid",
    "paper_id": "arxiv:0006100",
    "paper_title": "Compactly supported wavelets...",
    "latex": "S_j^* S_j = I",
    "name": null,
    "role": null
  }
]
```

**Implementation** — add to `papers.py`:

```python
@router.get("/api/equations/search")
async def search_equations(
    q: str,
    paper_id: str | None = None,
    store: ResearchStore = Depends(get_store),
):
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query too short")
    results = await run_in_executor(store.search_equations, q.strip())
    if paper_id:
        results = [r for r in results if r["paper_id"] == paper_id]
    return results
```

---

## UI Wiring

### Detail panel — `key_objects` chips

In `showDetail()`, after the regime tags section:

```javascript
if (paper.key_objects && paper.key_objects.length) {
  const chips = paper.key_objects.map(obj =>
    `<span class="pill key-obj-chip" style="cursor:pointer;"
           onclick="filterEquations(${JSON.stringify(obj)})"
           title="Filter equations by: ${esc(obj)}"
     >${esc(obj)}</span>`
  ).join('');
  sections.push(`<div class="detail-section">
    <h4>Key Objects <span style="color:var(--text-muted);font-size:10px;font-weight:normal;">— click to filter equations</span></h4>
    <div class="tag-list">${chips}</div>
  </div>`);
}
```

### `filterEquations(query)` — client-side first, server fallback

```javascript
async function filterEquations(query) {
  // 1. Filter already-loaded equations in the detail panel in-place
  const paperId = state.selectedPaperId;
  const results = await apiFetch(
    `/api/equations/search?q=${encodeURIComponent(query)}&paper_id=${encodeURIComponent(paperId)}`
  );

  // Replace the equations section with filtered results
  const body = document.getElementById('detail-body');
  const eqSection = body.querySelector('[data-section="equations"]');
  if (!eqSection) return;

  if (!results.length) {
    eqSection.querySelector('.eq-list').innerHTML =
      `<div style="color:var(--text-muted);font-size:11px;">No equations matched "${esc(query)}"</div>`;
    return;
  }

  const items = results.map(eq =>
    `<div class="equation-item"><code>${esc(eq.latex)}</code></div>`
  ).join('');
  eqSection.querySelector('.eq-list').innerHTML = items;
  eqSection.querySelector('h4').textContent = `Equations — filtered: "${query}" (${results.length})`;
}
```

This requires tagging the equations section in `showDetail` with `data-section="equations"` and wrapping equation items in a `.eq-list` div — a small structural change to the existing equations render block.

### Reset

Add a "clear filter" button that re-renders the full paper detail:

```javascript
// In eqSection header after filtering:
`<button onclick="selectPaper('${esc(paperId)}')"
         style="font-size:10px;...">clear</button>`
```

---

## Acceptance Criteria

### Extraction quality

For `arxiv:0006100` (wavelets), `key_objects` must:
- Contain 3–5 items
- Include at least one of: "wavelet", "spin vector", "Cuntz"
- Not include generic strings like "the paper", "the operator", "the method"

For a finance paper (e.g. the Fama-French factor zoo paper), `key_objects` must:
- Name a specific estimator, factor, or procedure (not just "machine learning")

### Regression test additions (`test_wavelets_regression.py`)

```python
def test_key_objects_exist(paper):
    assert paper.key_objects, "key_objects missing — re-run batch_abstract"

def test_key_objects_count(paper):
    assert 1 <= len(paper.key_objects) <= 5

def test_key_objects_mention_core_construct(paper):
    combined = " ".join(paper.key_objects).lower()
    assert any(kw in combined for kw in ["wavelet", "spin", "cuntz", "scaling"]), (
        f"key_objects don't mention any core construct: {paper.key_objects}"
    )
```

### UI

- Clicking a chip with a paper that has Tier 2 equations filters the list
- Clicking a chip with no equations shows "No equations matched" (not an error)
- Clearing the filter restores the full equation list

---

## Out of Scope (this spec)

- Cross-paper equation search from the Guide tab
- Symbol resolution ("what does φ mean in context") — requires nearby text, deferred to Tier 2 click interaction
- Auto-linking `key_objects` to specific equation IDs — requires a second extraction pass against the equations table
- C++ translation of candidate implementations
