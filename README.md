# QuantWorkstation

End-to-end algo trading workbench: data collection → research → strategy → execution.

**Markets:** Crypto (Alpaca) · Futures (IBKR) — no equities
**Mode:** Paper trading by default. Interface: `qw` CLI + MCP only.

---

## Highlights

- **IS/OOS validation framework** with evidence-weighted significance gating — killed a champion strategy (4.58 IS Sharpe, 32 trades) on OOS regime sensitivity (−12% DD) instead of deploying a false positive. See [docs/PROVENANCE_ENGINE.md](docs/PROVENANCE_ENGINE.md).
- **Research provenance graph** (Neo4j): Hypothesis → Trial → Champion → FormerChampion lineage; every run, parameter set, and promotion gate recorded and queryable.
- **Prop-firm risk engine** enforcing daily-loss, trailing-drawdown, exposure, and consistency rules before every order. See the Risk Engine table below.
- **`qw` CLI + MCP server** as the only research interface. No direct Cypher, no raw Python glue.

---

## Architecture

```
data/           — collectors, schemas, arcticdb store
execution/      — broker clients, OMS, risk engine, scheduler
strategies/     — BaseStrategy ABC, adapters, signal implementations
research/       — trials, experiments (sweep, walk-forward), analytics; `research/graph/` holds the Neo4j CLI/store/MCP
docs/           — manifesto, workflow, provenance spec; `docs/graph/` holds schema + runbook
epics/          — sprint/story backlog
infra/          — deployment scaffolds (docker-compose.neo4j.yml, launchd plists)
scripts/        — one-off ingest/inspection/seed scripts
tests/          — unit, integration, e2e (incl. graph tests)
```

The `qw` CLI entry point lives at `research/graph/cli.py` (installed via `pip install -e .`).
Neo4j lifecycle: `make neo4j-up / neo4j-down / seed`.

Data + research flows:

```
arcticdb → strategy.generate_signals()
         → OMS.rebalance(targets, current_positions)
         → RiskEngine.check_order()
         → broker.submit_order()

research/trials/NN_script.py
         → qw record --bundle <results_dir>
         → Neo4j graph (Trial → Hypothesis → Champion lineage)
         → qw query --name recent_champions
```

### Research Graph

Neo4j tracks the full provenance chain: Hypothesis → Trial → Champion → FormerChampion.
The `qw` CLI is the only interface — no direct Cypher, no FastAPI.

```bash
qw record --hypothesis "<one-line hypothesis statement>"
qw record --bundle research/results/<asset>/<strategy>/runs/<timestamp>/
qw query --name recent_champions
qw query --name queued_hypotheses
```

Schema, MCP tools, and promotion gate logic: [docs/PROVENANCE_ENGINE.md](docs/PROVENANCE_ENGINE.md)

### Research Agents

Two agents assist with research sessions:

| Agent | Role |
|---|---|
| `research-navigator` | Session start: graph screening → ranked shortlist. Redundancy check before hypothesis commit. Mid-session pivot analysis. Session wrap with findings update. |
| `trial-engineer` | Accepts hypothesis input contract, generates trial script + bundle.json, stops before run. After "run it": executes, ingests, reports raw metrics. |

Usage: [docs/AGENT_USER_MANUAL.md](docs/AGENT_USER_MANUAL.md)

---

## Setup

**1. Create virtualenv and install**
```bash
git clone https://github.com/william-burks/QuantWorkstation.git
cd QuantWorkstation
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

**2. Configure environment**
```bash
cp env.example .env
# Edit .env — fill in ALPACA_API_KEY and ALPACA_API_SECRET at minimum
```

**3. Futures only — start IB Gateway**

Open IB Gateway (paper account):
- Configure → API → Settings → Enable ActiveX and Socket Clients ✓
- Socket port: `4002` (paper) or `4001` (live)
- Trusted IPs: `127.0.0.1`

---

## Runbook

### Inspect stored data

```python
from data.store import get_store

store = get_store()
for sym in store.list_symbols("crypto"):
    df = store.read_bars("crypto", sym)
    print(f"{sym}: {len(df)} bars | {df.index.min()} → {df.index.max()}")
```

### Collect crypto bars manually

```python
from data.collectors.alpaca_crypto import collect, collect_all

