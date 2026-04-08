"""Unit tests for QWS-0402 — OOS outcome tracking.

Covers:
- store.update_champion_oos_status() — valid transition, lifecycle conflict (retired),
  champion not found
- _cmd_oos_update / cmd_record --oos — CLI flag parsing, exit codes, receipt writing
"""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest

QWS_GRAPH_ROOT = Path(__file__).resolve().parents[2]
if str(QWS_GRAPH_ROOT) not in sys.path:
    sys.path.insert(0, str(QWS_GRAPH_ROOT))

from research.graph.cli import cmd_record, _VALID_OOS_STATUSES
from research.graph.store import StoreError, StoreInfraError


# ---------------------------------------------------------------------------
# Fake store
# ---------------------------------------------------------------------------

class FakeGraphStore:
    """Minimal duck-type for GraphStore used by _cmd_oos_update."""

    def __init__(
        self,
        champion_exists: bool = True,
        current_oos_status: str = "oos_pending",
        raise_infra: bool = False,
    ) -> None:
        self._champion_exists = champion_exists
        self._current_oos_status = current_oos_status
        self._raise_infra = raise_infra
        self.updates: list[dict] = []

    def update_champion_oos_status(
        self,
        champion_id: str,
        status: str,
        oos_date: str | None = None,
    ) -> bool:
        if self._raise_infra:
            raise StoreInfraError("fake infra failure")
        if self._current_oos_status == "retired":
            raise StoreError(
                f"Champion {champion_id!r} has lifecycle status 'retired'; "
                "use qw retire instead"
            )
        if not self._champion_exists:
            return False
        self.updates.append({
            "champion_id": champion_id,
            "status": status,
            "oos_date": oos_date,
        })
        return True

    def close(self) -> None:
        pass


class FakeNeoConnector:
    def __init__(self, available: bool = True) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


def _run_oos(
    oos_status: str = "oos_pass",
    champion_id: str = "abc123def456",
    available: bool = True,
    champion_exists: bool = True,
    current_oos_status: str = "oos_pending",
    raise_infra: bool = False,
    tmp_path: Path | None = None,
    monkeypatch=None,
) -> tuple[int, FakeGraphStore]:
    """Run cmd_record --oos with injected fakes. Returns (exit_code, store)."""
    store = FakeGraphStore(
        champion_exists=champion_exists,
        current_oos_status=current_oos_status,
        raise_infra=raise_infra,
    )
    connector = FakeNeoConnector(available=available)

    import research.graph.cli as cli_module

    monkeypatch.setattr(cli_module, "NeoConnector", lambda **_kw: connector)
    monkeypatch.setattr(
        cli_module,
        "GraphStore",
        type("FakeGS", (), {
            "from_env": staticmethod(lambda **_: store),
        }),
    )

    args = Namespace(
        oos=oos_status,
        champion=champion_id,
        bundle=None,
        file=None,
        timeout_seconds=3,
        repo_root=str(tmp_path) if tmp_path else None,
    )
    code = cmd_record(args)
    return code, store


# ---------------------------------------------------------------------------
# Store method — valid transitions
# ---------------------------------------------------------------------------

class TestUpdateChampionOosStatusStore:
    def test_oos_pass_returns_exit_0(self, monkeypatch, tmp_path) -> None:
        code, store = _run_oos(oos_status="oos_pass", monkeypatch=monkeypatch, tmp_path=tmp_path)
        assert code == 0
        assert len(store.updates) == 1
        assert store.updates[0]["status"] == "oos_pass"

    def test_oos_fail_returns_exit_0(self, monkeypatch, tmp_path) -> None:
        code, store = _run_oos(oos_status="oos_fail", monkeypatch=monkeypatch, tmp_path=tmp_path)
        assert code == 0
        assert store.updates[0]["status"] == "oos_fail"

    def test_oos_pending_returns_exit_0(self, monkeypatch, tmp_path) -> None:
        code, store = _run_oos(oos_status="oos_pending", monkeypatch=monkeypatch, tmp_path=tmp_path)
        assert code == 0
        assert store.updates[0]["status"] == "oos_pending"

    def test_champion_not_found_returns_1(self, monkeypatch, tmp_path, capsys) -> None:
        code, store = _run_oos(
            champion_exists=False,
            monkeypatch=monkeypatch,
            tmp_path=tmp_path,
        )
        assert code == 1
        assert len(store.updates) == 0
        assert "not found" in capsys.readouterr().err.lower()

    def test_retired_champion_returns_1(self, monkeypatch, tmp_path, capsys) -> None:
        code, store = _run_oos(
            current_oos_status="retired",
            monkeypatch=monkeypatch,
            tmp_path=tmp_path,
        )
        assert code == 1
        assert len(store.updates) == 0
        assert "retired" in capsys.readouterr().err.lower()

    def test_infra_error_returns_2(self, monkeypatch, tmp_path, capsys) -> None:
        code, _ = _run_oos(raise_infra=True, monkeypatch=monkeypatch, tmp_path=tmp_path)
        assert code == 2
        assert "ERROR" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# CLI validation
