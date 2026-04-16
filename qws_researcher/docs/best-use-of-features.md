# Best Use of Features

## AI Tips for This Repository

This repo works best with AI when prompts are narrow, file-scoped, and explicit about whether the change belongs in the Next frontend or the FastAPI backend.

### Start With the Right Scope

- For frontend work, treat `next/` as the source of truth.
- For backend or API work, use `src/research_ui/`.
- Avoid asking for repo-wide changes unless you actually want both sides touched.
- Name the route, feature, and exact file or symbol when possible.

Good prompts:

- "Update `features/papers/PapersToolbar.tsx` to add a sort dropdown."
- "Trace why `/guide` fails to load `best-use-of-features.md`."
- "Add a new FastAPI endpoint under `src/research_ui/routes/papers.py` and wire the frontend call in `next/features/papers/usePapers.ts`."

Weak prompts:

- "Improve the app UI."
- "Refactor the architecture."
- "Make papers better."

### Use the AI Snapshot First

Before a larger frontend prompt, generate the snapshot:

```bash
cd next
npm run snapshot:ai
```

Then give the AI:

1. `next/.ai/snapshot.md`
2. Only the files involved in the change
3. A short success condition

Example:

- "Using `next/.ai/snapshot.md`, update the papers route so the toolbar can filter by ingestion status. Only touch `features/papers/*` unless the route entrypoint must change. Keep `app/(research)/papers/page.tsx` thin."

### Mention the Frontend Rules

- Route files in `next/app/(research)/*/page.tsx` should stay thin.
- Business logic belongs in `next/features/*`.
- Prefer `@/features/<feature>` entrypoints over deep imports when practical.
- Do not introduce a top-level `@/features` barrel.

Prompt template:

- "Implement this in `next/` while preserving the current architecture: keep route pages thin, put behavior in `features/*`, and avoid umbrella `@/features` imports."

### Tell the AI Which Side Owns the Change

Frontend-only prompt:

- "Frontend only. Do not modify Python files."

Backend-only prompt:

- "Backend only. Do not modify `next/` files unless you need to document the contract change."

Full-stack prompt:

- "This is a full-stack change: add the endpoint in `src/research_ui/routes/papers.py`, then wire it in `next/features/papers/usePapers.ts` and update the papers UI."

### Ask for File-Bounded Changes

Examples:

- "Limit changes to `features/graph/*` and `types/graph.ts`."
- "Start from `app/(research)/graph/page.tsx`, then inspect `features/graph/GraphPage.tsx`, `useGraph.ts`, and `useGraphD3.ts`."

### End With Success + Validation

Examples:

- "Success: users can sort papers by title and year from the papers toolbar."
- "Success: `/guide` shows the markdown doc without a load error."
- "Run the relevant checks after editing."

Useful checks:

```bash
cd next
npm run check
npm run snapshot:ai
```

### Short Prompt Template

- Scope: frontend / backend / full-stack
- Route or feature:
- Files allowed to change:
- Constraints: keep route thin / use feature entrypoint / no umbrella imports / minimal change
- Success condition:
- Validation:

### Daily AI Workflow

Use this as the default loop for day-to-day frontend work.

#### 1. Refresh context

From the repo root:

```bash
npm --prefix next run snapshot:ai
```

This updates `next/.ai/snapshot.md`.

#### 2. Build a narrow prompt

Give the AI:

1. `next/.ai/snapshot.md`
2. Only the files in scope
3. One clear success condition

Recommended format:

- Scope: frontend / backend / full-stack
- Files allowed to change:
- Constraints:
- Success:
- Validation:

Example:

- "Scope: frontend. Files allowed: `features/papers/*`, `types/paper.ts`. Constraints: keep route files thin, minimal change, no umbrella feature imports. Success: add a sort dropdown to the papers toolbar. Validation: run `npm run check`."

#### 3. Make the change in the right layer

- UI and behavior: `next/features/*`
- Route composition only: `next/app/(research)/*`
- Shared presentation: `next/shared/*`
- Backend/API: `src/research_ui/routes/*.py`

If the task touches structure, repeat the architecture rules in the prompt.

#### 4. Run checks before commit

```bash
cd next
npm run check
npm run snapshot:ai
```

If hooks are enabled, `pre-commit` will refresh and stage `next/.ai/snapshot.md`, and `pre-push`
will run `npm --prefix next run check`.

#### 5. Commit with a reviewable diff

- Keep the change bounded to one feature when possible.
- Review `next/.ai/snapshot.md` if the structure changed.
- Avoid mixing unrelated backend and frontend edits in one commit.

#### 6. Use this fast path for small tasks

```bash
npm --prefix next run snapshot:ai
```

