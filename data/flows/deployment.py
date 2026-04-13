"""Register Prefect deployments for all scheduled collection flows.

Run this script with a Prefect server running to register all 4 deployments:
    python data/flows/deployment.py

Deployments registered:
  1. crypto-daily     — crypto-collection flow, daily at 00:15 UTC
  2. crypto-hourly    — crypto-collection flow, hourly at :05
  3. futures-daily    — futures-collection flow, daily at 01:00 UTC
  4. parquet-export   — parquet-export flow, daily at 02:00 UTC
"""

from prefect.client.schemas.schedules import CronSchedule

from data.flows.crypto import crypto_collection_flow
from data.flows.futures import futures_collection_flow
from data.flows.parquet import parquet_export_flow


def register_deployments() -> None:
    crypto_collection_flow.serve(
        name="crypto-daily",
        schedules=[CronSchedule(cron="15 0 * * *", timezone="UTC")],
        parameters={"timeframe": "daily"},
    )


def _build_all() -> None:
    """Build and apply all 4 deployments to a running Prefect server."""
    import asyncio

    from prefect.deployments import Deployment

    deployments = [
        Deployment.build_from_flow(
            flow=crypto_collection_flow,
            name="crypto-daily",
            schedule=CronSchedule(cron="15 0 * * *", timezone="UTC"),
            parameters={"timeframe": "daily"},
        ),
        Deployment.build_from_flow(
            flow=crypto_collection_flow,
            name="crypto-hourly",
            schedule=CronSchedule(cron="5 * * * *", timezone="UTC"),
            parameters={"timeframe": "1H"},
        ),
        Deployment.build_from_flow(
            flow=futures_collection_flow,
            name="futures-daily",
            schedule=CronSchedule(cron="0 1 * * *", timezone="UTC"),
            parameters={"timeframe": "1D"},
        ),
        Deployment.build_from_flow(
            flow=parquet_export_flow,
            name="parquet-export",
            schedule=CronSchedule(cron="0 2 * * *", timezone="UTC"),
        ),
    ]

    async def _apply_all() -> None:
        for dep in deployments:
            dep_id = await dep.apply()
            print(f"Registered deployment: {dep.name} ({dep_id})")

    asyncio.run(_apply_all())


if __name__ == "__main__":
    _build_all()
