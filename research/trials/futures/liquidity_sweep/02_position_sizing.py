"""Position sizing experiments for the liquidity sweep baseline trades."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.experiments.metrics import summary
from research.graph_export import write_grid_csv
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




def main() -> None:
    ap = argparse.ArgumentParser(description="Liquidity sweep position sizing trial")
    ap.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Write all artifacts here (default: research/results/futures/liquidity_sweep/)",
    )
    args = ap.parse_args()
    _default_out = ROOT / "research" / "results" / "futures" / "liquidity_sweep"
    _out_dir = Path(args.output_dir) if args.output_dir else _default_out
    _out_dir.mkdir(parents=True, exist_ok=True)

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

    summary_csv = _out_dir / "position_sizing_results.csv"
    curves_csv = _out_dir / "position_sizing_equity_curves.csv"
    html_path = _out_dir / "position_sizing.html"
    json_path = _out_dir / "position_sizing_summary.json"

    summary_df.to_csv(summary_csv, index=False)
    curves_df.to_csv(curves_csv, index=False)
    _write_html(summary_df, html_path)

    graph_csv = _out_dir / "position_sizing_grid_graph.csv"
    wrote_graph_csv = False
    if not summary_df.empty:
        # Compute per-trade metrics from baseline trades (shared across sizing modes).
        mode_lookup = {str(row.get("label", "")): row for row in MODE_ROWS}
        _win_rate = float((trades["pnl_r"].astype(float) > 0).mean()) if not trades.empty else 0.0
        _gross_profit = float(trades.loc[trades["pnl_r"] > 0, "pnl_r"].sum()) if not trades.empty else 0.0
        _gross_loss = float((-trades.loc[trades["pnl_r"] < 0, "pnl_r"].sum())) if not trades.empty else 0.0
        _profit_factor = (_gross_profit / _gross_loss) if _gross_loss > 0 else (999.0 if _gross_profit > 0 else 0.0)
        grid_df = summary_df.copy()
        grid_df["total_trades"] = int(len(trades))
        grid_df["win_rate"] = _win_rate
        grid_df["profit_factor"] = _profit_factor
        grid_df["max_drawdown"] = grid_df["max_drawdown"].astype(float)
        grid_df["sharpe"] = grid_df["sharpe"].astype(float)
        if not trades.empty:
            grid_df["first_trade_ts"] = pd.Timestamp(trades["entry_time"].min()).isoformat()
            grid_df["last_trade_ts"] = pd.Timestamp(trades["entry_time"].max()).isoformat()
            grid_df["backtest_start"] = cl1h.index.min().isoformat()
            grid_df["backtest_end"] = cl1h.index.max().isoformat()
        grid_df["params_json"] = grid_df["label"].astype(str).map(
            lambda lbl: json.dumps(mode_lookup.get(lbl, {"label": lbl}), sort_keys=True)
        )
        write_grid_csv(
            grid_df,
            output_path=graph_csv,
            instrument="CL",
            timeframe="1H",
            direction="bear",
            logic_type="liquidity-sweep",
        )
        wrote_graph_csv = True

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

