# Data Collectors

Batch collectors for crypto (Alpaca) and futures (IBKR) OHLCV data, stored in arcticdb.

---

## Prerequisites

**1. Install dependencies**
```bash
cd ~/ClaudeProjects/QuantWorkstation
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

**2. Create your `.env`**
```bash
cp env.example .env
# Fill in ALPACA_API_KEY and ALPACA_API_SECRET at minimum
```

**3. For futures only — start IB Gateway**

Open IB Gateway (paper account), enable API connections:
- Configure → API → Settings → Enable ActiveX and Socket Clients ✓
- Socket port: `4002` (paper) or `4001` (live)
- Trusted IPs: `127.0.0.1`

---

## Running the Collectors

### Crypto (Alpaca)

No external process required — just valid API keys in `.env`.

```bash
# From repo root, with .venv active
python3 - <<'EOF'
from data.collectors.alpaca_crypto import collect, collect_all

# Single symbol, single timeframe
collect("BTC/USD", "daily")
collect("ETH/USD", "hourly")

# All configured symbols (BTC/USD, ETH/USD, SOL/USD by default)
collect_all("daily")
EOF
```

Available timeframes: `1-minute`, `5-minute`, `15-minute`, `hourly`, `4-hour`, `daily`, `weekly`

First run fetches 2 years of history. Subsequent runs are incremental.

### Futures (IBKR)

Requires IB Gateway running before calling collect.

```bash
python3 - <<'EOF'
from data.collectors.ibkr_futures import collect, collect_all

# Single root
collect("ES", "daily")

# All configured roots (ES, NQ, CL, GC by default)
collect_all("daily")
EOF
```

Available timeframes: `daily`, `hourly`

First run fetches 1 year of history (IBKR limit). Subsequent runs are incremental.

---

## Verifying Data Was Stored

```bash
python3 - <<'EOF'
from data.store import get_store
import os; os.environ.setdefault("ARCTIC_URI", "lmdb:///data/arctic")

store = get_store()

# List what's in each library
print("Crypto symbols:", store.list_symbols("crypto"))
print("Futures symbols:", store.list_symbols("futures"))

# Read and inspect a symbol
df = store.read_bars("crypto", "BTC/USD_daily")
print(df.tail())
print(f"\n{len(df)} bars, {df.index.min()} → {df.index.max()}")
EOF
```

---

## Running the Tests

Unit tests use mocked API clients — no live connections required.

```bash
# All unit tests
pytest tests/unit/ -v

# Collectors only
pytest tests/unit/test_alpaca_crypto_collector.py -v
pytest tests/unit/test_ibkr_futures_collector.py -v

# Roll calendar
pytest tests/unit/test_roll_calendar.py -v

# Schemas
pytest tests/unit/test_schemas.py tests/unit/test_schemas_quote.py -v
```

Expected output: **35 passed**.

---

## Troubleshooting

**`ValidationError: alpaca_api_key field required`**
→ `.env` file is missing or not loaded. Make sure it's in the repo root and contains `ALPACA_API_KEY`.

**`ConnectionRefusedError` on IBKR collect**
→ IB Gateway is not running, or the port doesn't match `IBKR_PORT` in `.env` (default `4002` for paper).

**`KeyError: 'BTC/USD'` from Alpaca response**
→ No data returned for that symbol/timeframe. Check the symbol spelling — Alpaca uses `BTC/USD` not `BTCUSD`.

**`ValueError: Unknown futures root`**
→ Symbol not in `_CONTRACT_SPECS`. Add it to `ibkr_futures.py` and to `futures_symbols` in `.env`.

---

## Adding a New Futures Symbol

1. Add to `_CONTRACT_SPECS` in `ibkr_futures.py`:
```python
"MES": {"multiplier": "5", "exchange": "CME", "currency": "USD"},
```
2. Add to `FUTURES_SYMBOLS` in `.env` (or update the default in `data/config.py`):
```bash
FUTURES_SYMBOLS=["ES","NQ","CL","GC","MES"]
```
