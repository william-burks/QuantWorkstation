# Epic 6 — Research Analytics

## Objective
Move from recording what happened to computing what it means. This epic builds the
analytical layer on top of the graph — tools that use the graph as a data source but
do their computation in Python, plus the one graph-native story that is genuinely
new schema: research hypothesis journaling.

## Why it exists
After Epics 4 and 5, the graph has clean data, OOS outcomes, regime context, and
cross-instrument views. The next bottleneck is answering qualitative research questions:
- Is this champion's performance robust or was it a lucky parameter set?
- If I trade all current champions simultaneously, when do they blow up together?
- What was I thinking when I ran this strategy six months ago?

None of these are graph query problems. They are analytics problems that happen to
use the graph as their data index.

## Architecture note
Stories 2 and 3 in this epic produce Python scripts in `research/`, not `qws_graph/`
modules. The graph provides file paths and metadata; pandas/numpy does the computation.
This is intentional — the graph is the index, not the compute engine.

## Stories
1. `QWS-0601` `story_1_hypothesis_journaling.md` — `:Hypothesis` nodes linked to runs
2. `QWS-0602` `story_2_parameter_stability.md` — Python stability analysis tool
3. `QWS-0603` `story_3_portfolio_correlation.md` — Python portfolio correlation tool

Stories 2 and 3 are independent of Story 1 and of each other.

## Dependencies
- Epic 4 complete (OOS outcomes recorded, champions have `oos_status`).
- Epic 5 QWS-0501 (family_id) before Story 2 can group by strategy family.
- No hard dependency on Epic 5 QWS-0502 (regime) though Story 2 benefits from it.

## Exit Criteria
- A hypothesis can be recorded with `qw record --hypothesis` and linked to ≥1 Run nodes.
- `research/experiments/stability.py` classifies a champion's parameter set as
  robust or brittle given its grid sweep neighbors.
- `research/analytics/portfolio_correlation.py` outputs a correlation matrix for all
  current OOS-pass champions given their artifact CSV paths.
