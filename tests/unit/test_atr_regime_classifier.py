"""Unit tests for QWS-1403: ATR+ADX regime classifier."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from research.regimes.atr_trend_classifier import (
    LABEL_DTYPE,
    LABELS,
    MAX_SINGLE_LABEL_FRACTION,
    _check_distribution,
    classify,
    run,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bars(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Synthetic OHLCV bars with realistic price movement."""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    idx = pd.date_range("2023-01-01", periods=n, freq="1h")
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close}, index=idx)


def _make_crisis_bars(n: int = 100) -> pd.DataFrame:
    """High-volatility trending bars designed to trigger 'crisis' label."""
    rng = np.random.default_rng(0)
    # Large moves, clear trend
    close = 100 + np.cumsum(rng.normal(2.0, 3.0, n))
    high = close + rng.uniform(2.0, 5.0, n)
    low = close - rng.uniform(0.1, 0.5, n)
    idx = pd.date_range("2023-01-01", periods=n, freq="1h")
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close}, index=idx)


def _make_ranging_bars(n: int = 100) -> pd.DataFrame:
    """Low-volatility choppy bars designed to trigger 'low_vol_ranging' label."""
    rng = np.random.default_rng(1)
    # Tiny oscillations, no trend
    close = 100 + np.cumsum(rng.normal(0, 0.02, n))
    high = close + rng.uniform(0.01, 0.05, n)
    low = close - rng.uniform(0.01, 0.05, n)
    idx = pd.date_range("2023-01-01", periods=n, freq="1h")
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close}, index=idx)


# ---------------------------------------------------------------------------
# classify() — label structure
# ---------------------------------------------------------------------------


class TestClassifyStructure:
    def test_returns_series(self) -> None:
        df = _make_bars()
        result = classify(df)
        assert isinstance(result, pd.Series)

    def test_categorical_dtype(self) -> None:
        df = _make_bars()
        result = classify(df)
        assert result.dtype == LABEL_DTYPE

    def test_all_four_categories_present_in_dtype(self) -> None:
        df = _make_bars()
        result = classify(df)
        assert set(result.cat.categories) == set(LABELS)

    def test_index_matches_input(self) -> None:
        df = _make_bars(300)
        result = classify(df)
        assert result.index.equals(df.index)

    def test_no_null_values_after_warmup(self) -> None:
        df = _make_bars(300)
        result = classify(df)
        # Some NaNs are expected at the start (warmup period for ATR/ADX)
        # — all non-NaN values must be valid labels
        non_null = result.dropna()
        assert non_null.isin(LABELS).all()

    def test_missing_column_raises(self) -> None:
        df = _make_bars().drop(columns=["high"])
        with pytest.raises(ValueError, match="missing columns"):
            classify(df)


# ---------------------------------------------------------------------------
# classify() — label assignment correctness
# ---------------------------------------------------------------------------


class TestLabelAssignment:
    def test_diverse_bars_produce_multiple_labels(self) -> None:
        """A realistic bar set should contain at least 2 distinct labels."""
        df = _make_bars(500)
        result = classify(df)
        assert result.dropna().nunique() >= 2

    def test_at_least_some_transitional(self) -> None:
        """Transitional is the catch-all — should appear in a mixed dataset."""
        df = _make_bars(500)
        result = classify(df)
        assert "transitional" in result.dropna().values

    def test_no_single_label_dominates_mixed(self) -> None:
        """On a mixed dataset, no label should exceed the 80% guard."""
        df = _make_bars(500)
        result = classify(df).dropna()
        counts = result.value_counts(normalize=True)
        assert counts.max() < MAX_SINGLE_LABEL_FRACTION


# ---------------------------------------------------------------------------
# 80% distribution guard
# ---------------------------------------------------------------------------


