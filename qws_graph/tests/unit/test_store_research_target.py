"""Unit tests for QWS-0408 — ResearchTarget singleton node.

Covers:
- store.ensure_research_target() — first-time seed, idempotent re-seed, --set override,
  unknown key validation
- cmd_seed / qw seed --targets — CLI flag parsing, exit codes, Neo4j unavailable
"""

from __future__ import annotations

from argparse import Namespace

import pytest
from research.graph.cli import cmd_seed
from research.graph.store import (
    _RESEARCH_TARGET_DEFAULTS,
    RESEARCH_TARGET_ALLOWED_KEYS,
    StoreInfraError,
)

# ---------------------------------------------------------------------------
# Fake store
# ---------------------------------------------------------------------------


class FakeGraphStore:
    """Minimal duck-type for GraphStore used by cmd_seed."""

    def __init__(
        self,
        raise_infra: bool = False,
    ) -> None:
        self._raise_infra = raise_infra
        self.seed_calls: list[dict | None] = []

    def ensure_research_target(
        self,
        overrides: dict | None = None,
    ) -> None:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        self.seed_calls.append(overrides)

    def close(self) -> None:
        pass


class FakeNeoConnector:
    def __init__(self, available: bool = True) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


def _run_seed(
    targets: bool = True,
    sets: list[str] | None = None,
    available: bool = True,
    raise_infra: bool = False,
    monkeypatch=None,
) -> tuple[int, FakeGraphStore]:
    """Run cmd_seed with injected fakes. Returns (exit_code, store)."""
    store = FakeGraphStore(raise_infra=raise_infra)
    connector = FakeNeoConnector(available=available)

    import research.graph.cli as cli_module

    monkeypatch.setattr(cli_module, "NeoConnector", lambda **_kw: connector)
    monkeypatch.setattr(
        cli_module,
        "GraphStore",
        type(
            "FakeGS",
            (),
            {
                "from_env": staticmethod(lambda **_: store),
            },
        ),
    )

    args = Namespace(
        targets=targets,
        set=sets,
        timeout_seconds=3,
    )
    code = cmd_seed(args)
    return code, store


# ---------------------------------------------------------------------------
# Store defaults
# ---------------------------------------------------------------------------


class TestResearchTargetDefaults:
    def test_all_expected_keys_present(self) -> None:
        expected = {
            "sharpe_professional",
            "sharpe_institutional",
            "max_holding_hours",
            "min_trades",
            "min_active_window_frequency",
            "profit_factor_min",
            "calmar_min",
            "max_drawdown_floor",
            "correlation_gate",
            "decay_threshold",
        }
        assert set(_RESEARCH_TARGET_DEFAULTS) == expected

    def test_default_values(self) -> None:
        assert _RESEARCH_TARGET_DEFAULTS["sharpe_professional"] == 2.0
        assert _RESEARCH_TARGET_DEFAULTS["sharpe_institutional"] == 3.5
        assert _RESEARCH_TARGET_DEFAULTS["max_holding_hours"] == 4
        assert _RESEARCH_TARGET_DEFAULTS["min_trades"] == 30
        assert _RESEARCH_TARGET_DEFAULTS["min_active_window_frequency"] == pytest.approx(0.06)
        assert _RESEARCH_TARGET_DEFAULTS["profit_factor_min"] == pytest.approx(1.3)
        assert _RESEARCH_TARGET_DEFAULTS["calmar_min"] == pytest.approx(1.5)
        assert _RESEARCH_TARGET_DEFAULTS["max_drawdown_floor"] == pytest.approx(-0.20)
        assert _RESEARCH_TARGET_DEFAULTS["correlation_gate"] == pytest.approx(0.30)

    def test_allowed_keys_matches_defaults(self) -> None:
        assert RESEARCH_TARGET_ALLOWED_KEYS == frozenset(_RESEARCH_TARGET_DEFAULTS)


# ---------------------------------------------------------------------------
# CLI — basic seed
# ---------------------------------------------------------------------------


class TestSeedBasic:
    def test_seed_targets_exits_0(self, monkeypatch) -> None:
        code, store = _run_seed(monkeypatch=monkeypatch)
        assert code == 0

    def test_seed_calls_store_once(self, monkeypatch) -> None:
        code, store = _run_seed(monkeypatch=monkeypatch)
        assert len(store.seed_calls) == 1

    def test_seed_no_overrides_passes_none(self, monkeypatch) -> None:
        _, store = _run_seed(monkeypatch=monkeypatch)
        assert store.seed_calls[0] is None

    def test_seed_idempotent_second_call(self, monkeypatch) -> None:
        # Both calls should succeed; store tracks each call
        _, store1 = _run_seed(monkeypatch=monkeypatch)
        _, store2 = _run_seed(monkeypatch=monkeypatch)
        assert store1.seed_calls[0] is None
        assert store2.seed_calls[0] is None


# ---------------------------------------------------------------------------
# CLI — --set overrides
# ---------------------------------------------------------------------------


