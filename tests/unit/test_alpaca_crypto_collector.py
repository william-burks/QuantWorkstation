"""
Unit tests for the Alpaca crypto collector.
All external calls (Alpaca API, arcticdb store) are mocked.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd

from data.collectors.alpaca_crypto import _bars_to_df, collect


def _make_mock_bar(ts: datetime, price: float = 40000.0) -> MagicMock:
    bar = MagicMock()
    bar.timestamp = ts
    bar.open = price
    bar.high = price * 1.01
    bar.low = price * 0.99
    bar.close = price
    bar.volume = 100.0
    return bar


def _make_response(symbol: str, bars: list) -> MagicMock:
    """Mock a BarSet — data lives in response.data dict."""
    response = MagicMock()
    response.data = {symbol: bars} if bars else {}
    return response


# ------------------------------------------------------------------
# _bars_to_df  (now takes a list, not a response object)
# ------------------------------------------------------------------


def test_bars_to_df_shape():
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    bars = [_make_mock_bar(ts), _make_mock_bar(ts + timedelta(days=1))]
    df = _bars_to_df(bars)
    assert len(df) == 2
    assert list(df.columns) == [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "market",
        "source",
        "adjusted",
    ]
    assert df.index.name == "timestamp"
    assert df["market"].iloc[0] == "crypto"
    assert df["source"].iloc[0] == "alpaca"
    assert not df["adjusted"].iloc[0]


def test_bars_to_df_index_is_utc():
    ts = datetime(2024, 6, 1, tzinfo=UTC)
    bars = [_make_mock_bar(ts)]
    df = _bars_to_df(bars)
    assert df.index.tz is not None
    assert str(df.index.tz) == "UTC"


# ------------------------------------------------------------------
# collect — init path (no existing data)
# ------------------------------------------------------------------


@patch("data.collectors.alpaca_crypto.get_store")
@patch("data.collectors.alpaca_crypto._client")
def test_collect_init_fetches_two_years(mock_client, mock_get_store):
    store = MagicMock()
    store.has_symbol.return_value = False
    mock_get_store.return_value = store

    ts = datetime(2024, 1, 1, tzinfo=UTC)
    mock_bars = [_make_mock_bar(ts + timedelta(days=i)) for i in range(5)]
    response = _make_response("BTC/USD", mock_bars)

    client = MagicMock()
    client.get_crypto_bars.return_value = response
    mock_client.return_value = client

    collect("BTC/USD", "1D")

    store.write_bars.assert_called_once()
    call_args = store.write_bars.call_args[0]
    assert call_args[0] == "crypto"
    assert call_args[1] == "BTC/USD_1D"
    assert len(call_args[2]) == 5


@patch("data.collectors.alpaca_crypto.get_store")
@patch("data.collectors.alpaca_crypto._client")
def test_collect_init_start_is_approx_two_years_ago(mock_client, mock_get_store):
    store = MagicMock()
    store.has_symbol.return_value = False
    mock_get_store.return_value = store

    response = _make_response("BTC/USD", [])
    client = MagicMock()
    client.get_crypto_bars.return_value = response
    mock_client.return_value = client

    collect("BTC/USD", "1D")

    request = client.get_crypto_bars.call_args[0][0]
    # CryptoBarsRequest stores start as tz-naive; compare without tz
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    start = (
        request.start
        if isinstance(request.start, datetime)
        else request.start.to_pydatetime().replace(tzinfo=None)
    )
    age = now - start
    assert 720 <= age.days <= 732  # ~2 years


# ------------------------------------------------------------------
# collect — incremental path (existing data)
# ------------------------------------------------------------------


@patch("data.collectors.alpaca_crypto.get_store")
@patch("data.collectors.alpaca_crypto._client")
def test_collect_incremental_starts_after_last_bar(mock_client, mock_get_store):
    last_ts = pd.Timestamp("2024-06-01", tz="UTC")
    existing_df = pd.DataFrame(
        {"close": [40000.0]},
        index=pd.DatetimeIndex([last_ts]),
    )

    store = MagicMock()
    store.has_symbol.return_value = True
    store.read_bars.return_value = existing_df
    mock_get_store.return_value = store

    new_ts = last_ts + timedelta(days=1)
    mock_bars = [_make_mock_bar(new_ts.to_pydatetime())]
    response = _make_response("BTC/USD", mock_bars)
    client = MagicMock()
    client.get_crypto_bars.return_value = response
    mock_client.return_value = client

    collect("BTC/USD", "1D")

    request = client.get_crypto_bars.call_args[0][0]
    req_start = pd.Timestamp(request.start).tz_localize("UTC")
    assert req_start > last_ts


@patch("data.collectors.alpaca_crypto.get_store")
@patch("data.collectors.alpaca_crypto._client")
def test_collect_skips_write_when_no_bars_returned(mock_client, mock_get_store):
    store = MagicMock()
    store.has_symbol.return_value = False
    mock_get_store.return_value = store

    response = _make_response("BTC/USD", [])  # empty .data dict
    client = MagicMock()
    client.get_crypto_bars.return_value = response
    mock_client.return_value = client

    collect("BTC/USD", "1D")

    store.write_bars.assert_not_called()


@patch("data.collectors.alpaca_crypto.get_store")
@patch("data.collectors.alpaca_crypto._client")
def test_collect_skips_when_already_up_to_date(mock_client, mock_get_store):
    """If last bar is within the last hour, no API call should be made."""
    near_now = pd.Timestamp.now(tz="UTC") - timedelta(minutes=30)
    existing_df = pd.DataFrame(
        {"close": [40000.0]},
        index=pd.DatetimeIndex([near_now]),
    )

    store = MagicMock()
    store.has_symbol.return_value = True
    store.read_bars.return_value = existing_df
    mock_get_store.return_value = store

    client = MagicMock()
    mock_client.return_value = client

    collect("BTC/USD", "1D")

    client.get_crypto_bars.assert_not_called()
