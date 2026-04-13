"""Prefect flow wrapping the Alpaca crypto collector."""

from prefect import flow, task


@task
def collect_all_crypto(timeframe: str = "daily") -> None:
    from data.collectors.alpaca_crypto import collect_all

    collect_all(timeframe=timeframe)


@flow(name="crypto-collection", retries=2, retry_delay_seconds=60)
def crypto_collection_flow(timeframe: str = "daily") -> None:
    """Collect all crypto OHLCV data from Alpaca."""
    collect_all_crypto(timeframe=timeframe)
