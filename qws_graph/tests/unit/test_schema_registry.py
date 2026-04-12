# mypy: ignore-errors
"""Unit tests for schema_registry and Story 4 CSV column routing."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

import pytest

registry_module = import_module("research.graph.schema_registry")
parsers_module = import_module("research.graph.parsers")

CORE_CONFIG_PROPERTIES = registry_module.CORE_CONFIG_PROPERTIES
CORE_RISK_PARAM_COLUMNS = registry_module.CORE_RISK_PARAM_COLUMNS
STRATEGY_EXTENSIONS = registry_module.STRATEGY_EXTENSIONS
RUN_PROPERTIES = registry_module.RUN_PROPERTIES
IGNORED_COLUMNS = registry_module.IGNORED_COLUMNS
get_config_keys = registry_module.get_config_keys
all_config_keys = registry_module.all_config_keys

CSVParser = parsers_module.CSVParser

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "artifacts"


def _fixed_ingested_at() -> datetime:
    return datetime(2026, 4, 2, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Schema registry unit tests
# ---------------------------------------------------------------------------


class TestGetConfigKeys:
    def test_returns_core_plus_risk_params_when_no_logic_type(self):
        keys = get_config_keys()
        assert "sizing_mode" in keys
        assert "target_r" in keys
        assert "atr_mult_stop" in keys  # risk param, still a Config key
        assert "wick_mode" in keys

    def test_adds_mars_extensions_for_mars_logic_type(self):
        keys = get_config_keys("mars")
        assert "atr_period" in keys
        assert "mom_period" in keys
        assert "trend_period" in keys
        assert "vol_threshold" in keys
        # Core keys still present
        assert "sizing_mode" in keys

    def test_adds_liquidity_sweep_extensions(self):
        keys = get_config_keys("liquidity-sweep")
        assert "time_stop" in keys
        assert "sizing_mode" in keys

    def test_unknown_logic_type_returns_core_only(self):
        keys = get_config_keys("some-unknown-strategy")
        assert keys == get_config_keys()

    def test_none_logic_type_returns_core_only(self):
        assert get_config_keys(None) == get_config_keys()

    def test_mars_keys_not_in_core(self):
        core = get_config_keys()
        assert "atr_period" not in core
        assert "mom_period" not in core


class TestAllConfigKeys:
    def test_includes_all_strategy_extensions(self):
        keys = all_config_keys()
        assert "atr_period" in keys  # mars
        assert "vol_threshold" in keys  # mars
        assert "time_stop" in keys  # liquidity-sweep
        assert "sizing_mode" in keys  # core

    def test_superset_of_get_config_keys_for_any_logic_type(self):
        for logic_type in list(STRATEGY_EXTENSIONS) + [None]:
            assert get_config_keys(logic_type).issubset(all_config_keys())


class TestRegistrySets:
    def test_risk_params_are_subset_of_config_keys(self):
        assert CORE_RISK_PARAM_COLUMNS.issubset(get_config_keys())

    def test_run_properties_contains_expected_columns(self):
        assert "calmar" in RUN_PROPERTIES
        assert "return" in RUN_PROPERTIES
        assert "tier" in RUN_PROPERTIES

    def test_ignored_columns_do_not_overlap_config_or_run(self):
        assert IGNORED_COLUMNS.isdisjoint(get_config_keys())
        assert IGNORED_COLUMNS.isdisjoint(RUN_PROPERTIES)

    def test_run_properties_and_config_keys_are_disjoint(self):
        # "return" is a raw CSV column name; it won't be in config keys
        assert RUN_PROPERTIES.isdisjoint(all_config_keys())


# ---------------------------------------------------------------------------
# Parser integration: new columns route correctly
# ---------------------------------------------------------------------------


class TestCsvParserSchemaRouting:
    def test_calmar_and_return_and_tier_do_not_produce_warnings(self, tmp_path: Path):
        csv_path = tmp_path / "cl_bear_liquidity_sweep_1h_golden.csv"
        csv_path.write_text(
            "instrument,timeframe,direction,logic_type,"
            "target_r,wick_mode,sizing_mode,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "calmar,return,tier,"
            "first_trade_ts,last_trade_ts\n"
            "CL,1H,bear,liquidity-sweep,"
            "1.25,exclude_q2,rdist_vol_target,"
            "32,0.65625,2.136028,4.58565,-0.028805,"
            "27.312855,0.099539,professional,"
            "2024-01-02T10:00:00Z,2025-10-01T16:00:00Z\n",
            encoding="utf-8",
        )

        artifact, warnings = CSVParser(
            csv_path, "baseline_csv", ingested_at=_fixed_ingested_at()
        ).parse()

        assert warnings == [], f"unexpected warnings: {warnings}"
        assert artifact.runs[0].calmar == pytest.approx(27.312855)
        assert artifact.runs[0].metrics_return == pytest.approx(0.099539)
        assert artifact.runs[0].tier == "professional"

    def test_mars_extension_columns_do_not_produce_warnings(self, tmp_path: Path):
        csv_path = tmp_path / "btc_bull_mars_1d_golden.csv"
        csv_path.write_text(
            "instrument,timeframe,direction,logic_type,"
            "atr_period,mom_period,trend_period,vol_threshold,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "first_trade_ts,last_trade_ts\n"
            "BTC,1D,bull,mars,"
            "14,20,50,0.05,"
            "26,0.307692,0.937264,0.278891,-0.724867,"
            "2024-01-02T10:00:00Z,2025-10-01T16:00:00Z\n",
            encoding="utf-8",
        )

        artifact, warnings = CSVParser(
            csv_path, "baseline_csv", ingested_at=_fixed_ingested_at()
        ).parse()

        assert warnings == [], f"unexpected warnings: {warnings}"
        assert artifact.configs[0].params_json["atr_period"] == 14
        assert artifact.configs[0].params_json["mom_period"] == 20
        assert artifact.configs[0].params_json["trend_period"] == 50
        assert artifact.configs[0].params_json["vol_threshold"] == pytest.approx(0.05)

    def test_label_routes_to_config_params_json(self, tmp_path: Path):
        csv_path = tmp_path / "cl_bear_liquidity_sweep_1h_position_sizing.csv"
        csv_path.write_text(
            "instrument,timeframe,direction,logic_type,"
            "label,target_r,sizing_mode,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "first_trade_ts,last_trade_ts\n"
            "CL,1H,bear,liquidity-sweep,"
            "loss_streak_2_half,1.25,rdist_vol_target,"
            "32,0.65625,2.064049,4.919603,-0.020557,"
            "2024-01-02T10:00:00Z,2025-10-01T16:00:00Z\n",
            encoding="utf-8",
        )

        artifact, warnings = CSVParser(
            csv_path, "baseline_csv", ingested_at=_fixed_ingested_at()
        ).parse()

        assert warnings == [], f"unexpected warnings: {warnings}"
        assert artifact.configs[0].params_json["label"] == "loss_streak_2_half"
        assert artifact.configs[0].params_json["sizing_mode"] == "rdist_vol_target"

    def test_ignored_columns_produce_no_warnings(self, tmp_path: Path):
        csv_path = tmp_path / "cl_bear_liquidity_sweep_1h_ignored.csv"
        csv_path.write_text(
            "instrument,timeframe,direction,logic_type,"
            "target_r,total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "gain,fees,fee_pct_of_gain,"
            "first_trade_ts,last_trade_ts\n"
            "CL,1H,bear,liquidity-sweep,"
            "1.25,32,0.65625,2.136028,4.58565,-0.028805,"
            "NaN,NaN,NaN,"
            "2024-01-02T10:00:00Z,2025-10-01T16:00:00Z\n",
            encoding="utf-8",
        )

        _, warnings = CSVParser(csv_path, "baseline_csv", ingested_at=_fixed_ingested_at()).parse()

        assert warnings == [], f"unexpected warnings: {warnings}"

    def test_truly_unknown_column_produces_warning(self, tmp_path: Path):
        csv_path = tmp_path / "es_bear_baseline_unknown.csv"
        csv_path.write_text(
            "instrument,timeframe,direction,logic_type,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "notes,experimental_flag,"
            "first_trade_ts,last_trade_ts\n"
            "ES,1H,bear,baseline,"
            "88,0.38,1.12,0.88,-7.2,"
            "some note,yes,"
            "2024-01-02T10:00:00Z,2025-10-01T16:00:00Z\n",
            encoding="utf-8",
        )

        _, warnings = CSVParser(csv_path, "baseline_csv", ingested_at=_fixed_ingested_at()).parse()

        assert len(warnings) == 1
        assert "experimental_flag" in warnings[0]
        assert "notes" in warnings[0]

    def test_core_metrics_still_land_on_run(self, tmp_path: Path):
        """Regression: sharpe, win_rate, profit_factor, max_drawdown stay on Run."""
        csv_path = tmp_path / "es_bear_baseline_regression.csv"
        csv_path.write_text(
            "instrument,timeframe,direction,logic_type,"
            "total_trades,win_rate,profit_factor,sharpe,max_drawdown,"
            "first_trade_ts,last_trade_ts\n"
            "ES,1H,bear,baseline,"
            "88,0.38,1.12,0.88,-7.2,"
            "2024-01-02T10:00:00Z,2025-10-01T16:00:00Z\n",
            encoding="utf-8",
        )

        artifact, warnings = CSVParser(
            csv_path, "baseline_csv", ingested_at=_fixed_ingested_at()
        ).parse()

        assert warnings == []
        run = artifact.runs[0]
        assert run.sharpe == pytest.approx(0.88)
        assert run.win_rate == pytest.approx(0.38)
        assert run.profit_factor == pytest.approx(1.12)
        assert run.max_drawdown == pytest.approx(-7.2)
        assert run.calmar is None
        assert run.metrics_return is None
        assert run.tier is None

    def test_existing_fixture_still_parses_without_warnings(self):
        """Regression: existing ES grid fixture still clean after refactor."""
        artifact, warnings = CSVParser(
            FIXTURES_DIR / "grid" / "es_bear_sweep_1h_grid_nypre_london_v1_fixture.txt",
            "grid_csv",
            ingested_at=_fixed_ingested_at(),
        ).parse()

        assert warnings == []
        assert artifact.configs[0].params_json["target_r"] == pytest.approx(1.5)
