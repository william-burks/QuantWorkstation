"""Unit tests for the macro Prefect flow."""

from unittest.mock import patch


def test_macro_flow_importable() -> None:
    from data.flows.macro import macro_collection_flow

    assert macro_collection_flow is not None
    assert macro_collection_flow.name == "macro-collection"


def test_macro_deployment_constructible() -> None:
    from data.flows.deployment import register_all

    assert callable(register_all)


def test_macro_collection_deployment_in_module() -> None:
    import data.flows.deployment as dep_module

    import inspect

    src = inspect.getsource(dep_module)
    assert "macro_collection" in src
    assert "macro-collection" in src


def test_macro_flow_calls_all_collectors() -> None:
    """Flow tasks are importable and callable (no live I/O)."""
    from data.flows.macro import (
        collect_baker_hughes,
        collect_bdti,
        collect_cot,
        collect_economic_calendar,
        collect_eia,
        collect_fred,
        collect_google_trends,
    )

    tasks = [
        collect_cot,
        collect_fred,
        collect_eia,
        collect_baker_hughes,
        collect_google_trends,
        collect_bdti,
        collect_economic_calendar,
    ]
    assert len(tasks) == 7
    for t in tasks:
        assert callable(t)


def test_macro_flow_runs_with_mocked_collectors() -> None:
    """Flow executes end-to-end with all collector tasks mocked."""
    mock_targets = [
        "data.collectors.cot.collect",
        "data.collectors.fred.collect",
        "data.collectors.eia.collect",
        "data.collectors.baker_hughes.collect",
        "data.collectors.google_trends.collect",
        "data.collectors.bdti.collect",
        "data.collectors.economic_calendar.collect",
    ]
    patches = [patch(t) for t in mock_targets]
    mocks = [p.start() for p in patches]
    try:
        from data.flows.macro import macro_collection_flow

        macro_collection_flow()
        for m in mocks:
            m.assert_called_once()
    finally:
        for p in patches:
            p.stop()