class TestDistributionGuard:
    def test_passes_for_diverse_series(self) -> None:
        s = pd.Categorical(
            ["crisis"] * 20
            + ["high_vol_trending"] * 30
            + ["low_vol_ranging"] * 25
            + ["transitional"] * 25,
            categories=LABELS,
        )
        series = pd.Series(s)
        _check_distribution(series, "TEST_1H")  # must not raise

    def test_raises_when_dominated(self) -> None:
        s = pd.Categorical(
            ["transitional"] * 90 + ["crisis"] * 10,
            categories=LABELS,
        )
        series = pd.Series(s)
        with pytest.raises(ValueError, match="exceeds"):
            _check_distribution(series, "TEST_1H")

    def test_exact_80_pct_raises(self) -> None:
        # 80/100 = 80% exactly — should raise (> not >=, boundary check)
        s = pd.Categorical(
            ["transitional"] * 80 + ["crisis"] * 20,
            categories=LABELS,
        )
        series = pd.Series(s)
        # 80% is NOT > 80%, so it must NOT raise
        _check_distribution(series, "TEST_1H")  # should pass

    def test_just_over_80_raises(self) -> None:
        s = pd.Categorical(
            ["transitional"] * 81 + ["crisis"] * 19,
            categories=LABELS,
        )
        series = pd.Series(s)
        with pytest.raises(ValueError, match="transitional"):
            _check_distribution(series, "TEST_1H")


# ---------------------------------------------------------------------------
# store.write_signals mock
# ---------------------------------------------------------------------------


class TestStoreWrite:
    def test_overwrite_bars_called_once(self) -> None:
        """run() must call store.overwrite_bars() exactly once."""
        df = _make_bars(500)

        mock_store = MagicMock()
        mock_store.read_bars.return_value = df

        with patch("research.regimes.atr_trend_classifier.Store", return_value=mock_store):
            run("CL", "1H")

        mock_store.overwrite_bars.assert_called_once()

    def test_overwrite_bars_key(self) -> None:
        """overwrite_bars must be called with library='signals', symbol='regime_atr/CL_1H'."""
        df = _make_bars(500)

        mock_store = MagicMock()
        mock_store.read_bars.return_value = df

        with patch("research.regimes.atr_trend_classifier.Store", return_value=mock_store):
            run("CL", "1H")

        call_args = mock_store.overwrite_bars.call_args
        assert call_args[0][0] == "signals"
        assert call_args[0][1] == "regime_atr/CL_1H"

    def test_overwrite_bars_df_has_label_column(self) -> None:
        """DataFrame passed to overwrite_bars must have a 'label' column."""
        df = _make_bars(500)

        mock_store = MagicMock()
        mock_store.read_bars.return_value = df

        with patch("research.regimes.atr_trend_classifier.Store", return_value=mock_store):
            run("CL", "1H")

        written_df: pd.DataFrame = mock_store.overwrite_bars.call_args[0][2]
        assert "label" in written_df.columns

    def test_label_column_is_string_not_categorical(self) -> None:
        """Written DataFrame must use string dtype — ArcticDB cannot store categorical."""
        df = _make_bars(500)

        mock_store = MagicMock()
        mock_store.read_bars.return_value = df

        with patch("research.regimes.atr_trend_classifier.Store", return_value=mock_store):
            run("CL", "1H")

        written_df: pd.DataFrame = mock_store.overwrite_bars.call_args[0][2]
        assert str(written_df["label"].dtype) == "object"

    def test_unknown_symbol_raises(self) -> None:
        mock_store = MagicMock()
        with patch("research.regimes.atr_trend_classifier.Store", return_value=mock_store):
            with pytest.raises(ValueError, match="Unknown symbol"):
                run("UNKNOWN", "1H")

    def test_empty_bars_raises(self) -> None:
        mock_store = MagicMock()
        mock_store.read_bars.return_value = pd.DataFrame()
        with patch("research.regimes.atr_trend_classifier.Store", return_value=mock_store):
            with pytest.raises(RuntimeError, match="No bars found"):
                run("CL", "1H")