class TestSeedSetOverrides:
    def test_set_known_key_exits_0(self, monkeypatch) -> None:
        code, _ = _run_seed(sets=["sharpe_professional=2.5"], monkeypatch=monkeypatch)
        assert code == 0

    def test_set_passes_override_to_store(self, monkeypatch) -> None:
        _, store = _run_seed(sets=["sharpe_professional=2.5"], monkeypatch=monkeypatch)
        assert store.seed_calls[0] == {"sharpe_professional": 2.5}

    def test_set_int_key_coerces_to_int(self, monkeypatch) -> None:
        _, store = _run_seed(sets=["max_holding_hours=8"], monkeypatch=monkeypatch)
        value = store.seed_calls[0]["max_holding_hours"]
        assert value == 8
        assert isinstance(value, int)

    def test_set_multiple_keys(self, monkeypatch) -> None:
        _, store = _run_seed(
            sets=["sharpe_professional=2.5", "profit_factor_min=1.5"],
            monkeypatch=monkeypatch,
        )
        overrides = store.seed_calls[0]
        assert overrides["sharpe_professional"] == pytest.approx(2.5)
        assert overrides["profit_factor_min"] == pytest.approx(1.5)
        assert len(overrides) == 2

    def test_set_negative_value(self, monkeypatch) -> None:
        # max_drawdown_floor is legitimately negative
        code, store = _run_seed(sets=["max_drawdown_floor=-0.25"], monkeypatch=monkeypatch)
        assert code == 0
        assert store.seed_calls[0]["max_drawdown_floor"] == pytest.approx(-0.25)


# ---------------------------------------------------------------------------
# CLI — unknown key rejection
# ---------------------------------------------------------------------------


class TestSeedUnknownKey:
    def test_unknown_key_exits_1(self, monkeypatch, capsys) -> None:
        code, store = _run_seed(sets=["unknown_key=1.0"], monkeypatch=monkeypatch)
        assert code == 1

    def test_unknown_key_no_store_call(self, monkeypatch) -> None:
        _, store = _run_seed(sets=["unknown_key=1.0"], monkeypatch=monkeypatch)
        assert len(store.seed_calls) == 0

    def test_unknown_key_prints_error(self, monkeypatch, capsys) -> None:
        _run_seed(sets=["unknown_key=1.0"], monkeypatch=monkeypatch)
        err = capsys.readouterr().err
        assert "unknown_key" in err
        assert "ERROR" in err

    def test_unknown_key_lists_allowed_keys(self, monkeypatch, capsys) -> None:
        _run_seed(sets=["bad_key=99"], monkeypatch=monkeypatch)
        err = capsys.readouterr().err
        for key in RESEARCH_TARGET_ALLOWED_KEYS:
            assert key in err


# ---------------------------------------------------------------------------
# CLI — infrastructure errors
# ---------------------------------------------------------------------------


class TestSeedInfra:
    def test_neo4j_unavailable_exits_2(self, monkeypatch) -> None:
        code, store = _run_seed(available=False, monkeypatch=monkeypatch)
        assert code == 2
        assert len(store.seed_calls) == 0

    def test_infra_error_from_store_exits_2(self, monkeypatch, capsys) -> None:
        code, _ = _run_seed(raise_infra=True, monkeypatch=monkeypatch)
        assert code == 2
        assert "ERROR" in capsys.readouterr().err

    def test_no_targets_flag_exits_1(self, monkeypatch, capsys) -> None:
        code, store = _run_seed(targets=False, monkeypatch=monkeypatch)
        assert code == 1
        assert len(store.seed_calls) == 0
        assert "--targets" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Store method — direct unit tests (no Neo4j)
# ---------------------------------------------------------------------------


class TestEnsureResearchTargetStore:
    def test_unknown_key_raises_value_error(self) -> None:
        from research.graph.store import GraphStore

        # We can't call the real method without Neo4j, but we can test the
        # validation branch via a thin wrapper.
        class _FakeDriver:
            def session(self, **_kw):
                raise AssertionError("should not reach Neo4j for validation errors")

        store = GraphStore.__new__(GraphStore)
        store._database = "neo4j"
        store._driver = _FakeDriver()

        with pytest.raises(ValueError, match="Unknown ResearchTarget keys"):
            store.ensure_research_target(overrides={"invalid_key": 1.0})

    def test_known_key_does_not_raise_before_neo4j(self) -> None:
        from research.graph.store import GraphStore

        call_log: list = []

        class _FakeSession:
            def execute_write(self, fn):
                call_log.append("write")

                class _FakeTx:
                    def run(self, *a, **kw):
                        class _FakeResult:
                            def consume(self):
                                pass

                        return _FakeResult()

                fn(_FakeTx())

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        class _FakeDriver:
            def session(self, **_kw):
                return _FakeSession()

        store = GraphStore.__new__(GraphStore)
        store._database = "neo4j"
        store._driver = _FakeDriver()

        # Should not raise — calls write, not validation error
        store.ensure_research_target(overrides={"sharpe_professional": 2.5})
        assert len(call_log) == 1
