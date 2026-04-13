# mypy: ignore-errors
"""Unit tests for evolutionary run deduplication and champion auto-promotion."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from research.graph.store import (
    _INSTITUTIONAL_SHARPE_THRESHOLD,
    _PROFESSIONAL_SHARPE_THRESHOLD,
    EvolutionOutcome,
    GraphStore,
    StoreResult,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_store() -> GraphStore:
    with patch("research.graph.store.GraphDatabase.driver"):
        return GraphStore(uri="bolt://localhost:7687", username="neo4j", password="password")


def _make_tx_with_single(record: dict | None):
    class FakeTx:
        def run(self, *args, **kwargs):
            result = MagicMock()
            result.single.return_value = record
            return result

    return FakeTx()


def _make_artifact(sharpe: float = 1.5, total_trades: int = 30):
    from datetime import UTC, datetime

    from research.graph.models import Config, Provenance, ResearchArtifact, Run, Strategy

    prov = Provenance(
        artifact_path="research/results/test/result.csv",
        artifact_hash="deadbeef" * 8,
        artifact_mtime_iso="2026-04-05T10:00:00Z",
        ingested_at=datetime(2026, 4, 5, 10, 0, 0, tzinfo=UTC),
        parser_version="v1",
    )
    run = Run(
        run_id="aabbcc112233",
        strategy_id="cl-1h-bear-liquidity-sweep",
        timestamp=datetime(2026, 4, 5, tzinfo=UTC),
        sharpe=sharpe,
        profit_factor=1.8,
        win_rate=0.55,
        max_drawdown=-0.08,
        total_trades=total_trades,
        first_trade_ts=datetime(2024, 1, 2, 10, 0, 0, tzinfo=UTC),
        last_trade_ts=datetime(2025, 10, 1, 16, 0, 0, tzinfo=UTC),
        artifact_path="research/results/test/result.csv",
        provenance=prov,
    )
    config = Config(config_id="fedcba987654", params_json={}, risk_params={})
    strategy = Strategy(
        strategy_id="cl-1h-bear-liquidity-sweep",
        instrument="CL",
        timeframe="1H",
        direction="bear",
        logic_type="liquidity-sweep",
    )
    return ResearchArtifact(kind="baseline_csv", strategy=strategy, runs=[run], configs=[config])


# ── _check_run_redundancy ─────────────────────────────────────────────────────


class TestCheckRunRedundancy:
    def test_returns_false_when_no_competing_run(self):
        store = _make_store()
        fake_session = MagicMock()
        fake_session.execute_read.side_effect = lambda fn: fn(
            _make_tx_with_single({"is_redundant": False})
        )
        assert (
            store._check_run_redundancy(
                fake_session, "cl-1h-bear", "abc123", 30, 2.0, "2026-04-05T00:00:00+00:00"
            )
            is False
        )

    def test_returns_true_when_better_run_exists(self):
        store = _make_store()
        fake_session = MagicMock()
        fake_session.execute_read.side_effect = lambda fn: fn(
            _make_tx_with_single({"is_redundant": True})
        )
        assert (
            store._check_run_redundancy(
                fake_session, "cl-1h-bear", "abc123", 30, 2.0, "2026-04-05T00:00:00+00:00"
            )
            is True
        )

    def test_returns_false_when_no_strategy_exists(self):
        store = _make_store()
        fake_session = MagicMock()
        fake_session.execute_read.side_effect = lambda fn: fn(_make_tx_with_single(None))
        assert (
            store._check_run_redundancy(
                fake_session, "new-strategy", "abc123", 5, 1.5, "2026-04-05T00:00:00+00:00"
            )
            is False
        )


# ── _maybe_auto_promote_champion ──────────────────────────────────────────────


class TestMaybeAutoPromoteChampion:
    def _make_run_data(self, sharpe: float = 3.0, total_trades: int = 20) -> dict:
        return {
            "run_id": "newrun123",
            "sharpe": sharpe,
            "profit_factor": 1.9,
            "win_rate": 0.60,
            "max_drawdown": -0.05,
            "total_trades": total_trades,
            "total_r": 0.12,
            "artifact_path": "research/results/test/result.csv",
        }

    def test_does_not_promote_below_professional_threshold(self):
        store = _make_store()
        fake_session = MagicMock()
        run_data = self._make_run_data(sharpe=_PROFESSIONAL_SHARPE_THRESHOLD - 0.1)

        result = store._maybe_auto_promote_champion(fake_session, "s-x", run_data, 5.0)

        assert result is None
        fake_session.execute_read.assert_not_called()

    def test_does_not_promote_fail_tier(self):
        """Explicit tier='fail' in run_data blocks promotion regardless of sharpe."""
        store = _make_store()
        fake_session = MagicMock()
        run_data = {**self._make_run_data(sharpe=4.0), "tier": "fail"}

        result = store._maybe_auto_promote_champion(fake_session, "s-x", run_data, 20.0)

        assert result is None
        fake_session.execute_read.assert_not_called()

    def test_promotes_when_no_existing_champion(self):
        store = _make_store()
        fake_session = MagicMock()
        # First execute_read: current champion query → None (no existing champion).
        # Second execute_read: read-back after write → return the persisted ID.
        _readback_id = "ab12cd34ef56"  # 12-char stub
        _read_call = [0]

        def _side_effect(fn):
            _read_call[0] += 1
            if _read_call[0] == 1:
                return fn(_make_tx_with_single(None))
            # read-back after write
            return fn(_make_tx_with_single({"champion_id": _readback_id}))

        fake_session.execute_read.side_effect = _side_effect
        fake_session.execute_write = MagicMock()

        champion_id = store._maybe_auto_promote_champion(
            fake_session, "s-x", self._make_run_data(3.0, 20), 3.0 * (20**0.5)
        )

        assert champion_id is not None and len(champion_id) == 12
        fake_session.execute_write.assert_called_once()

    def test_promotes_when_evidence_beats_existing_champion(self):
        store = _make_store()
        fake_session = MagicMock()
        fake_session.execute_read.side_effect = lambda fn: fn(
            _make_tx_with_single(
                {
                    "champion_id": "oldchamp123",
                    "evidence_score": 15.0,
                    "auto_promoted": True,
                }
            )
        )
        fake_session.execute_write = MagicMock()

        champion_id = store._maybe_auto_promote_champion(
            fake_session, "s-x", self._make_run_data(3.5, 33), 20.0
        )

        assert champion_id is not None
        fake_session.execute_write.assert_called_once()

    def test_does_not_auto_promote_over_manual_champion(self):
        """A manually-curated champion_md must never be overridden by auto-promote."""
        store = _make_store()
        fake_session = MagicMock()
        # auto_promoted is absent (manually curated champion_md)
        fake_session.execute_read.side_effect = lambda fn: fn(
            _make_tx_with_single(
                {
                    "champion_id": "manual_champ",
                    "evidence_score": 15.0,
                    "auto_promoted": None,
                }
            )
        )

        result = store._maybe_auto_promote_champion(
            fake_session,
            "s-x",
            self._make_run_data(4.5, 33),
            25.0,  # beats evidence=15
        )

        assert result is None
        fake_session.execute_write.assert_not_called()

    def test_does_not_promote_when_evidence_matches_or_lower(self):
        store = _make_store()
        fake_session = MagicMock()
        fake_session.execute_read.side_effect = lambda fn: fn(
            _make_tx_with_single(
                {
                    "champion_id": "champion99",
                    "evidence_score": 25.0,
                    "auto_promoted": True,
                }
            )
        )

        result = store._maybe_auto_promote_champion(
            fake_session,
            "s-x",
            self._make_run_data(3.0, 25),
            15.0,  # ev=15 < 25
        )

        assert result is None
        fake_session.execute_write.assert_not_called()

    def test_institutional_tier_assigned_above_threshold(self):
        store = _make_store()
        fake_session = MagicMock()
        fake_session.execute_read.side_effect = lambda fn: fn(_make_tx_with_single(None))

        captured_params: list[dict] = []

        def fake_write(fn):
            class FakeTx:
                def run(self_tx, query, **kwargs):
                    if "ch.tier" in query:
                        captured_params.append(kwargs)
                    return MagicMock(consume=MagicMock())

            fn(FakeTx())

        fake_session.execute_write.side_effect = fake_write

        store._maybe_auto_promote_champion(
            fake_session,
            "s-x",
            self._make_run_data(sharpe=_INSTITUTIONAL_SHARPE_THRESHOLD + 0.5),
            30.0,
        )

        assert captured_params and captured_params[0].get("tier") == "institutional"

    def test_superseded_by_edge_created_when_prior_champion_exists(self):
        """Promotion over an existing champion must emit SUPERSEDED_BY in the Cypher."""
        store = _make_store()
        fake_session = MagicMock()
        fake_session.execute_read.side_effect = lambda fn: fn(
            _make_tx_with_single(
                {
                    "champion_id": "oldchamp999",
                    "evidence_score": 10.0,
                    "auto_promoted": True,
                }
            )
        )

        captured_queries: list[str] = []

        def fake_write(fn):
            class FakeTx:
                def run(self_tx, query, **kwargs):
                    captured_queries.append(query)
                    return MagicMock(consume=MagicMock())

            fn(FakeTx())

        fake_session.execute_write.side_effect = fake_write

        store._maybe_auto_promote_champion(
            fake_session, "s-x", self._make_run_data(sharpe=3.2, total_trades=30), 20.0
        )

        assert captured_queries, "execute_write should have been called"
        assert any("SUPERSEDED_BY" in q for q in captured_queries), (
            "SUPERSEDED_BY edge creation missing from promotion Cypher"
        )

    def test_superseded_by_edge_not_created_on_first_promotion(self):
        """First promotion (prev IS NULL) must not emit SUPERSEDED_BY."""
        store = _make_store()
        fake_session = MagicMock()
        # No existing champion — execute_read returns None.
        fake_session.execute_read.side_effect = lambda fn: fn(_make_tx_with_single(None))

        captured_queries: list[str] = []

        def fake_write(fn):
            class FakeTx:
                def run(self_tx, query, **kwargs):
                    captured_queries.append(query)
                    return MagicMock(consume=MagicMock())

            fn(FakeTx())

        fake_session.execute_write.side_effect = fake_write

        store._maybe_auto_promote_champion(
            fake_session, "s-x", self._make_run_data(sharpe=2.5, total_trades=30), 13.7
        )

        # SUPERSEDED_BY is guarded by FOREACH (_ IN CASE WHEN prev IS NULL THEN [] ELSE [1] END)
        # so the string should NOT appear as a standalone edge creation call — only in the
        # conditional FOREACH body. The Cypher query text WILL contain "SUPERSEDED_BY" as part of
        # the FOREACH definition; we verify that execute_write was called (promotion happened)
        # and that the query contains the FOREACH guard, meaning no unconditional edge creation.
        assert captured_queries, "execute_write should have been called for first promotion"
        assert any("prev IS NULL" in q for q in captured_queries), (
            "FOREACH guard (prev IS NULL) missing — unconditional SUPERSEDED_BY would be created"
        )

    def test_idempotent_repromotion_same_run_id(self):
        """Promoting the same run_id twice returns the same champion_id without re-writing."""
        store = _make_store()
        fake_session = MagicMock()

        import hashlib

        expected_champ_id = hashlib.sha256(b"s-x|newrun123").hexdigest()[:12]

        # execute_read returns the SAME champion_id that would be generated → idempotent exit.
        fake_session.execute_read.side_effect = lambda fn: fn(
            _make_tx_with_single(
                {
                    "champion_id": expected_champ_id,
                    "evidence_score": 10.0,
                    "auto_promoted": True,
                }
            )
        )

        result = store._maybe_auto_promote_champion(
            fake_session, "s-x", self._make_run_data(sharpe=3.0, total_trades=20), 13.4
        )

        assert result == expected_champ_id
        fake_session.execute_write.assert_not_called()


# ── _reconcile_champion ───────────────────────────────────────────────────────


class TestReconcileChampion:
    """_reconcile_champion reads best run from DB and delegates to _maybe_auto_promote."""

    def test_returns_none_when_no_runs(self):
        store = _make_store()
        fake_session = MagicMock()
        fake_session.execute_read.side_effect = lambda fn: fn(_make_tx_with_single(None))

        result = store._reconcile_champion(fake_session, "no-runs-strategy")
        assert result is None

    def test_promotes_best_run_with_high_evidence(self):
        store = _make_store()
        fake_session = MagicMock()

        # reconcile read → best run with sharpe=3.0
        reconcile_record = {
            "run_id": "best_run_x",
            "sharpe": 3.0,
            "profit_factor": 2.0,
            "win_rate": 0.6,
            "max_drawdown": -0.05,
            "total_trades": 30,
            "total_r": 0.15,
            "artifact_path": "results/x.csv",
            "evidence_score": 3.0 * (30**0.5),
        }
        # _maybe_auto_promote_champion will call execute_read for the champion check
        # and then a read-back after the write to return the persisted ID.
        call_idx = [0]
        _readback_id = "ff00aa11bb22"  # 12-char stub

        def fake_read(fn):
            call_idx[0] += 1
            if call_idx[0] == 1:
                # reconcile_champion's best-run query
                return fn(_make_tx_with_single(reconcile_record))
            if call_idx[0] == 2:
                # _maybe_auto_promote_champion's current champion query → no champion
                return fn(_make_tx_with_single(None))
            # call 3: read-back after write → return persisted champion_id
            return fn(_make_tx_with_single({"champion_id": _readback_id}))

        fake_session.execute_read.side_effect = fake_read
        fake_session.execute_write = MagicMock()

        result = store._reconcile_champion(fake_session, "strategy-y")

        assert result is not None and len(result) == 12
        # flatten (1) + promotion (1) = 2 execute_write calls
        assert fake_session.execute_write.call_count == 2

    def test_no_op_when_quality_gate_blocks(self):
        """Best run sharpe < PROFESSIONAL → no promotion write, returns None.
        The flatten step still calls execute_write (no-op Cypher when 0 or 1 champion)."""
        store = _make_store()
        fake_session = MagicMock()
        low_sharpe_record = {
            "run_id": "r1",
            "sharpe": 1.0,  # below professional
            "profit_factor": 1.2,
            "win_rate": 0.5,
            "max_drawdown": -0.1,
            "total_trades": 10,
            "total_r": 0.05,
            "artifact_path": "results/x.csv",
            "evidence_score": 1.0 * (10**0.5),
        }
        fake_session.execute_read.side_effect = lambda fn: fn(
            _make_tx_with_single(low_sharpe_record)
        )

        result = store._reconcile_champion(fake_session, "strategy-z")

        assert result is None
        # flatten always fires (1 execute_write); promotion write must NOT fire
        assert fake_session.execute_write.call_count == 1


# ── persist_artifact — dedup and promotion integration ───────────────────────


class TestPersistArtifactDedup:
    def test_all_skipped_runs_reconcile_champion(self):
        """All runs redundant → skipped status, but _reconcile_champion still fires."""
        store = _make_store()
        artifact = _make_artifact(sharpe=1.5)

        mock_driver = store._driver
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_session
        mock_session.execute_write = MagicMock()

        with patch.object(store, "_reconcile_champion", return_value=None) as mock_reconcile:
            mock_session.execute_read.return_value = True  # redundant
            result = store.persist_artifact(artifact)

        assert result.status == "skipped"
        assert result.evolution[0].status == "skipped"
        mock_reconcile.assert_called_once_with(mock_session, "cl-1h-bear-liquidity-sweep")
        mock_session.execute_write.assert_not_called()

    def test_non_redundant_below_professional_threshold_recorded_no_champion(self):
        """sharpe < PROFESSIONAL → outcome is 'promoted' for best run but champion_id is None."""
        store = _make_store()
        artifact = _make_artifact(sharpe=1.5, total_trades=30)

        mock_driver = store._driver
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_session
        mock_session.execute_write = MagicMock()

        # Patch _reconcile_champion (quality gate below threshold → None)
        with patch.object(store, "_reconcile_champion", return_value=None):
            _call_idx = [0]

            def fake_read(fn):
                idx = _call_idx[0]
                _call_idx[0] += 1
                if idx == 0:
                    return False  # not redundant

                class FakeTx:
                    _inner = [0]

                    def run(self_tx, q, **kw):
                        r = MagicMock()
                        if self_tx._inner[0] == 0:
                            r.single.return_value = {"brid": None}
                        else:
                            r.single.return_value = {
                                "run_id": "aabbcc112233",
                                "evidence_score": 8.2,
                            }
                        self_tx._inner[0] += 1
                        return r

                return fn(FakeTx())

            mock_session.execute_read.side_effect = fake_read

            result = store.persist_artifact(artifact)

        assert result.status == "persisted"
        outcome = result.evolution[0]
        assert outcome.status == "promoted"
        assert outcome.champion_id is None

    def test_promoted_run_at_professional_threshold_gets_champion(self):
        """sharpe >= PROFESSIONAL and beats existing → champion_id populated."""
        store = _make_store()
        artifact = _make_artifact(sharpe=3.0, total_trades=25)

        mock_driver = store._driver
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_session
        mock_session.execute_write = MagicMock()

        with patch.object(store, "_reconcile_champion", return_value="newchamp999"):
            _call_idx = [0]
            ev = 3.0 * (25**0.5)

            def fake_read(fn):
                idx = _call_idx[0]
                _call_idx[0] += 1
                if idx == 0:
                    return False  # not redundant

                class FakeTx:
                    _inner = [0]

                    def run(self_tx, q, **kw):
                        r = MagicMock()
                        if self_tx._inner[0] == 0:
                            r.single.return_value = {"brid": None}
                        else:
                            r.single.return_value = {"run_id": "aabbcc112233", "evidence_score": ev}
                        self_tx._inner[0] += 1
                        return r

                return fn(FakeTx())

            mock_session.execute_read.side_effect = fake_read

            result = store.persist_artifact(artifact)

        outcome = result.evolution[0]
        assert outcome.status == "promoted"
        assert outcome.champion_id == "newchamp999"

    def test_promoted_run_does_not_displace_better_champion(self):
        """_reconcile_champion returns None → champion_id stays None in outcome."""
        store = _make_store()
        artifact = _make_artifact(sharpe=2.5, total_trades=10)

        mock_driver = store._driver
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_session
        mock_session.execute_write = MagicMock()

        with patch.object(store, "_reconcile_champion", return_value=None):
            _call_idx = [0]
            ev = 2.5 * (10**0.5)

            def fake_read(fn):
                idx = _call_idx[0]
                _call_idx[0] += 1
                if idx == 0:
                    return False

                class FakeTx:
                    _inner = [0]

                    def run(self_tx, q, **kw):
                        r = MagicMock()
                        if self_tx._inner[0] == 0:
                            r.single.return_value = {"brid": None}
                        else:
                            r.single.return_value = {"run_id": "aabbcc112233", "evidence_score": ev}
                        self_tx._inner[0] += 1
                        return r

                return fn(FakeTx())

            mock_session.execute_read.side_effect = fake_read

            result = store.persist_artifact(artifact)

        outcome = result.evolution[0]
        assert outcome.champion_id is None


# ── champion_md quality gate ─────────────────────────────────────────────────


class TestChampionMdQualityGate:
    def _make_champion_artifact(self, tier: str = "professional"):
        from datetime import UTC, date, datetime

        from research.graph.models import Champion, Provenance, ResearchArtifact, Strategy

        prov = Provenance(
            artifact_path="research/results/champions/test_champion.md",
            artifact_hash="deadbeef" * 8,
            artifact_mtime_iso="2026-04-05T10:00:00Z",
            ingested_at=datetime(2026, 4, 5, 10, 0, 0, tzinfo=UTC),
            parser_version="v1",
        )
        metrics = {
            "sharpe": 0.28 if tier == "fail" else 2.5,
            "calmar": 0.27,
            "profit_factor": 0.94 if tier == "fail" else 1.8,
            "total_trades": 26,
            "win_rate": 0.31 if tier == "fail" else 0.58,
            "max_drawdown_r": -0.72,
            "sample_size": 26,
            "tier": tier,
        }
        champion = Champion(
            champion_id="aabbccddeeff",
            strategy_id="btc-1d-bull-mars",
            freeze_date=date(2026, 4, 5),
            oos_status="oos_pending",
            fragilities=["test fragility"],
            artifact_path="research/results/champions/test_champion.md",
            metrics_summary=metrics,
            provenance=prov,
        )
        strategy = Strategy(
            strategy_id="btc-1d-bull-mars",
            instrument="BTC",
            timeframe="1D",
            direction="bull",
            logic_type="mars",
        )
        return ResearchArtifact(kind="champion_md", strategy=strategy, champion=champion)

    def test_fail_tier_champion_is_skipped(self):
        store = _make_store()
        artifact = self._make_champion_artifact(tier="fail")

        mock_driver = store._driver
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_session

        result = store.persist_artifact(artifact)

        assert result.status == "skipped"
        mock_session.execute_write.assert_not_called()

    def test_professional_tier_champion_is_persisted(self):
        store = _make_store()
        artifact = self._make_champion_artifact(tier="professional")

        mock_driver = store._driver
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_session
        mock_session.execute_write = MagicMock()

        result = store.persist_artifact(artifact)

        assert result.status == "persisted"
        mock_session.execute_write.assert_called_once()


# ── EvolutionOutcome ──────────────────────────────────────────────────────────


class TestEvolutionOutcome:
    def test_fields_default_champion_id_none(self):
        o = EvolutionOutcome(run_id="a", status="promoted", reason="", evidence_score=17.5)
        assert o.champion_id is None

    def test_champion_id_set(self):
        o = EvolutionOutcome(
            run_id="a", status="promoted", reason="", evidence_score=17.5, champion_id="xyz"
        )
        assert o.champion_id == "xyz"

    def test_skipped_has_reason(self):
        o = EvolutionOutcome(
            run_id="x",
            status="skipped",
            reason="existing run with total_trades=30 has sharpe >= 2.000 within 30 days",
            evidence_score=10.0,
        )
        assert "total_trades=30" in o.reason


# ── StoreResult ───────────────────────────────────────────────────────────────


class TestStoreResultEvolution:
    def test_default_empty(self):
        r = StoreResult(status="persisted", node_counts={}, relationship_counts={})
        assert r.evolution == []

    def test_evolution_populated(self):
        outcomes = [
            EvolutionOutcome(
                run_id="a", status="promoted", reason="", evidence_score=12.3, champion_id="abc"
            ),
        ]
        r = StoreResult(
            status="persisted", node_counts={}, relationship_counts={}, evolution=outcomes
        )
        assert r.evolution[0].champion_id == "abc"


# ── threshold constants ───────────────────────────────────────────────────────


class TestThresholdConstants:
    def test_professional_below_institutional(self):
        assert _PROFESSIONAL_SHARPE_THRESHOLD < _INSTITUTIONAL_SHARPE_THRESHOLD

    def test_professional_is_positive(self):
        assert _PROFESSIONAL_SHARPE_THRESHOLD > 0
