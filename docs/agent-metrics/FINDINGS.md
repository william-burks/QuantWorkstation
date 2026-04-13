# Agent Performance Findings

Cumulative analysis across epics. Each section documents what changed, what patterns emerged, and what to build on. Raw data lives in `qa_runs.csv` and `lead_engineer_runs.csv`.

---

## Epic 9HF — Baseline Behavior Under Load

**Epics covered:** QWS-HF-001 (hypothesis fast-follow), QWS-0904

### Lead-Engineer
| Run | Calls | Waste % | Top Pattern | Verdict |
|-----|-------|---------|-------------|---------|
| QWS-HF-001 R1 | 78 | 51% | post-stop-rampage | COMPLETED-OVERRUN |
| QWS-HF-001 R2 | 54 | 35% | grep-storm | completed |
| QWS-HF-001 R3 | 34 | 21% | file-reread | TESTING |
| QWS-0904 R1 | 47 | 23% | file-reread | TESTING |
| QWS-0904 R2 | 68 | 37% | file-reread | TESTING |
| QWS-0904 R3 | 53 | 30% | grep-storm | TESTING |

### QA-Engineer
| Run | Calls | Waste % | Top Pattern | Verdict |
|-----|-------|---------|-------------|---------|
| 9HF R1 | 36 | 33% | grep-storm | ISSUES_REMAINING |
| 9HF R2 | 32 | 31% | unlisted-tests | CLEAN |

### Findings
- **post-stop-rampage** is the most destructive pattern: agent hits STOP GATE but continues issuing tool calls (post-gate flailing). Accounted for 40 wasted calls in one run.
- **grep-storm** appears when agent lacks a file anchor — opens broad searches instead of reading known files.
- Multiple retries per story (3x for QWS-HF-001, 3x for QWS-0904) indicates phase gate wasn't reliably armed between attempts. Each retry starts from scratch and accumulates its own waste.
- Lead-engineer waste floor in this era: ~21%. Ceiling: 51%.
- QA waste floor: 31%.

### What changed going into 9.5
- `make prime-agent` hardened to re-arm phase gate on every retry
- Story file `## Status` update added to lead-engineer close sequence (source of TESTING verdicts — close-story was failing on stale status)

---

## Epic 9.5 — First Clean Lead-Engineer Run

**Stories:** QWS-0905 (hypothesis lookup + findings field), QWS-0906, QWS-0907, QWS-0908

### Lead-Engineer
| Run | Calls | Waste % | Top Pattern | Verdict |
|-----|-------|---------|-------------|---------|
| QWS-0905 | 86 | 20% | file-reread | completed |

Only one lead-engineer row recorded (auditor trace coverage gap for QWS-0906–0908).

### QA-Engineer
| Run | Calls | Waste % | Top Pattern | Verdict |
|-----|-------|---------|-------------|---------|
| 9.5 | 45 | 16% | scope-archaeology | CLEAN |

### Findings
- **20% lead-engineer waste** is the lowest recorded single-story score. Previous floor was 21% (QWS-HF-001 R3), and that run still ended TESTING.
- **16% QA waste** is the lowest QA score in the dataset.
- **scope-archaeology** appears for the first time as top pattern — agent is spending calls confirming what's in/out of scope rather than redundantly reading files. This is qualitatively better waste: it's uncertainty about story boundaries, not sloppiness.
- No lint fixlists written. No retries.
- **Gap identified:** lead_engineer_runs.csv wasn't appended for QWS-0906–0908 — auditor trace either wasn't preserved or Step 5c didn't fire. Improvement trend is unmeasured for those stories.

### What changed going into Epic 10
- scope-archaeology flagged as target: "In Scope / Out of Scope" section in story files should be surfaced explicitly in qa-engineer prompt preamble
- lead_engineer_runs.csv coverage gap noted for investigation

---

## Epic 10 — Macro Data (10 Stories)

**Stories:** QWS-1000 through QWS-1009, QWS-1010 (QWS-1005/1006/1011 skipped — MANIFESTO misalignment)

### Lead-Engineer
No rows recorded in lead_engineer_runs.csv for Epic 10 stories. Coverage gap persists.

### QA-Engineer
| Run | Calls | Waste % | Top Pattern | Verdict |
|-----|-------|---------|-------------|---------|
| Epic 10 | 71 | 20% | scope-archaeology | CLEAN |

### Findings
- **Largest single QA run in the dataset** (71 calls) with only 20% waste — the agent handled a 10-story scope cleanly.
- Waste did not scale with scope. This is the key result: prior epics showed waste proportional to complexity; Epic 10 broke that pattern.
- scope-archaeology remains dominant — confirms it's structural to multi-story epics, not a one-time artifact.
- MANIFESTO misalignment (QWS-1005/1006/1011) was caught by the architect validation step before implementation, preventing wasted lead-engineer spawns. Skipping 3 stories rather than building then reverting saved ~3 story-sized runs.
- **Dependency unblocking pattern established:** after QWS-1000 closed, a product-owner batch-update of downstream story files (QWS-1007/1008/1009 still showed BLOCKED) was needed. This is now a reusable pattern.
- **Read guard deadlock observed:** shared `/tmp/agent-read-tracker/` between orchestrator and subagents caused a block on `story_0_store_series_methods.md` (read 2x). Fix: `rm /tmp/agent-read-tracker/<file>` clears the tracker for that file. Document this as a known recovery procedure.

