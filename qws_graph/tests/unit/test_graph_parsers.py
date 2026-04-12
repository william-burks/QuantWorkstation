"""Unit tests for V1 graph models and artifact parsers."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from importlib import import_module
from pathlib import Path

import pytest

ids_module = import_module("research.graph.ids")
models_module = import_module("research.graph.models")
parsers_module = import_module("research.graph.parsers")

canonical_json = ids_module.canonical_json
champion_id = ids_module.champion_id
config_id = ids_module.config_id
hash12 = ids_module.hash12
normalize_text = ids_module.normalize_text
run_id = ids_module.run_id
strategy_id = ids_module.strategy_id

Champion = models_module.Champion
Config = models_module.Config
Provenance = models_module.Provenance
ResearchArtifact = models_module.ResearchArtifact
Run = models_module.Run
Strategy = models_module.Strategy

CSVParser = parsers_module.CSVParser
ChampionMarkdownParser = parsers_module.ChampionMarkdownParser
research_artifact_payload_hash = parsers_module.research_artifact_payload_hash

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "artifacts"
ES_BASELINE_FIXTURE = FIXTURES_DIR / "baseline" / "es_bear_baseline_fixture.txt"
NQ_BASELINE_FIXTURE = FIXTURES_DIR / "baseline" / "nq_bull_baseline_fixture.txt"
ES_GRID_FIXTURE = FIXTURES_DIR / "grid" / "es_bear_sweep_1h_grid_nypre_london_v1_fixture.txt"


def _fixed_ingested_at() -> datetime:
    return datetime(2026, 4, 2, 12, 0, tzinfo=UTC)


class TestIdUtilities:
    def test_normalize_text(self):
        assert normalize_text("Bear_Baseline") == "bear-baseline"
        assert normalize_text(" test---value ") == "test-value"

    def test_canonical_json_is_deterministic(self):
        assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})

    def test_hash_helpers_are_stable(self):
        assert hash12("a", "b") == hash12("a", "b")
        assert strategy_id("ES", "1H", "bear", "sweep") == "es-1h-bear-sweep"
        assert len(run_id("es-1h-bear-sweep", "results/x.csv", "2026-04-01T10:00:00Z")) == 12
        assert config_id({"target_r": 1.5}, {"atr_mult_stop": 0.5}) == config_id(
            {"target_r": 1.5}, {"atr_mult_stop": 0.5}
        )
        assert champion_id("es-1h-bear-sweep", "2026-04-02") == champion_id(
            "es-1h-bear-sweep", "2026-04-02"
        )


class TestModels:
    def test_run_win_rate_validation(self):
        provenance = Provenance(
            artifact_path="results/test.csv",
            artifact_hash="abc123",
            artifact_mtime_iso="2026-04-01T10:00:00Z",
            ingested_at=_fixed_ingested_at(),
        )
        with pytest.raises(ValueError, match="win_rate must be in"):
            Run(
                run_id="abc123def456",
                strategy_id="es-1h-bear-sweep",
                timestamp=_fixed_ingested_at(),
                sharpe=1.0,
                profit_factor=1.1,
                win_rate=1.2,
                max_drawdown=-4.0,
                total_trades=25,
                artifact_path="results/test.csv",
                provenance=provenance,
            )

    def test_champion_requires_fragilities(self):
        provenance = Provenance(
            artifact_path="research/results/champions/test.md",
            artifact_hash="abc123",
            artifact_mtime_iso="2026-04-01T10:00:00Z",
            ingested_at=_fixed_ingested_at(),
        )
        with pytest.raises(ValueError, match="fragilities"):
            Champion(
                champion_id="abc123def456",
                strategy_id="es-1h-bear-sweep",
                freeze_date=date(2026, 4, 2),
                metrics_summary={"sharpe": 1.2},
                oos_status="oos_pending",
                fragilities=[],
                artifact_path="research/results/champions/test.md",
                provenance=provenance,
            )

    def test_csv_artifact_requires_config_per_run(self):
        strategy = Strategy(
            strategy_id="es-1h-bear-sweep",
            instrument="ES",
            timeframe="1H",
            direction="bear",
            logic_type="sweep",
        )
        provenance = Provenance(
            artifact_path="results/test.csv",
            artifact_hash="abc123",
            artifact_mtime_iso="2026-04-01T10:00:00Z",
            ingested_at=_fixed_ingested_at(),
        )
        run = Run(
            run_id="abc123def456",
            strategy_id=strategy.strategy_id,
            timestamp=_fixed_ingested_at(),
            sharpe=1.0,
            profit_factor=1.1,
            win_rate=0.5,
            max_drawdown=-4.0,
            total_trades=25,
            artifact_path="results/test.csv",
            provenance=provenance,
            first_trade_ts=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            last_trade_ts=datetime(2025, 10, 1, 16, 0, tzinfo=UTC),
        )
        with pytest.raises(ValueError, match="at least one config"):
            ResearchArtifact(kind="baseline_csv", strategy=strategy, runs=[run], configs=[])


class TestCsvParser:
    def test_baseline_csv_parser_returns_valid_runs(self):
        artifact, warnings = CSVParser(
            ES_BASELINE_FIXTURE,
            "baseline_csv",
            ingested_at=_fixed_ingested_at(),
        ).parse()

        assert warnings == []
        assert artifact.kind == "baseline_csv"
        assert artifact.strategy.strategy_id == "es-1h-bear-baseline"
        assert len(artifact.runs) == 2
        assert len(artifact.configs) == 2
        assert len({run.run_id for run in artifact.runs}) == 2
        assert artifact.configs[0].params_json["allowed_sessions"] == ["NY_PRE", "LONDON"]
        assert artifact.configs[0].risk_params == {"atr_mult_stop": 0.5}

    def test_nq_baseline_fixture_validates_second_instrument(self):
        artifact, _ = CSVParser(
            NQ_BASELINE_FIXTURE,
            "baseline_csv",
            ingested_at=_fixed_ingested_at(),
        ).parse()

        assert artifact.strategy.instrument == "NQ"
        assert artifact.strategy.timeframe == "4H"
        assert artifact.strategy.direction == "bull"
        assert artifact.runs[0].total_trades == 52

    def test_grid_csv_parser_maps_real_repo_columns(self):
        artifact, warnings = CSVParser(
            ES_GRID_FIXTURE,
            "grid_csv",
            ingested_at=_fixed_ingested_at(),
        ).parse()

        assert warnings == []
        assert artifact.kind == "grid_csv"
        assert artifact.strategy.strategy_id == "es-1h-bear-sweep"
        assert len(artifact.runs) == 3
        assert len(artifact.configs) == 3
        assert artifact.runs[0].total_trades == 99
        assert artifact.runs[0].profit_factor == pytest.approx(1.15625)
        assert artifact.configs[0].params_json["sessions"] == ["NY_PRE", "LONDON"]
        assert artifact.configs[0].params_json["target_r"] == pytest.approx(1.5)
        assert artifact.configs[0].risk_params["atr_mult_stop"] == pytest.approx(0.5)

    def test_missing_required_columns_fail_validation(self, tmp_path: Path):
        csv_path = tmp_path / "broken.csv"
        csv_path.write_text(
            "instrument,timeframe,direction,logic_type,total_trades,win_rate,profit_factor,max_drawdown,first_trade_ts,last_trade_ts\n"
            "ES,1H,bear,baseline,88,0.38,1.12,-7.2,2024-01-02T10:00:00Z,2025-10-01T16:00:00Z\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="missing required columns: sharpe"):
            CSVParser(csv_path, "baseline_csv", ingested_at=_fixed_ingested_at()).parse()

    def test_unknown_columns_are_ignored_and_reported(self, tmp_path: Path):
        csv_path = tmp_path / "es_bear_baseline_extra.csv"
        csv_path.write_text(
            "instrument,timeframe,direction,logic_type,target_r,total_trades,"
            "win_rate,profit_factor,sharpe,max_drawdown,first_trade_ts,last_trade_ts,notes\n"
            "ES,1H,bear,baseline,1.0,88,0.38,1.12,0.88,-7.2,"
            "2024-01-02T10:00:00Z,2025-10-01T16:00:00Z,ignore me\n",
            encoding="utf-8",
        )

        artifact, warnings = CSVParser(
            csv_path, "baseline_csv", ingested_at=_fixed_ingested_at()
        ).parse()

        assert artifact.runs[0].total_trades == 88
        assert warnings == [f"Unknown columns in {csv_path.name}: notes"]

    def test_repeated_csv_parse_returns_identical_normalized_payload_hash(self):
        parser = CSVParser(
            ES_GRID_FIXTURE,
            "grid_csv",
        )
        artifact_1, _ = parser.parse()
        artifact_2, _ = CSVParser(
            ES_GRID_FIXTURE,
            "grid_csv",
        ).parse()

        assert research_artifact_payload_hash(artifact_1) == research_artifact_payload_hash(
            artifact_2
        )
        assert [config.config_id for config in artifact_1.configs] == [
            config.config_id for config in artifact_2.configs
        ]


class TestChampionMarkdownParser:
    def test_champion_parser_returns_valid_champion_payload(self):
        artifact, warnings = ChampionMarkdownParser(
            FIXTURES_DIR / "champion" / "es_bear_sweep_1h_v1.md",
            ingested_at=_fixed_ingested_at(),
        ).parse()

        assert warnings == []
        assert artifact.kind == "champion_md"
        assert artifact.strategy.strategy_id == "es-1h-bear-sweep"
        assert artifact.champion is not None
        assert artifact.champion.freeze_date == date(2026, 4, 2)
        assert artifact.champion.metrics_summary["sample_size"] == 99
        assert artifact.champion.metrics_summary["max_drawdown_r"] == pytest.approx(-8.68605)
        assert artifact.champion.oos_status == "oos_pending"
        assert len(artifact.champion.fragilities) == 4
        assert artifact.champion.pivot_from_run_id == "a1b2c3d4e5f6"

    def test_nq_champion_fixture_parses_fragilities(self):
        artifact, _ = ChampionMarkdownParser(
            FIXTURES_DIR / "champion" / "nq_bull_sweep_4h_v1.md",
            ingested_at=_fixed_ingested_at(),
        ).parse()

        assert artifact.strategy.instrument == "NQ"
        assert artifact.strategy.timeframe == "4H"
        assert len(artifact.champion.fragilities) == 3

    def test_registry_status_is_used_when_present(self, tmp_path: Path):
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(
            json.dumps(
                [
                    {
                        "champion_file": "research/results/champions/es_bear_sweep_1h_v1.md",
                        "status": "live_paper",
                    }
                ]
            ),
            encoding="utf-8",
        )

        artifact, _ = ChampionMarkdownParser(
            FIXTURES_DIR / "champion" / "es_bear_sweep_1h_v1.md",
            registry_path=registry_path,
            ingested_at=_fixed_ingested_at(),
        ).parse()

        assert artifact.champion.oos_status == "live_paper"

    def test_missing_required_sections_fail_validation(self, tmp_path: Path):
        md_path = tmp_path / "broken.md"
        md_path.write_text(
            "# Broken Champion\n\n"
            "**Freeze Date**: 2026-04-02\n\n"
            "## Config\n- Instrument: ES\n- Direction: BEAR\n- Sweep timeframe: 1H\n\n"
            "## IS Metrics\n- Sample size: 20\n- Sharpe: 1.1\n\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="missing required champion sections"):
            ChampionMarkdownParser(md_path, ingested_at=_fixed_ingested_at()).parse()

    def test_repeated_champion_parse_returns_identical_normalized_payload_hash(self):
        artifact_1, _ = ChampionMarkdownParser(
            FIXTURES_DIR / "champion" / "es_bear_sweep_1h_v1.md"
        ).parse()
        artifact_2, _ = ChampionMarkdownParser(
            FIXTURES_DIR / "champion" / "es_bear_sweep_1h_v1.md"
        ).parse()

        assert research_artifact_payload_hash(artifact_1) == research_artifact_payload_hash(
            artifact_2
        )
        assert (
            artifact_1.champion.champion_id  # type: ignore[union-attr]
            == artifact_2.champion.champion_id  # type: ignore[union-attr]
        )


class TestParserIntegration:
    def test_baseline_and_champion_share_core_strategy_dimensions(self):
        baseline, _ = CSVParser(
            ES_BASELINE_FIXTURE,
            "baseline_csv",
            ingested_at=_fixed_ingested_at(),
        ).parse()
        champion, _ = ChampionMarkdownParser(
            FIXTURES_DIR / "champion" / "es_bear_sweep_1h_v1.md",
            ingested_at=_fixed_ingested_at(),
        ).parse()

        b, c = baseline.strategy, champion.strategy
        assert (b.instrument, b.timeframe, b.direction) == (
            c.instrument,
            c.timeframe,
            c.direction,
        )


class TestArtifactPathNormalization:
    """Unit tests for _artifact_path_text repo-relative normalization (QWS artifact path story)."""

    _fn = staticmethod(parsers_module._artifact_path_text)

    def test_absolute_path_under_repo_root_normalized(self, tmp_path):
        repo_root = tmp_path / "repo"
        artifact = repo_root / "research" / "results" / "futures" / "baseline.csv"
        result = self._fn(artifact, repo_root)
        assert result == "research/results/futures/baseline.csv"

    def test_absolute_path_outside_repo_root_returned_as_posix(self, tmp_path):
        repo_root = tmp_path / "repo"
        artifact = tmp_path / "other" / "baseline.csv"
        result = self._fn(artifact, repo_root)
        assert result == artifact.as_posix()

    def test_no_repo_root_returns_path_as_posix(self, tmp_path):
        artifact = tmp_path / "research" / "results" / "baseline.csv"
        result = self._fn(artifact, None)
        assert result == artifact.as_posix()

    def test_relative_path_under_repo_root_normalized(self, tmp_path):
        # Path constructed relative-style but resolves under repo root
        repo_root = tmp_path / "repo"
        artifact = repo_root / "research" / "results" / "baseline.csv"
        result = self._fn(artifact, repo_root)
        assert not result.startswith("/")
        assert result == "research/results/baseline.csv"

    def test_csv_and_champion_md_paths_normalize_consistently(self, tmp_path):
        repo_root = tmp_path / "repo"
        csv = (
            repo_root
            / "research"
            / "results"
            / "futures"
            / "runs"
            / "20260101-120000"
            / "baseline.csv"
        )
        md = repo_root / "research" / "results" / "champions" / "es_bear_v1.md"
        assert self._fn(csv, repo_root) == (
            "research/results/futures/runs/20260101-120000/baseline.csv"
        )
        assert self._fn(md, repo_root) == "research/results/champions/es_bear_v1.md"


class TestSignificanceGateProperties:
    """Tests for QWS-0407: active_window_frequency and duty_cycle computation."""

    def _make_csv(
        self,
        tmp_path,
        extra_header="",
        extra_vals="",
        n_trades=60,
        first_ts="2024-01-01T00:00:00Z",
        last_ts="2024-07-01T00:00:00Z",
    ):
        """Build a minimal valid CSV with timestamp columns."""
        path = tmp_path / "es_bear_baseline_test.csv"
        path.write_text(
            f"instrument,timeframe,direction,logic_type,total_trades,win_rate,profit_factor,sharpe,max_drawdown,first_trade_ts,last_trade_ts{extra_header}\n"
            f"ES,1H,bear,baseline,{n_trades},0.50,1.50,1.20,-0.10,{first_ts},{last_ts}{extra_vals}\n",
            encoding="utf-8",
        )
        return path

    def test_active_window_frequency_computed_correctly(self, tmp_path):
        path = self._make_csv(tmp_path)
        artifact, warnings = CSVParser(
            path, "baseline_csv", ingested_at=_fixed_ingested_at()
        ).parse()

        run = artifact.runs[0]
        # first=2024-01-01, last=2024-07-01: 182 days (Jan31+Feb29+Mar31+Apr30+May31+Jun30=182)
        expected_active_days = 182.0
        expected_freq = 60 / expected_active_days
        assert run.active_window_frequency == pytest.approx(expected_freq)

    def test_duty_cycle_computed_when_backtest_range_present(self, tmp_path):
        path = self._make_csv(
            tmp_path,
            extra_header=",backtest_start,backtest_end",
            extra_vals=",2024-01-01T00:00:00Z,2024-12-31T00:00:00Z",
        )
        artifact, _ = CSVParser(path, "baseline_csv", ingested_at=_fixed_ingested_at()).parse()

        run = artifact.runs[0]
        # active_days=182, total_backtest_days=(Dec31-Jan1)=365
        assert run.duty_cycle == pytest.approx(182.0 / 365.0)

    def test_duty_cycle_null_when_backtest_range_absent(self, tmp_path):
        path = self._make_csv(tmp_path)
        artifact, _ = CSVParser(path, "baseline_csv", ingested_at=_fixed_ingested_at()).parse()

        assert artifact.runs[0].duty_cycle is None

    def test_missing_first_trade_ts_raises(self, tmp_path):
        path = tmp_path / "broken.csv"
        path.write_text(
            "instrument,timeframe,direction,logic_type,total_trades,win_rate,profit_factor,sharpe,max_drawdown,last_trade_ts\n"
            "ES,1H,bear,baseline,60,0.50,1.50,1.20,-0.10,2024-07-01T00:00:00Z\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="first_trade_ts"):
            CSVParser(path, "baseline_csv", ingested_at=_fixed_ingested_at()).parse()

    def test_missing_last_trade_ts_raises(self, tmp_path):
        path = tmp_path / "broken.csv"
        path.write_text(
            "instrument,timeframe,direction,logic_type,total_trades,win_rate,profit_factor,sharpe,max_drawdown,first_trade_ts\n"
            "ES,1H,bear,baseline,60,0.50,1.50,1.20,-0.10,2024-01-01T00:00:00Z\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="last_trade_ts"):
            CSVParser(path, "baseline_csv", ingested_at=_fixed_ingested_at()).parse()

    def test_zero_duration_yields_null_frequency(self, tmp_path):
        # first == last → zero active window → active_window_frequency is None
        path = self._make_csv(
            tmp_path,
            first_ts="2024-01-01T00:00:00Z",
            last_ts="2024-01-01T00:00:00Z",
        )
        artifact, _ = CSVParser(path, "baseline_csv", ingested_at=_fixed_ingested_at()).parse()

        run = artifact.runs[0]
        assert run.active_window_frequency is None
        assert run.duty_cycle is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
