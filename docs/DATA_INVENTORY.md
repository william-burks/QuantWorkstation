# Data Inventory

Last updated: 2026-04-16

---

## Futures (`futures` ArcticDB lib)

### Tier 1 — Databento GLBX.MDP3 (7yr, 11 timeframes)

| Symbol | Description | Range |
|--------|-------------|-------|
| ES | S&P 500 | 2019-01-01 → current |
| NQ | Nasdaq 100 | 2019-01-01 → current |
| CL | Crude Oil WTI | 2019-01-01 → current |
| GC | Gold | 2019-01-01 → current |
| ZN | 10yr Treasury Note | 2019-01-01 → current |
| RTY | Russell 2000 | 2019-01-01 → current |
| 6E | Euro FX | 2019-01-01 → current |
| NG | Natural Gas | 2019-01-01 → current |
| ZB | 30yr Treasury Bond | 2019-01-01 → current |
| SI | Silver | 2019-01-01 → current |
| HG | Copper | 2019-01-01 → current |
| 6J | Japanese Yen | 2019-01-01 → current |
| 6B | British Pound | 2019-01-01 → current |

Timeframes: `5min, 10min, 15min, 30min, 1H, 2H, 4H, 8H, 1D, 1W, 1M`

Key pattern: `{SYM}_{tf}` for intraday (e.g. `ES_5min`, `ES_1H`), `{SYM}_contfut_{tf}` for daily+ (e.g. `ES_contfut_1D`)

Covers: 2019 low-vol bull, 2020 COVID crash + V-recovery, 2021 bull, 2022 rate hike cycle, 2023-2024 normalization, 2025-2026 current regime. Extended to 2019-01-01 via GLBX-20260416-W99LWYHNVP (2026-04-16).

### Tier 2 — IBKR only (~1yr, 5min + 10min only)

MES, MNQ, MGC, M2K, MBT, DX, ZC, ZS, Z

Suitable for recent-regime tests only. Not viable for multi-year walk-forward studies.

---

## Crypto (`crypto` ArcticDB lib)

| Symbol | Source | Depth | Timeframes |
|--------|--------|-------|------------|
| BTC/USD | Coinbase (via ingest_coinbase_crypto.py) | 7yr (2019-01-01 → current) | 1min, 5min, 10min, 15min, 30min, 1H, 2H, 4H, 8H, 1D, 1W, 1M |
| ETH/USD | Coinbase (via ingest_coinbase_crypto.py) | 7yr (2019-01-01 → current) | 1min, 5min, 10min, 15min, 30min, 1H, 2H, 4H, 8H, 1D, 1W, 1M |

Key pattern: `{PAIR}_{tf}` (e.g. `BTC/USD_1H`, `BTC/USD_5min`)

Note: Legacy Alpaca T-suffix keys deleted. Coinbase keys are the only source.

---

## Macro (`macro` ArcticDB lib, 189 series)

| Category | Series | Depth |
|----------|--------|-------|
| FRED — yield curve | DGS2, DGS10, T10Y2Y | 1976+ |
| FRED — vol/credit | VIXCLS, BAMLH0A0HYM2 | 1990+, 1996+ |
| FRED — inflation | T5YIE, T10YIE, DFII10, PCEPILFE | 2003+ |
| FRED — labor/activity | ICSA, RSAFS | 1967+, 1992+ |
| FRED ALFRED releases | CPIAUCSL, CPILFESL, PCEPILFE, PAYEMS, UNRATE, ICSA, RSAFS — key `{ID}_release_1D` | 2019+ |
| FRED — financial stress | STLFSI4 | 1993+ |
| EIA — petroleum | WCRSTUS1, WCSSTUS1, WGTSTUS1, WDISTUS1 | 1982-1990+ |
| EIA — degree days | ZWHDPUS, ZWCDPUS (monthly) | 1973+ |
| Baker Hughes NA | US total/oil/gas rigs, Canada rigs (weekly) | 2013+ |
| Baker Hughes WW | Total, Intl, NA, US, Canada, LatAm, Europe, Africa, MidEast, APAC (monthly) | 2013+ |
| Baker Hughes state | TX, NM, ND, LA, OK, PA, WV, WY, CO (weekly) | 2000-01-07 → 2026-04-10 |
| CFTC COT | ES, NQ, CL, GC, ZN, ZB, 6E (disaggregated, weekly) | 2010-07-20+ (~16yr) |
| CFTC COT | MGC (disaggregated, weekly) | 2020-12-01+ (contract launched 2020) |
| USDA NASS | Corn + soybean crop progress, 5 states + national (weekly, seasonal) | 2019+ |
| Google Trends | buy gold, gold inflation hedge, recession, inflation (weekly) | 2019+ |
| Earnings surprises | FMP quarterly earnings beats/misses | 1985+ |
| Insider trades | FMP (2025+) + SEC EDGAR Form 4 (via ingest_sec_insider.py) | 2006+ |
| Treasury rates | FMP full curve (weekly) | 2019+ |
| BDTI | Baltic Dirty Tanker Index (daily) | 2016+ |
| Economic calendar | FOMC, NFP, CPI, etc. (`calendar` lib) — upcoming events + blackout flags only. For historical actuals see FRED ALFRED rows above. | rolling 5 weeks |

**ML feature construction note:**
- `_release_1D` keys (ALFRED): index = release date. Use `asof` join — `series.reindex(bar_index, method="ffill")`. No look-ahead bias.
- All other FRED/market series (yields, VIX, spreads): daily market data, no revision risk, safe to join directly.
- Do NOT use `PCEPILFE_1D`, `ICSA_1D`, `RSAFS_1D` (revised values) for ML features — use the `_release_1D` equivalents.

---

## Signals (`signals` ArcticDB lib)

Empty — populated during research trials.
Key pattern: `{strategy}_{symbol}_{tf}`

---

## Refresh cadence

| Source | How to refresh | Frequency |
|--------|---------------|-----------|
| Futures Tier 1 | `python -m data.collectors.ibkr_futures` (IB Gateway required) | Monthly |
| Crypto | `python util/ingest_coinbase_crypto.py` | Monthly |
| FRED / EIA / BHI | `python -m data.collectors.fred` / `eia` / `baker_hughes` | Weekly |
| COT | `python -m data.collectors.cot` | Weekly (Fridays) |
| USDA | `python -m data.collectors.usda_nass` | Weekly (in-season) |

Databento data ends 2026-04-13. IBKR incremental runs extend from that date forward.
