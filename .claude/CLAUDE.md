# QuantWorkstation — Claude Code Context

## What this is
Trading workbench for crypto (Alpaca REST) and futures (IBKR via ib_insync). Manual research-to-execution boundary; paper trading by default.

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

## Strategies
- `ema_crossover.py` — EMA crossover with RSI filter
- `mars.py` — momentum + SMA trend + ATR screen
- `rsi_reversion.py` — RSI/Bollinger reversion, max 6-bar hold
- `dual_tf_trend.py` — dual timeframe trend following

## Hard rules
1. **Destructive scripts** — `util/reseed_symbol.py`, `util/reseed_all_stitched.py`, `util/deleteData.py` delete and rewrite ArcticDB symbols. Confirm symbol and timeframe before running.
2. **No direct lib writes** — always go through `store.write_bars()` / `store.write_signals()`.
3. **Paper by default** — `alpaca_base_url=https://paper-api.alpaca.markets`, `ibkr_port=4002`. Verify `.env` before any live change.
4. **`DRAWDOWN_HALT` requires restart** — does not auto-lift. `DAILY_LOSS_HALT` resets at 00:00 UTC via `reset_day()`.
5. **Risk constants are fixed** — 5% daily loss, 10% trailing DD, 5% per-symbol, 40% total exposure. Do not change without explicit instruction.
6. **Trial filenames are permanent** — `NN_description.py`; results reference by filename; do not renumber.
7. **Tests use mock brokers only** — no live connections in `tests/unit/`.
8. **No auto-commit** — never `git commit` or `git push` without explicit instruction.

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
