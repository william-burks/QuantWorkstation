"""Prefect flow for exporting ArcticDB data to parquet."""

from prefect import flow, task


@task
def export_all_parquet() -> None:
    from data.parquet_export import export_all

    export_all()


@flow(name="parquet-export", retries=2, retry_delay_seconds=60)
def parquet_export_flow() -> None:
    """Export all ArcticDB bars to parquet files."""
    export_all_parquet()