Then prompt the AI with:

- snapshot
- touched files
- success condition
- validation step

A living reference for how to get the most out of each pipeline layer. Add entries as patterns emerge from real usage.

---

## TeX Source Extraction

**What it does:** For arXiv papers, Tier 2 fetches the original `.tar.gz` source from `arxiv.org/e-print/{id}` and extracts raw LaTeX instead of parsing the PDF. Non-arXiv papers fall back to PDF text via pymupdf4llm.

**Why it beats PDF parsing for math:**

PDF-based tools (pymupdf4llm, Nougat) produce Unicode approximations: `∥ψ∥`, `ℓ²(ℤ)`, `=[∼]`. The equation extractor is designed around LaTeX patterns — `$...$`, `\begin{equation}`, `\\[...\\]` — so it extracts almost nothing useful from PDF text of a math-heavy paper. From `.tex` source, the same paper yields clean LaTeX like `\|\psi\|_{L^2(\mathbb{R})} = 1` and named environments with full symbol fidelity.

**The realistic win in this system:**

The most productive use of TeX-extracted equations is not "auto-convert every equation to code." It is a semi-automatic workflow:

1. **Extract equations** via Tier 2 (auto-fetch for arXiv, Upload TeX for others)
2. **Link symbols to local definitions** — resolve what each variable means from surrounding text (abstract, method section)
3. **Generate candidate implementations** for selected formulas — emit Python first, C++ optionally afterward

This works because `.tex` gives you the formula as the author wrote it, not a lossy Unicode approximation. Symbol resolution is the hard part; having the right LaTeX to start from removes one major source of error.

**When to use Upload TeX vs auto-fetch:**

| Situation | Use |
|---|---|
| arXiv paper, any vintage | Tier 2 button (auto-fetches source) |
| Old arXiv paper (pre-2007) | Same — URL-derived path handles `math/0006100` format |
| Non-arXiv paper, TeX source available | Upload TeX button |
| Non-arXiv paper, PDF only | Upload PDF → Tier 2 falls back to PDF extraction |
| Journal paper behind paywall | Upload TeX if author's source available, otherwise PDF |

**Known limitations:**

- Papers authored in AMS-TeX or plain TeX (not LaTeX) will extract fewer equations — the extractor targets LaTeX environments.
- Very old arXiv papers may have a single uncompressed `.tex` file with TCIDATA metadata headers. These are handled but the preamble noise may require post-filtering.
- Multi-file submissions: the three largest `.tex` files are extracted. If the main file `\input`s sub-files, equations in sub-files appear in both — equation-level deduplication handles this.

---

## Brief Generation

**What it does:** Calls `gpt-4o-mini` on the abstract to produce a structured 3-sentence brief: (1) what was studied, (2) what was found, (3) key caveat.

**Best use:** The brief becomes the primary embedding text for semantic search. A good brief is more searchable than a raw abstract because it forces signal-to-noise compression. Run `batch_abstract` after any bulk import before doing semantic searches.

**Regression anchor:** `arxiv:0006100` (wavelets paper) is the canonical non-finance test case. Its `approach=theoretical` and `finding_type=methodological` tags and 3-sentence brief form the regression baseline in `tests/test_wavelets_regression.py`. Any prompt change that breaks this paper's classification is a regression.

---

## Key Objects *(planned — see `docs/spec-key-objects.md`)*

**What it will be:** 3–5 named constructs extracted at Tier 1 cost (abstract only) that anchor equation navigation in Tier 2. Examples: "Cuntz operators Sⱼ", "Fama-MacBeth cross-sectional regression", "GARCH(1,1) variance process".

**The interaction:** Clickable chips in the paper detail panel. Clicking "Cuntz operators" filters the equations section to formulas containing related terms via FTS5 search. Bridges the gap between "I know what this paper is about" (brief) and "I need to find the specific formula" (equations list).

**Best use:** Run batch_abstract (or re-run per paper) after the prompt is updated. Most useful when the equation list has > 20 entries and you know what you're looking for from the brief.

---

## Regime Tags

**What they are:** Nine dimensions extracted from the abstract alongside the brief: `asset_class`, `frequency`, `time_period`, `market_cap`, `market_condition`, `geography`, `data_type`, `approach`, `finding_type`.

**Best use:** Filtering via `find_papers_by_regime` in the MCP or the asset class / frequency dropdowns in the Papers tab. Most useful for narrowing to papers that actually match your experimental setup before reading.

**Honest limitation:** Tags are extracted from the abstract only. A paper titled "US Equity Momentum" that studies international data will be mis-tagged. The brief + manual notes are more reliable for nuanced filtering.

---
