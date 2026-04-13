"""Register Prefect deployments for all scheduled collection flows.

Run this script with a Prefect server running to register all 4 deployments:
    python data/flows/deployment.py

Deployments registered:
  1. crypto-daily     — crypto-collection flow, daily at 00:15 UTC
  2. crypto-hourly    — crypto-collection flow, hourly at :05
  3. futures-daily    — futures-collection flow, daily at 01:00 UTC
  4. parquet-export   — parquet-export flow, daily at 02:00 UTC
"""

from prefect import serve
from prefect.deployments.runner import RunnerDeployment

from data.flows.crypto import crypto_collection_flow
from data.flows.futures import futures_collection_flow
from data.flows.parquet import parquet_export_flow


def register_all() -> None:
    """Build and serve all 4 deployments against a running Prefect server."""
    # to_deployment is async_dispatch — callable synchronously; cast narrows union
    crypto_daily: RunnerDeployment = crypto_collection_flow.to_deployment(  # type: ignore[assignment]
        name="crypto-daily",
        cron="15 0 * * *",
        parameters={"timeframe": "daily"},
    )
    crypto_hourly: RunnerDeployment = crypto_collection_flow.to_deployment(  # type: ignore[assignment]
        name="crypto-hourly",
        cron="5 * * * *",
        parameters={"timeframe": "1H"},
    )
    futures_daily: RunnerDeployment = futures_collection_flow.to_deployment(  # type: ignore[assignment]
        name="futures-daily",
        cron="0 1 * * *",
        parameters={"timeframe": "1D"},
    )
    parquet_export: RunnerDeployment = parquet_export_flow.to_deployment(  # type: ignore[assignment]
        name="parquet-export",
        cron="0 2 * * *",
    )
    serve(crypto_daily, crypto_hourly, futures_daily, parquet_export)


if __name__ == "__main__":
    register_all()
