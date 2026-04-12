"""Unit tests for QWS-0801 — FormerChampion lifecycle store methods.

Covers:
- GraphStore.degrade_champion() — valid, empty reason, champion not found, infra error
- GraphStore.retire_former_champion() — valid (with note), valid (without note),
  former champion not found, infra error
- GraphStore.get_former_champions() — returns list, infra error
"""

from __future__ import annotations

import sys
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.store import StoreError, StoreInfraError

# ---------------------------------------------------------------------------
# Fake store helpers (bypass Neo4j)
# ---------------------------------------------------------------------------


class FakeGraphStoreDegradeRetire:
    """Minimal duck-type for GraphStore covering degrade/retire/get_former methods."""

    def __init__(
        self,
        champion_exists: bool = True,
        former_champion_exists: bool = True,
        raise_infra: bool = False,
    ) -> None:
        self._champion_exists = champion_exists
        self._former_champion_exists = former_champion_exists
        self._raise_infra = raise_infra
        self.degraded: list[dict] = []
        self.retired: list[dict] = []

    def degrade_champion(
        self,
        champion_id: str,
        oos_reason: str,
        metrics_sharpe_at_degradation: float | None = None,
    ) -> str:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if not oos_reason.strip():
            raise StoreError("oos_reason must be a non-empty string")
        if not self._champion_exists:
            raise StoreError(f"Champion {champion_id!r} not found in graph")
        fc_id = f"fc_{champion_id[:8]}"
        self.degraded.append({
            "champion_id": champion_id,
            "oos_reason": oos_reason,
            "metrics_sharpe_at_degradation": metrics_sharpe_at_degradation,
            "former_champion_id": fc_id,
        })
        return fc_id

    def retire_former_champion(
        self,
        former_champion_id: str,
        retirement_note: str | None = None,
    ) -> str:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if not self._former_champion_exists:
            raise StoreError(f"FormerChampion {former_champion_id!r} not found in graph")
        rc_id = f"rc_{former_champion_id[:8]}"
        self.retired.append({
            "former_champion_id": former_champion_id,
            "retirement_note": retirement_note,
            "retired_champion_id": rc_id,
        })
        return rc_id

    def get_former_champions(self) -> list[dict]:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        return [
            {
                "former_champion_id": "demo_fc_001",
                "strategy_id": "demo-strategy-beta",
                "instrument": "ES",
                "degraded_at": "2026-04-08T12:00:00+00:00",
                "oos_reason": "MaxDD breached",
                "retirement_note": None,
                "status": "DEGRADED",
            }
        ]

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# degrade_champion tests
# ---------------------------------------------------------------------------


class TestDegradeChampion:
    def test_valid_degrade_returns_fc_id(self) -> None:
        store = FakeGraphStoreDegradeRetire()
        fc_id = store.degrade_champion("abc123def456", "MaxDD breached -15%")
        assert fc_id.startswith("fc_")
        assert len(store.degraded) == 1
        assert store.degraded[0]["oos_reason"] == "MaxDD breached -15%"

    def test_sharpe_stored_when_passed(self) -> None:
        store = FakeGraphStoreDegradeRetire()
        store.degrade_champion("abc123def456", "reason", metrics_sharpe_at_degradation=1.8)
        assert store.degraded[0]["metrics_sharpe_at_degradation"] == 1.8

    def test_sharpe_none_when_omitted(self) -> None:
        store = FakeGraphStoreDegradeRetire()
        store.degrade_champion("abc123def456", "reason")
        assert store.degraded[0]["metrics_sharpe_at_degradation"] is None

    def test_empty_reason_raises_store_error(self) -> None:
        store = FakeGraphStoreDegradeRetire()
        try:
            store.degrade_champion("abc123def456", "")
            assert False, "expected StoreError"
        except StoreError as exc:
            assert "oos_reason" in str(exc).lower() or "non-empty" in str(exc).lower()

    def test_whitespace_only_reason_raises_store_error(self) -> None:
        store = FakeGraphStoreDegradeRetire()
        try:
            store.degrade_champion("abc123def456", "   ")
            assert False, "expected StoreError"
        except StoreError:
            pass

    def test_champion_not_found_raises_store_error(self) -> None:
        store = FakeGraphStoreDegradeRetire(champion_exists=False)
        try:
            store.degrade_champion("nonexistent", "reason")
            assert False, "expected StoreError"
        except StoreError as exc:
            assert "not found" in str(exc).lower()

    def test_infra_error_raises_store_infra_error(self) -> None:
        store = FakeGraphStoreDegradeRetire(raise_infra=True)
        try:
            store.degrade_champion("abc123def456", "reason")
            assert False, "expected StoreInfraError"
        except StoreInfraError:
            pass


# ---------------------------------------------------------------------------
# retire_former_champion tests
# ---------------------------------------------------------------------------


class TestRetireFormerChampion:
    def test_valid_retire_with_note(self) -> None:
        store = FakeGraphStoreDegradeRetire()
        rc_id = store.retire_former_champion("fc_001", retirement_note="No pivot hypothesis")
        assert rc_id.startswith("rc_")
        assert store.retired[0]["retirement_note"] == "No pivot hypothesis"

    def test_valid_retire_without_note(self) -> None:
        store = FakeGraphStoreDegradeRetire()
        rc_id = store.retire_former_champion("fc_001")
        assert rc_id.startswith("rc_")
        assert store.retired[0]["retirement_note"] is None

    def test_former_champion_not_found_raises_store_error(self) -> None:
        store = FakeGraphStoreDegradeRetire(former_champion_exists=False)
        try:
            store.retire_former_champion("nonexistent")
            assert False, "expected StoreError"
        except StoreError as exc:
            assert "not found" in str(exc).lower()

    def test_infra_error_raises_store_infra_error(self) -> None:
        store = FakeGraphStoreDegradeRetire(raise_infra=True)
        try:
            store.retire_former_champion("fc_001")
            assert False, "expected StoreInfraError"
        except StoreInfraError:
            pass


# ---------------------------------------------------------------------------
# get_former_champions tests
# ---------------------------------------------------------------------------


class TestGetFormerChampions:
    def test_returns_list(self) -> None:
        store = FakeGraphStoreDegradeRetire()
        results = store.get_former_champions()
        assert isinstance(results, list)
        assert len(results) == 1

    def test_row_has_required_keys(self) -> None:
        store = FakeGraphStoreDegradeRetire()
        row = store.get_former_champions()[0]
        required = {"former_champion_id", "strategy_id", "instrument",
                    "degraded_at", "oos_reason", "retirement_note", "status"}
        assert required.issubset(row.keys())

    def test_degraded_status(self) -> None:
        store = FakeGraphStoreDegradeRetire()
        row = store.get_former_champions()[0]
        assert row["status"] == "DEGRADED"
        assert row["retirement_note"] is None

    def test_infra_error_raises(self) -> None:
        store = FakeGraphStoreDegradeRetire(raise_infra=True)
        try:
            store.get_former_champions()
            assert False, "expected StoreInfraError"
        except StoreInfraError:
            pass