---

## Epic 10b — Commodity Regime Data (4 Stories)

**Stories:** QWS-1005 (NOAA), QWS-1006 (USDA), QWS-1011 (NDVI/AppEEARS), QWS-1013 (Prefect flow)

### Lead-Engineer
No rows recorded in lead_engineer_runs.csv. Coverage gap persists across Epic 10b.

### QA-Engineer
| Run | Calls | Waste % | Top Pattern | Verdict |
|-----|-------|---------|-------------|---------|
| Epic 10b | 40 | 18% | file-discovery | CLEAN |

### Findings
- **file-discovery** replaces scope-archaeology as top pattern — new in this epic. Agent is spending calls locating new files (NOAA/USDA/NDVI collectors are brand-new; no prior reads to cache against).
- 18% waste on 4 new-code stories is strong. file-discovery is lower-severity waste than grep-storm or file-reread: it's one-time orientation cost per new module, not repetitive redundancy.
- AppEEARS REST substitution (replacing rasterio/GDAL/HDF4 for NDVI) was an architect-recommended mid-story pivot. Lead-engineer accepted autonomously. Result: ~100 LOC vs ~400, 41 tests pass, no binary deps. Good example of architect intervention reducing implementation complexity.
- **API Error 500** on QWS-1011 lead-engineer spawn — first spawn failed with internal server error. Re-prime + re-spawn resolved it. Pattern: API errors on spawn are transient; always re-prime guards before retry.

---

## Cross-Epic Trends

### QA-Engineer Waste by Epic

| Epic | Waste % | Top Pattern |
|------|---------|-------------|
| 6 (12-run avg) | ~27% | file-reread / grep-storm |
| 7 | 30% | grep-storm |
| 9HF | 32% | grep-storm |
| **9.5** | **16%** | scope-archaeology |
| **10** | **20%** | scope-archaeology |
| **10b** | **18%** | file-discovery |

**-11pp improvement** from historical baseline to current. Trend is flat-stable in the 16–20% range across 9.5/10/10b — this appears to be the current floor given story complexity.

### Lead-Engineer Waste by Epic

| Epic | Waste % range | Top Pattern |
|------|---------------|-------------|
| 7–8 | 24–59% | lint-loop, file-reread, scope-archaeology |
| 9HF | 21–51% | post-stop-rampage, grep-storm |
| **9.5** | **20%** (1 run) | file-reread |
| 10, 10b | not measured | — |

### Waste Pattern Taxonomy

| Pattern | Severity | Description | Mitigation |
|---------|----------|-------------|------------|
| post-stop-rampage | Critical | Agent continues after STOP GATE | Enforce gate in command file; orchestrator detects and terminates |
| lint-loop | High | Agent re-runs linter repeatedly without fixing | lint-mechanic handoff; don't retry in same session |
| grep-storm | High | Broad unfocused searches, no file anchor | Explicit file paths in story Repo Touchpoints section |
| file-reread | Medium | Re-reads same file 2+ times in one session | Read guard (`/tmp/agent-read-tracker/`) blocks at 2x |
| scope-archaeology | Low-Medium | Calls spent confirming in/out of scope | Surface "In Scope / Out of Scope" in qa-engineer prompt |
| file-discovery | Low | One-time orientation cost on new files | Acceptable on new-module stories; not worth mitigating |
| unlisted-tests | Low | Agent searches for tests that don't exist yet | Note "new test file" in story Repo Touchpoints |

### Measurement Gap

lead_engineer_runs.csv has entries only through Epic 9.5. Epics 10 and 10b produced no rows. The auditor Step 5c fires only when a JSONL trace is present at the expected path. Likely causes:
1. Trace file path changed or was not written during those runs
2. Step 5c was not reached (post-epic QA path differs from per-story audit path)

**Action:** Verify Step 5c trace path in `run-epic.md` matches what lead-engineer actually writes. Until fixed, lead-engineer waste trend is blind for Epics 10+.

---

## Recommendations

1. **Fix lead_engineer_runs.csv coverage** — single highest-value measurement gap. Without it, lead-engineer improvement/regression is invisible.
2. **Scope section in qa-engineer preamble** — add explicit "In Scope" surface to reduce scope-archaeology calls.
3. **Dependency unblock pattern** — after any story with downstream BLOCKED dependents closes, always run a product-owner batch-update before spawning the next lead-engineer. Codify in run-epic.md.
4. **Read guard recovery procedure** — document `rm /tmp/agent-read-tracker/<filename>` as the standard fix for deadlock. Add to run-epic.md troubleshooting section.
5. **Transient API error recovery** — re-prime + re-spawn is the correct response. Do not treat API 500 as a story failure.
