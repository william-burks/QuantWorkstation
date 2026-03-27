# Data Collectors

Batch collectors for crypto and futures OHLCV data. All data is written to arcticdb.

---

## Collectors

### `alpaca_crypto.py`
Fetches crypto bars from Alpaca Markets.

**Symbols:** configured via `CRYPTO_SYMBOLS` env var (default: `BTC/USD`, `ETH/USD`, `SOL/USD`)

**Timeframes:**

| Key | Resolution |
|---|---|
| `1-minute` | 1 min |
| `5-minute` | 5 min |
| `15-minute` | 15 min |
| `hourly` | 1 hour |
| `4-hour` | 4 hours |
| `daily` | 1 day |
| `weekly` | 1 week |

**arcticdb keys:** `crypto / {symbol}_{timeframe}` (e.g. `BTC/USD_daily`)

**Behavior:**
- First run: fetches 2 years of history
- Subsequent runs: incremental from last stored timestamp
- Skips if last bar is within the past hour (already current)

**Requires:** `ALPACA_API_KEY`, `ALPACA_API_SECRET`

```python
from data.collectors.alpaca_crypto import collect, collect_all

collect("BTC/USD", "daily")       # single symbol
collect("ETH/USD", "hourly")
collect_all("daily")              # all configured symbols
```

---

### `ibkr_futures.py`
Fetches futures daily bars from IBKR via `ib_insync`.

**Supported roots:**

| Symbol | Exchange | Multiplier |
|---|---|---|
| `ES` | CME | $50/pt |
| `NQ` | CME | $20/pt |
| `CL` | NYMEX | $1,000/contract |
| `GC` | COMEX | $100/troy oz |

**Timeframes:** `daily`, `hourly`

**arcticdb keys:** `futures / {root}_continuous_{timeframe}` (e.g. `ES_continuous_daily`)

**Behavior:**
- Fetches front-month contract bars
- First run: 1-year history (IBKR limit)
- Subsequent runs: incremental from last stored timestamp
- Deduplicates: bars at or before last stored timestamp are discarded
- Always disconnects from IB Gateway, even on error

**Requires:** IB Gateway or TWS running locally on `IBKR_HOST:IBKR_PORT` (default `127.0.0.1:4002` for paper)

```python
from data.collectors.ibkr_futures import collect, collect_all

collect("ES", "daily")    # single root
collect_all("daily")      # all configured roots
```

---

### `roll_calendar.py`
Builds Panama-adjusted continuous price series from individual contract bars.

**Panama method:** at each roll, prior prices are multiplied by `(new_front_close / old_front_close)`. Percentage returns are preserved; prices are not actual tradeable prices.

**Roll timing:** 5 business days before contract expiry.

```python
from data.collectors.roll_calendar import build_continuous

# contracts: DataFrame with [expiry, front_month] columns
# bars_by_expiry: dict mapping expiry date → OHLCV DataFrame
continuous_df = build_continuous("ES", contracts, bars_by_expiry)
```

---

## arcticdb Libraries

| Library | Contents | Key format |
|---|---|---|
| `crypto` | Crypto OHLCV bars | `{symbol}_{timeframe}` |
| `futures` | Futures continuous bars | `{root}_continuous_{timeframe}` |
| `futures_meta` | Contract metadata | `{root}` |
| `signals` | Strategy signals | `{strategy}/{symbol}` |

---

## Scheduling

Collectors are run as APScheduler jobs (configured in `execution/scheduler.py`):

| Job | Schedule | Notes |
|---|---|---|
| Crypto daily | 00:15 UTC daily | After midnight close |
| Futures daily | 23:15 UTC Mon–Fri | After CME close (17:15 CT) |

For intraday timeframes (hourly, 15-min), adjust the schedule accordingly.

---

## Adding a New Futures Symbol

1. Add an entry to `_CONTRACT_SPECS` in `ibkr_futures.py`:
```python
"MES": {"multiplier": "5", "exchange": "CME", "currency": "USD"},
```
2. Add the root to `futures_symbols` in your `.env` or `data/config.py` defaults.
3. No other changes required.
