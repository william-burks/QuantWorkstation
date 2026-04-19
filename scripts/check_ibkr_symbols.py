"""
Check IBKR contract validity for all configured futures and index symbols.

Connects to IB Gateway / TWS, runs reqContractDetails for every symbol,
and prints a PASS/FAIL table. Does NOT collect any data.

Usage:
    python scripts/check_ibkr_symbols.py
"""

import sys
from typing import Any

from ib_insync import IB, Contract

from data.collectors.ibkr_futures import _CONTRACT_SPECS, _INDEX_SPECS
from data.config import get_settings


def check_futures(ib: IB) -> list[dict[str, Any]]:
    results = []
    for root, spec in _CONTRACT_SPECS.items():
        c = Contract()
        c.symbol = root
        c.secType = "FUT"
        c.exchange = spec["exchange"]
        c.currency = spec["currency"]
        c.includeExpired = False
        try:
            details = ib.reqContractDetails(c)
            if details and details[0].contract is not None:
                expiry = details[0].contract.lastTradeDateOrContractMonth[:6]
                results.append(
                    {
                        "symbol": root,
                        "type": "FUT",
                        "status": "PASS",
                        "detail": f"{len(details)} contract(s), front={expiry}",
                        "exchange": spec["exchange"],
                        "currency": spec["currency"],
                    }
                )
            else:
                results.append(
                    {
                        "symbol": root,
                        "type": "FUT",
                        "status": "FAIL",
                        "detail": "no contract details returned",
                        "exchange": spec["exchange"],
                        "currency": spec["currency"],
                    }
                )
        except Exception as e:
            results.append(
                {
                    "symbol": root,
                    "type": "FUT",
                    "status": "FAIL",
                    "detail": str(e),
                    "exchange": spec["exchange"],
                    "currency": spec["currency"],
                }
            )
        ib.sleep(0.2)
    return results


def check_indices(ib: IB) -> list[dict[str, Any]]:
    results = []
    for sym, spec in _INDEX_SPECS.items():
        c = Contract()
        c.symbol = sym
        c.secType = "IND"
        c.exchange = spec["exchange"]
        c.currency = spec["currency"]
        try:
            details = ib.reqContractDetails(c)
            if details and details[0].contract is not None:
                results.append(
                    {
                        "symbol": sym,
                        "type": "IND",
                        "status": "PASS",
                        "detail": f"conId={details[0].contract.conId}",
                        "exchange": spec["exchange"],
                        "currency": spec["currency"],
                    }
                )
            else:
                results.append(
                    {
                        "symbol": sym,
                        "type": "IND",
                        "status": "FAIL",
                        "detail": "no contract details returned",
                        "exchange": spec["exchange"],
                        "currency": spec["currency"],
                    }
                )
        except Exception as e:
            results.append(
                {
                    "symbol": sym,
                    "type": "IND",
                    "status": "FAIL",
                    "detail": str(e),
                    "exchange": spec["exchange"],
                    "currency": spec["currency"],
                }
            )
        ib.sleep(0.2)
    return results


def print_table(rows: list[dict[str, Any]]) -> None:
    col_w = {"symbol": 8, "type": 5, "exchange": 8, "currency": 8, "status": 6, "detail": 50}
    header = (
        f"{'SYMBOL':<{col_w['symbol']}}  {'TYPE':<{col_w['type']}}  "
        f"{'EXCHANGE':<{col_w['exchange']}}  {'CCY':<{col_w['currency']}}  "
        f"{'STATUS':<{col_w['status']}}  DETAIL"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        status_str = r["status"]
        line = (
            f"{r['symbol']:<{col_w['symbol']}}  {r['type']:<{col_w['type']}}  "
            f"{r['exchange']:<{col_w['exchange']}}  {r['currency']:<{col_w['currency']}}  "
            f"{status_str:<{col_w['status']}}  {r['detail']}"
        )
        print(line)


def main() -> None:
    s = get_settings()
    ib = IB()  # type: ignore[no-untyped-call]
    print(f"Connecting to {s.ibkr_host}:{s.ibkr_port} clientId={s.ibkr_client_id}...", flush=True)
    ib.connect(s.ibkr_host, s.ibkr_port, clientId=s.ibkr_client_id)

    try:
        print(f"\n=== Futures ({len(_CONTRACT_SPECS)} symbols) ===\n")
        fut_rows = check_futures(ib)
        print_table(fut_rows)

        print(f"\n=== Indices ({len(_INDEX_SPECS)} symbols) ===\n")
        idx_rows = check_indices(ib)
        print_table(idx_rows)

        all_rows = fut_rows + idx_rows
        fails = [r for r in all_rows if r["status"] == "FAIL"]
        total = len(all_rows)
        print(f"\n=== Summary: {total - len(fails)}/{total} PASS, {len(fails)} FAIL ===")
        if fails:
            print("\nFailed symbols:")
            for r in fails:
                print(f"  {r['symbol']} ({r['type']}, {r['exchange']}): {r['detail']}")
            sys.exit(1)

    finally:
        ib.disconnect()  # type: ignore[no-untyped-call]


if __name__ == "__main__":
    main()