collect("BTC/USD", "daily")       # single symbol + timeframe
collect_all("daily")              # all configured symbols
```

Available timeframes: `1-minute` `5-minute` `15-minute` `hourly` `4-hour` `daily` `weekly`

First run fetches 2 years of history. Subsequent runs are incremental from the last stored bar.

### Run the scheduler daemon

Runs data collection at 00:15 UTC daily and a 60s risk heartbeat.

```bash
source .venv/bin/activate
python3 -m execution.scheduler
```

Stop with `Ctrl+C` or `SIGTERM`.

### Check risk engine status

```python
from execution.brokers.alpaca import AlpacaBroker
from execution.risk import RiskEngine
from data.config import get_settings

s = get_settings()
broker = AlpacaBroker()
risk = RiskEngine(eval_profit_target=s.eval_profit_target)

acct = broker.get_account()
risk.seed(acct.equity)
print(risk.get_status())
```

### Execute a manual rebalance

```python
from execution.brokers.alpaca import AlpacaBroker
from execution.oms import OMS
from execution.risk import RiskEngine
from data.config import get_settings

broker = AlpacaBroker()
risk = RiskEngine(eval_profit_target=get_settings().eval_profit_target)

acct = broker.get_account()
risk.seed(acct.equity)

oms = OMS(risk)
orders = oms.rebalance(
    targets={"BTC/USD": 5000.0},      # symbol → target notional USD
    current=broker.get_positions(),
    account_equity=acct.equity,
)

for order in orders:
    broker.submit_order(order)
```

### Delete data from the store

ArcticDB does not support row-level deletes. Read, filter, rewrite:

```python
from data.store import get_store
import pandas as pd

store = get_store()
lib = "crypto"
symbol = "BTC/USD_daily"

df = store.read_bars(lib, symbol)
df = df[df.index != pd.Timestamp("2024-01-15", tz="UTC")]   # drop a row

store._libs[lib].delete(symbol)
store._libs[lib].write(symbol, df)
```

To wipe and start fresh — delete the `arctic_data/` directory. It is recreated automatically on next run.

### Run tests

```bash
make test           # qws_graph unit tests
make test-unit      # legacy tests/unit/ (risk, OMS)
make test-all       # both suites
make verify         # lint + typecheck + both test suites
```

---

## Risk Engine

Prop-firm standard rules enforced before every order:

| Rule | Limit | Behaviour |
|------|-------|-----------|
| Daily loss | 5% of starting day balance | Kill-switch — no orders until UTC midnight |
| Trailing drawdown | 10% from high-water mark | Kill-switch — manual reset required |
| Daily profit ceiling | 2.5% of starting day balance | Stop trading for day |
| Symbol exposure | 5% of account equity | Order notional capped |
| Total exposure | 40% of account equity | Order blocked if cap reached |
| Consistency (best day) | < 30% of `EVAL_PROFIT_TARGET` | Compliance mode — minimum lot sizes |
| Lot size spike | ≤ 2× last-10-trades average | Qty reduced to average |

Risk state resets daily at 00:00 UTC (kill-switch halts lift; drawdown halt requires manual restart).

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALPACA_API_KEY` | — | Required |
| `ALPACA_API_SECRET` | — | Required |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` | Change to live URL for live trading |
| `IBKR_HOST` | `127.0.0.1` | IB Gateway host |
| `IBKR_PORT` | `4002` | `4002`=paper, `4001`=live |
| `ARCTIC_URI` | `lmdb://<project>/arctic_data` | Override to use S3 or a different local path |
| `EVAL_PROFIT_TARGET` | `3000.0` | Evaluation profit goal in USD (used by consistency rule) |
| `RISK_PER_TRADE_PCT` | `0.01` | Fraction of balance risked per trade (0.005–0.01) |
| `CRYPTO_SYMBOLS` | `["BTC/USD"]` | Symbols to collect and trade |

---

## Troubleshooting

**`ValidationError: alpaca_api_key field required`**
→ `.env` is missing or not in the repo root. Run `cp env.example .env` and fill in the keys.

**`OSError: Read-only file system: /data`**
→ `ARCTIC_URI` is set to a root path. Remove it from `.env` to use the local `arctic_data/` default.

**`data={}` from Alpaca collector**
→ API returned no bars. Verify keys are valid and the symbol is spelled correctly (`BTC/USD` not `BTCUSD`).

**`ConnectionRefusedError` on IBKR collect**
→ IB Gateway is not running, or `IBKR_PORT` doesn't match the Gateway socket port.

**`RiskViolation: Trading halted: DRAWDOWN_HALT`**
→ Max drawdown breached. This halt does not lift at midnight — restart the process after investigating.