"""Prefect flow wrapping all macro/alternative data collectors."""

from prefect import flow, task


@task
def collect_cot() -> None:
    from data.collectors.cot import collect

    collect()


@task
def collect_fred() -> None:
    from data.collectors.fred import collect

    collect()


@task
def collect_eia() -> None:
    from data.collectors.eia import collect

    collect()


@task
def collect_baker_hughes() -> None:
    from data.collectors.baker_hughes import collect

    collect()


@task
def collect_google_trends() -> None:
    from data.collectors.google_trends import collect

    collect()


@task
def collect_bdti() -> None:
    from data.collectors.bdti import collect

    collect()


@task
def collect_economic_calendar() -> None:
    from data.collectors.economic_calendar import collect

    collect()


@flow(name="macro-collection", retries=1, retry_delay_seconds=120)
def macro_collection_flow() -> None:
    """Collect all macro and alternative data sources."""
    collect_cot()
    collect_fred()
    collect_eia()
    collect_baker_hughes()
    collect_google_trends()
    collect_bdti()
    collect_economic_calendar()