# ---------------------------------------------------------------------------

class TestOosCliValidation:
    def test_invalid_status_returns_1(self, monkeypatch, tmp_path, capsys) -> None:
        code, store = _run_oos(
            oos_status="bad_status",
            monkeypatch=monkeypatch,
            tmp_path=tmp_path,
        )
        assert code == 1
        assert len(store.updates) == 0
        assert "invalid" in capsys.readouterr().err.lower()

    def test_invalid_status_lists_valid_values(self, monkeypatch, tmp_path, capsys) -> None:
        _run_oos(oos_status="garbage", monkeypatch=monkeypatch, tmp_path=tmp_path)
        err = capsys.readouterr().err
        for valid in _VALID_OOS_STATUSES:
            assert valid in err

    def test_missing_champion_returns_1(self, monkeypatch, tmp_path, capsys) -> None:
        store = FakeGraphStore()
        connector = FakeNeoConnector()

        import research.graph.cli as cli_module
        monkeypatch.setattr(cli_module, "NeoConnector", lambda **_kw: connector)
        monkeypatch.setattr(
            cli_module,
            "GraphStore",
            type("FakeGS", (), {"from_env": staticmethod(lambda **_: store)}),
        )

        args = Namespace(
            oos="oos_pass",
            champion=None,
            bundle=None,
            file=None,
            timeout_seconds=3,
            repo_root=str(tmp_path),
        )
        code = cmd_record(args)
        assert code == 1
        assert "--champion" in capsys.readouterr().err

    def test_neo4j_unavailable_returns_2(self, monkeypatch, tmp_path) -> None:
        code, store = _run_oos(available=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
        assert code == 2
        assert len(store.updates) == 0


# ---------------------------------------------------------------------------
# Receipt
# ---------------------------------------------------------------------------

class TestOosReceipt:
    def test_receipt_written_on_success(self, monkeypatch, tmp_path) -> None:
        code, _ = _run_oos(
            oos_status="oos_pass",
            champion_id="abc123def456",
            monkeypatch=monkeypatch,
            tmp_path=tmp_path,
        )
        assert code == 0
        receipt_files = list((tmp_path / ".qws" / "receipts").glob("*.json"))
        assert len(receipt_files) == 1

    def test_receipt_kind_and_status(self, monkeypatch, tmp_path) -> None:
        _run_oos(
            oos_status="oos_pass",
            champion_id="abc123def456",
            monkeypatch=monkeypatch,
            tmp_path=tmp_path,
        )
        receipt = json.loads((tmp_path / ".qws" / "receipts" / "abc123def456.json").read_text())
        assert receipt["kind"] == "oos_update"
        assert receipt["status"] == "persisted"

    def test_no_receipt_on_failure(self, monkeypatch, tmp_path) -> None:
        _run_oos(champion_exists=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
        receipts_dir = tmp_path / ".qws" / "receipts"
        assert not receipts_dir.exists() or len(list(receipts_dir.glob("*.json"))) == 0


# ---------------------------------------------------------------------------
# Valid status enum
# ---------------------------------------------------------------------------

class TestValidOosStatuses:
    def test_expected_values(self) -> None:
        assert _VALID_OOS_STATUSES == {"oos_pending", "oos_pass", "oos_fail"}

    def test_old_enum_values_excluded(self) -> None:
        assert "live_paper" not in _VALID_OOS_STATUSES
        assert "retired" not in _VALID_OOS_STATUSES