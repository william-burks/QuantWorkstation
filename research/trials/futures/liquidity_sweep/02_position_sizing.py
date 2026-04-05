"""Position sizing experiments for the liquidity sweep baseline trades."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.experiments.metrics import summary
from research.trials.futures.liquidity_sweep.position_sizing import evaluate_sizing_modes
from strategies.adapters.liquidity_sweep_adapter import load_data_from_store, run_with_data

CONFIG_OVERRIDES = {
    "target_r": 1.25,
    "max_hold_bars": 24,
    "wick_mode": "exclude_q2",
    "chain_mode": "no_smt_in_chain",
    "partial_exit_r": 0.0,
    "stall_bars": 0,
    "allowed_sessions": ["NY_PRE", "AFTER"],
    "allowed_dir": ["BEAR"],
}

MODE_ROWS = [
    {"label": "fixed_0.25pct", "mode": "fixed", "base_risk": 0.0025},
    {"label": "fixed_0.50pct", "mode": "fixed", "base_risk": 0.0050},
    {"label": "fixed_1.00pct", "mode": "fixed", "base_risk": 0.0100},
    {
        "label": "drawdown_half_at_2pct",
        "mode": "drawdown_scale",
        "base_risk": 0.0100,
        "dd_threshold": 0.02,
        "dd_scale": 0.5,
    },
    {
        "label": "loss_streak_2_half",
        "mode": "loss_streak",
        "base_risk": 0.0100,
        "streak_len": 2,
        "streak_scale": 0.5,
    },
    {"label": "rdist_vol_target", "mode": "rdist_vol_target", "base_risk": 0.0100},
]


def _write_html(results: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if results.empty:
        table = "<p>No valid sizing results.</p>"
    else:
        table = results.to_html(index=False, border=0, classes="table")

    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Liquidity Sweep Position Sizing</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; }}
    .table {{ border-collapse: collapse; width: 100%; }}
    .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    .table th {{ background: #f7f7f7; }}
  </style>
</head>
<body>
  <h1>Position Sizing Comparison</h1>
  <p>Baseline entries/exits are unchanged; only risk per trade policy varies.</p>
  {table}
</body>
</html>
"""
    output_path.write_text(html)


def _write_graph_grid_csv(results: pd.DataFrame, mode_rows: list[dict], trades: pd.DataFrame, output_path: Path) -> bool:
    """Write a qw-compatible grid CSV for graph ingestion."""
    if results.empty:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build per-mode config payloads for traceability in qws_graph.
    mode_lookup = {str(row.get("label", "")): row for row in mode_rows}

    win_rate = float((trades["pnl_r"].astype(float) > 0).mean()) if not trades.empty else 0.0
    gross_profit = float(trades.loc[trades["pnl_r"] > 0, "pnl_r"].sum()) if not trades.empty else 0.0
    gross_loss = float((-trades.loc[trades["pnl_r"] < 0, "pnl_r"].sum())) if not trades.empty else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    total_trades = int(len(trades))

    export = results.copy()
    export["instrument"] = "CL"
    export["timeframe"] = "1H"
    export["direction"] = "bear"
    export["logic_type"] = "liquidity-sweep"
    export["total_trades"] = total_trades
    export["win_rate"] = win_rate
    export["profit_factor"] = profit_factor
    export["max_drawdown"] = export["max_drawdown"].astype(float)
    export["sharpe"] = export["sharpe"].astype(float)
    export["params_json"] = export["label"].astype(str).map(
        lambda lbl: json.dumps(mode_lookup.get(lbl, {"label": lbl}), sort_keys=True)
    )

    keep_cols = [
        "instrument",
        "timeframe",
        "direction",
        "logic_type",
        "label",
        "sharpe",
        "profit_factor",
        "win_rate",
        "max_drawdown",
        "total_trades",
        "params_json",
    ]
    export = export[[c for c in keep_cols if c in export.columns]]
    export.to_csv(output_path, index=False)
    return True


def main() -> None:
    data = load_data_from_store()
    result = run_with_data(data=data, config_overrides=CONFIG_OVERRIDES)
    trades = result.get("trades_df", pd.DataFrame())
    if trades.empty:
        print("No trades from baseline config; cannot run sizing comparison.")
        return

    cl1h = data["cl1h"]
    bh_equity = cl1h["close"] / cl1h["close"].iloc[0] * 100_000
    bh = summary(bh_equity)

    summary_df, curves_df = evaluate_sizing_modes(
        trades,
        MODE_ROWS,
        bh_return=float(bh["return"]),
        max_hold_bars_5m=int(CONFIG_OVERRIDES["max_hold_bars"]),
        total_hours=int(len(cl1h)),
    )

    out_dir = ROOT / "research" / "trials" / "futures" / "liquidity_sweep"
    summary_csv = out_dir / "position_sizing_results.csv"
    curves_csv = out_dir / "position_sizing_equity_curves.csv"
    html_path = out_dir / "position_sizing.html"
    json_path = out_dir / "position_sizing_summary.json"

    summary_df.to_csv(summary_csv, index=False)
    curves_df.to_csv(curves_csv, index=False)
    _write_html(summary_df, html_path)

    graph_csv = out_dir / "position_sizing_grid_graph.csv"
    wrote_graph_csv = _write_graph_grid_csv(summary_df, MODE_ROWS, trades, graph_csv)

    payload = {
        "config": CONFIG_OVERRIDES,
        "modes": MODE_ROWS,
        "top": summary_df.head(3).to_dict(orient="records"),
    }
    json_path.write_text(json.dumps(payload, indent=2, default=float))

    cols = [
        "label",
        "risk_avg",
        "return",
        "sharpe",
        "calmar",
        "max_drawdown",
        "bh_exposure_return",
        "outperformance_x",
    ]
    print("\n=== Position sizing comparison (top) ===")
    print(summary_df[cols].to_string(index=False))
    print(f"\nresults_csv: {summary_csv}")
    print(f"equity_csv: {curves_csv}")
    print(f"html: {html_path}")
    print(f"summary_json: {json_path}")
    if wrote_graph_csv:
        print(f"graph_csv: {graph_csv}")


if __name__ == "__main__":
    main()

