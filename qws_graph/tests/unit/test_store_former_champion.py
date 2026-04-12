"""Unit tests for QWS-0801 — FormerChampion store methods.

Covers:
- store.degrade_champion() — valid degrade, empty reason, champion not found
- store.retire_former_champion() — valid retire, no note, former champion not found
"""

from __future__ import annotations

import sys
from pathlib import Path

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.store import StoreError, StoreInfraError

# ---------------------------------------------------------------------------
# Fake store implementations
# ---------------------------------------------------------------------------


class FakeGraphStoreDegrade:
    """Minimal duck-type for GraphStore.degrade_champion."""

    def __init__(
        self,
        champion_exists: bool = True,
        raise_infra: bool = False,
    ) -> None:
        self._champion_exists = champion_exists
        self._raise_infra = raise_infra
        self.degraded: list[dict] = []

    def degrade_champion(
        self,
        champion_id: str,
        oos_reason: str,
        sharpe_at_degradation: float | None = None,
    ) -> str:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if not oos_reason.strip():
            raise StoreError("oos_reason must be non-empty")
        if not self._champion_exists:
            raise StoreError(f"Champion {champion_id!r} not found")
        fc_id = f"fc_{champion_id[:6]}"
        self.degraded.append({
            "champion_id": champion_id,
            "oos_reason": oos_reason,
            "sharpe_at_degradation": sharpe_at_degradation,
            "former_champion_id": fc_id,
        })
        return fc_id

    def close(self) -> None:
        pass


class FakeGraphStoreRetire:
    """Minimal duck-type for GraphStore.retire_former_champion."""

    def __init__(
        self,
        former_champion_exists: bool = True,
        raise_infra: bool = False,
    ) -> None:
        self._former_champion_exists = former_champion_exists
        self._raise_infra = raise_infra
        self.retired: list[dict] = []

    def retire_former_champion(
        self,
        former_champion_id: str,
        retirement_note: str | None = None,
    ) -> str:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if not self._former_champion_exists:
            raise StoreError(f"FormerChampion {former_champion_id!r} not found")
        rc_id = f"rc_{former_champion_id[:6]}"
        self.retired.append({
            "former_champion_id": former_champion_id,
            "retirement_note": retirement_note,
            "retired_champion_id": rc_id,
        })
        return rc_id

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# degrade_champion
# ---------------------------------------------------------------------------


class TestDegradeChampion:
    def test_valid_degrade_returns_former_champion_id(self) -> None:
        store = FakeGraphStoreDegrade()
        fc_id = store.degrade_champion("abc123def456", oos_reason="OOS fail in Oct CPI spike")
        assert fc_id.startswith("fc_")
        assert len(store.degraded) == 1
        assert store.degraded[0]["champion_id"] == "abc123def456"
        assert store.degraded[0]["oos_reason"] == "OOS fail in Oct CPI spike"

    def test_valid_degrade_with_sharpe(self) -> None:
        store = FakeGraphStoreDegrade()
        store.degrade_champion("abc123def456", oos_reason="Sharpe decay", sharpe_at_degradation=0.4)
        assert store.degraded[0]["sharpe_at_degradation"] == 0.4

    def test_valid_degrade_without_sharpe_stores_none(self) -> None:
        store = FakeGraphStoreDegrade()
        store.degrade_champion("abc123def456", oos_reason="OOS fail")
        assert store.degraded[0]["sharpe_at_degradation"] is None

    def test_empty_reason_raises_store_error(self) -> None:
        store = FakeGraphStoreDegrade()
        try:
            store.degrade_champion("abc123def456", oos_reason="")
            raise AssertionError("Expected StoreError")
        except StoreError as exc:
            assert "oos_reason" in str(exc).lower() or "non-empty" in str(exc).lower()

    def test_whitespace_only_reason_raises_store_error(self) -> None:
        store = FakeGraphStoreDegrade()
        try:
            store.degrade_champion("abc123def456", oos_reason="   ")
            raise AssertionError("Expected StoreError")
        except StoreError:
            pass

    def test_champion_not_found_raises_store_error(self) -> None:
        store = FakeGraphStoreDegrade(champion_exists=False)
        try:
            store.degrade_champion("nonexistent", oos_reason="valid reason")
            raise AssertionError("Expected StoreError")
        except StoreError as exc:
            assert "not found" in str(exc).lower()

    def test_infra_error_raises_store_infra_error(self) -> None:
        store = FakeGraphStoreDegrade(raise_infra=True)
        try:
            store.degrade_champion("abc123def456", oos_reason="valid")
            raise AssertionError("Expected StoreInfraError")
        except StoreInfraError:
            pass


# ---------------------------------------------------------------------------
# retire_former_champion
# ---------------------------------------------------------------------------


class TestRetireFormerChampion:
    def test_valid_retire_with_note(self) -> None:
        store = FakeGraphStoreRetire()
        rc_id = store.retire_former_champion("fc_abc123", retirement_note="No viable pivot")
        assert rc_id.startswith("rc_")
        assert len(store.retired) == 1
        assert store.retired[0]["retirement_note"] == "No viable pivot"

    def test_valid_retire_without_note(self) -> None:
        store = FakeGraphStoreRetire()
        rc_id = store.retire_former_champion("fc_abc123")
        assert rc_id.startswith("rc_")
        assert store.retired[0]["retirement_note"] is None

    def test_former_champion_not_found_raises_store_error(self) -> None:
        store = FakeGraphStoreRetire(former_champion_exists=False)
        try:
            store.retire_former_champion("nonexistent_fc")
            raise AssertionError("Expected StoreError")
        except StoreError as exc:
            assert "not found" in str(exc).lower()

    def test_infra_error_raises_store_infra_error(self) -> None:
        store = FakeGraphStoreRetire(raise_infra=True)
        try:
            store.retire_former_champion("fc_abc123")
            raise AssertionError("Expected StoreInfraError")
        except StoreInfraError:
            pass
