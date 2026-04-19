# Agent User Manual — QuantWorkstation

Index and system reference. Each agent has its own doc in `docs/agents/`.

---

## System Map

```
You (Guiding Researcher)
  │
  ├── research-navigator   ← session orchestrator; reads graph, synthesizes direction
  │     │
  │     ├── spawns → trial-engineer   (hypothesis → code → metrics)
  │     └── gates  → quant-strategist (available only after OOS champion confirmed)
  │
  ├── quant-strategist     ← on-demand alpha ideation; outputs research/ideas/ files
  │
  ├── learning-companion   ← quant theory tutor; tracks your depth across gap topics
  │
  └── qws_researcher       ← literature pipeline; fetch → store → extract → markdown
                              (lives in private sibling: ~/ClaudeProjects/QuantWorkstation-private/qws_researcher/)
```

You decide at every handoff. No agent promotes, retires, or acts on results without
your explicit instruction.

---

## Agents

| Agent | Model | Doc | When to Use |
|---|---|---|---|
| research-navigator | Opus 4.6 | [research-navigator.md](agents/research-navigator.md) | Every session — start, mid-pivot, wrap |
| trial-engineer | Sonnet 4.6 | [trial-engineer.md](agents/trial-engineer.md) | After direction is chosen; needs hypothesis_id |
| quant-strategist | Opus 4.6 | `~/ClaudeProjects/QuantWorkstation-private/docs/agents/quant-strategist.md` | After OOS champion confirmed; idea generation (private) |
| learning-companion | Sonnet 4.6 | [learning-companion.md](agents/learning-companion.md) | Any time; quant theory questions |
| literature pipeline | — (CLI) | `~/ClaudeProjects/QuantWorkstation-private/docs/agents/literature-pipeline.md` | After downloading papers; feed strategist (private) |

---

## Guard Boundaries (OS-enforced)

| Action | navigator | trial-engineer | quant-strategist |
|---|---|---|---|
| `qw query` | Yes | Yes (context only) | No |
| `qw record --hypothesis` | Yes | No | No |
| `qw record --bundle` | No | Yes (after "run it") | No |
| `qw champion / abort / retire` | No | No | No |
| Write `research/ideas/` | Yes | No | Yes |
| Write `research/trials/` | No | Yes | No |
| Write `execution/` | No | No | No |
| Execute trial scripts | No | Yes (after "run it") | No |
| `git commit / push` | No | No | No |

---

## File Locations

| Purpose | Path |
|---|---|
| Session notes | `research/ideas/session_YYYY-MM-DD.md` |
| Raw idea seeds | `research/ideas/YYYY-MM-DD-<slug>.md` |
| Trial scripts | `research/trials/<asset>/<strategy>/NN_description.py` |
| Trial results | `research/results/<asset>/<strategy>/runs/<timestamp>/` |
| Paper extracts | `~/ClaudeProjects/QuantWorkstation-private/qws_researcher/data/extracts/<paper_id>.md` |
| Navigator memory | `.claude/agent-memory/research-navigator/` |
| Research standards | `research/experiments/standards.py` |
| Strategy interface | `strategies/base.py` |

---

## First Session from Cold Start

1. **Ingest papers** (optional — do before first strategist session; pipeline lives in private sibling):
   ```bash
   cd ~/ClaudeProjects/QuantWorkstation-private
   python -m qws_researcher.ingest arxiv:<id>
   python -m qws_researcher.batch_extract --data-dir qws_researcher/data --limit 5
   ```

2. **Navigator Phase 1** — session start:
   ```
   /research-session
   Phase 1: session start
   ```

3. **Navigator Phase 2** — log a baseline hypothesis:
   ```
   Navigator: I want to establish a BTC 1H baseline — simple momentum, no filters
   ```

4. **Trial-engineer** — generate the trial:
   ```
   Use the trial-engineer agent.
   hypothesis_id: <from Phase 2>
   instrument: BTC/USD
   timeframe: 1H
   trial_type: baseline
   strategy_class: momentum
   entry_logic: long when close > 20-period high; short when close < 20-period low
   exit_logic: exit on opposite signal; hard stop 2 ATR from entry
   ```

5. **Review. Run:**
   ```
   run it
   ```

6. **Navigator Phase 3** — pivot analysis:
   ```
   Navigator: research/results/crypto/momentum/runs/<timestamp>/
   ```

7. **Navigator Phase 4** — wrap:
   ```
   Navigator, wrap up. Hypothesis <id>. Outcome: <verdict>. Finding: <one sentence>.
   ```

After a confirmed OOS champion, quant-strategist unlocks.
