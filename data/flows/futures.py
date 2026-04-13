"""Prefect flow wrapping the IBKR futures collector."""

from prefect import flow, task


@task
def collect_all_futures(timeframe: str = "1D") -> None:
    from data.collectors.ibkr_futures import collect_all

    collect_all(timeframe=timeframe)


@flow(name="futures-collection", retries=2, retry_delay_seconds=60)
def futures_collection_flow(timeframe: str = "1D") -> None:
    """Collect all futures OHLCV data from IBKR."""
    collect_all_futures(timeframe=timeframe)
