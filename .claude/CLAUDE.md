# QuantWorkstation — Claude Code Context

## Research Context

Personal systematic trading research exocortex. Graph (Neo4j + `qw` CLI + MCP) is the
shared brain. Any model with MCP access reads the same research history.

| Need | Document |
|---|---|
| Mission, targets, philosophy | `docs/MANIFESTO.md` |
| Graph schema, MCP tools, provenance chain | `docs/PROVENANCE_ENGINE.md` |
| Research loop, interaction rules | `docs/RESEARCH_WORKFLOW.md` |
| Current sprint, what's built vs. planned | `docs/BACKLOG_ALIGNMENT.md` |

**Always-active constraints:**
- Sharpe ≥ 2.0 | Holding ≤ 4h | Optimize for alpha — not win rate
- Interface is `qw` CLI + MCP only — no FastAPI
- Before suggesting a strategy: `qw query --name recent_champions` + `qw query --name list_aborted`
- Do NOT use nodes/tools marked `[TARGET]` in `PROVENANCE_ENGINE.md` until their story is COMPLETE in `BACKLOG_ALIGNMENT.md`
- **Current sprint:** Epic 4 — ~~QWS-0402~~ → ~~QWS-0407~~ → QWS-0406 → QWS-0405

---

## Modules

| Path | Purpose |
|------|---------|
| `data/config.py` | All env vars (pydantic-settings `Settings`) |
| `data/store.py` | ArcticDB entry point; `read_bars()`/`write_bars()`/`write_signals()`. Libs: `crypto`(`BTC/USD_1H`), `futures`(`ES_continuous_1H`, Panama-adj), `futures_meta`(`{root}_contracts`), `signals`(`{strategy}_{symbol}_{tf}`) |
| `data/collectors/alpaca_crypto.py` | Crypto OHLCV via REST (7 timeframes, 2yr init) |
| `data/collectors/ibkr_futures.py` | Futures OHLCV via ib_insync; `_CONTRACT_SPECS` to add symbols |
| `execution/oms.py` | Target notionals → Orders via RiskEngine |
| `execution/risk.py` | 8 prop-firm rules; TradingState machine |
| `strategies/base.py` | `generate_signals() → pd.Series` of {-1,0,1}; pandas-only; adapters in `strategies/adapters/` own vectorbt/backtrader |
| `research/experiments/` | sweep, walk_forward, evaluator, metrics, standards |
| `research/trials/` | Numbered trial scripts (`NN_description.py`) |

## Hard rules
1. **Destructive scripts** — `util/reseed_symbol.py`, `util/reseed_all_stitched.py`, `util/deleteData.py` delete and rewrite ArcticDB symbols. Confirm symbol and timeframe before running.
2. **No direct lib writes** — always go through `store.write_bars()` / `store.write_signals()`.
3. **Paper by default** — `alpaca_base_url=https://paper-api.alpaca.markets`, `ibkr_port=4002`. Verify `.env` before any live change.
4. **Risk constants are fixed** — 5% daily loss, 10% trailing DD, 5% per-symbol, 40% total exposure. Do not change without explicit instruction.
5. **Trial filenames are permanent** — `NN_description.py`; results reference by filename; do not renumber.
6. **Tests use mock brokers only** — no live connections in `tests/unit/`.
7. **No auto-commit** — never `git commit` or `git push` without explicit instruction.

## Quick reference
```bash
pip install -e ".[dev]"          # install
ruff check . && mypy --strict .  # lint + type check
pytest tests/unit/ -v            # tests
python -m data.collectors.alpaca_crypto    # collect crypto (no gateway)
python -m data.collectors.ibkr_futures    # collect futures (IB Gateway required)
python util/inspectDb.py                  # inspect ArcticDB
python research/runner.py                 # run a research trial
```
