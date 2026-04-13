"""Unit tests for Store.write_series and Store.read_series."""

import pandas as pd
import pytest

from data.store import Store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_df(dates: list[str], value_start: float = 1.0) -> pd.DataFrame:
    idx = pd.to_datetime(dates, utc=True)
    return pd.DataFrame(
        {"value": [value_start + i for i in range(len(dates))]},
        index=idx,
    )


@pytest.fixture()
def store(tmp_path: "pytest.TempPathFactory") -> Store:
    uri = f"lmdb://{tmp_path}"
    return Store(uri=uri)


# ---------------------------------------------------------------------------
# AC1: write_series exists and is importable
# ---------------------------------------------------------------------------


def test_write_series_importable() -> None:
    assert callable(Store.write_series)


# ---------------------------------------------------------------------------
# AC2: read_series exists and is importable
# ---------------------------------------------------------------------------


def test_read_series_importable() -> None:
    assert callable(Store.read_series)


# ---------------------------------------------------------------------------
# AC3: write then read returns identical DataFrame
# ---------------------------------------------------------------------------


def test_write_read_roundtrip(store: Store) -> None:
    df = _make_df(["2024-01-01", "2024-01-02", "2024-01-03"])
    store.write_series("macro", "TEST_SYMBOL_1D", df)
    result = store.read_series("macro", "TEST_SYMBOL_1D")
    pd.testing.assert_frame_equal(result.sort_index(), df.sort_index())


# ---------------------------------------------------------------------------
# AC4: overlapping write does not duplicate index entries
# ---------------------------------------------------------------------------


def test_idempotent_no_duplicates(store: Store) -> None:
    df1 = _make_df(["2024-01-01", "2024-01-02", "2024-01-03"])
    store.write_series("macro", "TEST_DEDUP_1D", df1)

    # Write overlapping range — same dates, different values (last write wins)
    df2 = _make_df(["2024-01-02", "2024-01-03", "2024-01-04"], value_start=10.0)
    store.write_series("macro", "TEST_DEDUP_1D", df2)

    result = store.read_series("macro", "TEST_DEDUP_1D")
    assert result.index.duplicated().sum() == 0, "Duplicate index entries found"
    assert len(result) == 4, f"Expected 4 rows, got {len(result)}"
    # Last-write wins for overlapping rows
    assert result.loc[pd.Timestamp("2024-01-02", tz="UTC"), "value"] == 10.0
    assert result.loc[pd.Timestamp("2024-01-03", tz="UTC"), "value"] == 11.0


# ---------------------------------------------------------------------------
# AC5: read_series with start/end returns only rows within range
# ---------------------------------------------------------------------------


def test_date_range_filter(store: Store) -> None:
    df = _make_df(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    store.write_series("macro", "TEST_RANGE_1D", df)

    result = store.read_series("macro", "TEST_RANGE_1D", start="2024-01-02", end="2024-01-04")
    assert len(result) == 3
    assert result.index[0] == pd.Timestamp("2024-01-02", tz="UTC")
    assert result.index[-1] == pd.Timestamp("2024-01-04", tz="UTC")


def test_date_range_start_only(store: Store) -> None:
    df = _make_df(["2024-01-01", "2024-01-02", "2024-01-03"])
    store.write_series("macro", "TEST_RANGE_START_1D", df)

    result = store.read_series("macro", "TEST_RANGE_START_1D", start="2024-01-02")
    assert len(result) == 2
    assert result.index[0] == pd.Timestamp("2024-01-02", tz="UTC")


def test_date_range_end_only(store: Store) -> None:
    df = _make_df(["2024-01-01", "2024-01-02", "2024-01-03"])
    store.write_series("macro", "TEST_RANGE_END_1D", df)

    result = store.read_series("macro", "TEST_RANGE_END_1D", end="2024-01-02")
    assert len(result) == 2
    assert result.index[-1] == pd.Timestamp("2024-01-02", tz="UTC")


# ---------------------------------------------------------------------------
# Bonus: macro library created on first write (no pre-existing lib required)
# ---------------------------------------------------------------------------


def test_new_library_created_on_write(store: Store) -> None:
    df = _make_df(["2024-06-01"])
    store.write_series("macro_new_lib", "SOME_SERIES_1D", df)
    result = store.read_series("macro_new_lib", "SOME_SERIES_1D")
    assert len(result) == 1
