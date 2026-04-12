"""Champion decay monitor — recursive validation loop (QWS-0803).

Reads all active Champions, re-runs their trial scripts with a fresh date window,
computes Sharpe drift, and creates DEGRADED_TO edges when drift exceeds the threshold.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .store import GraphStore

_DEFAULT_DECAY_THRESHOLD = 0.75
_DEFAULT_LOOKBACK_DAYS = 90


class MonitorResult:
    """Result for one Champion evaluation."""

    def __init__(
        self,
        champion_id: str,
        strategy_id: str,
        artifact_path: str,
        old_sharpe: float,
        new_sharpe: float | None,
        drift: float | None,
        threshold: float,
        status: str,  # "degraded" | "ok" | "skipped" | "error"
        message: str,
        former_champion_id: str | None = None,
    ) -> None:
        self.champion_id = champion_id
        self.strategy_id = strategy_id
        self.artifact_path = artifact_path
        self.old_sharpe = old_sharpe
        self.new_sharpe = new_sharpe
        self.drift = drift
        self.threshold = threshold
        self.status = status
        self.message = message
        self.former_champion_id = former_champion_id


class MonitorRunner:
    """Runs decay checks for active Champions.

    Args:
        repo_root: Path to the repository root (used to resolve trial scripts).
        decay_threshold: Sharpe drift magnitude that triggers degradation.
            Reads from ResearchTarget.decay_threshold when None; falls back to 0.75.
        lookback_days: Days of fresh data passed to the trial script (env var
            ``QWS_MONITOR_LOOKBACK_DAYS``).
        dry_run: When True, compute drift but make no graph writes.
        timeout_seconds: Neo4j connection timeout.
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        decay_threshold: float | None = None,
        lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
        dry_run: bool = False,
        timeout_seconds: int = 3,
    ) -> None:
        self._repo_root = repo_root or Path.cwd()
        self._decay_threshold = decay_threshold
        self._lookback_days = lookback_days
        self._dry_run = dry_run
        self._timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, champion_id: str | None = None) -> list[MonitorResult]:
        """Run decay checks.

        Args:
            champion_id: When provided, restrict to exactly this Champion.

        Returns:
            List of MonitorResult — one per Champion evaluated.
        """
        store = GraphStore.from_env(timeout_seconds=self._timeout_seconds)
        threshold = self._resolve_threshold(store)

        champions = self._get_champions(store, champion_id)
        if not champions:
            return []

        results: list[MonitorResult] = []
        for champ in champions:
            result = self._evaluate_champion(store, champ, threshold)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_threshold(self, store: Any) -> float:
        """Read decay_threshold from ResearchTarget; fall back to 0.75."""
        try:
            targets = store.get_research_targets()
            if targets and targets[0].get("decay_threshold") is not None:
                return float(targets[0]["decay_threshold"])
        except Exception:  # noqa: BLE001
            pass
        return (
            self._decay_threshold if self._decay_threshold is not None else _DEFAULT_DECAY_THRESHOLD
        )

    def _get_champions(self, store: Any, champion_id: str | None) -> list[dict[str, Any]]:
        """Return list of active Champion dicts."""
        all_champs = store.get_active_champions()
        if champion_id is not None:
            filtered = [c for c in all_champs if c["champion_id"] == champion_id]
            return filtered
        return cast(list[dict[str, Any]], all_champs)

    def _evaluate_champion(
        self, store: Any, champ: dict[str, Any], threshold: float
    ) -> MonitorResult:
        """Evaluate one Champion for Sharpe drift."""
        cid = str(champ["champion_id"])
        sid = str(champ["strategy_id"])
        old_sharpe = float(champ.get("metrics_sharpe", 0.0))
        artifact_path = str(champ.get("artifact_path", ""))

        # Resolve trial script path from artifact_path
        script_path = self._resolve_script(artifact_path)
        if script_path is None:
            msg = (
                f"[WARN] Champion {cid}: unresolvable trial script path"
                f" ({artifact_path!r}) — skipped"
            )
            print(msg, file=sys.stderr)
            return MonitorResult(
                champion_id=cid,
                strategy_id=sid,
                artifact_path=artifact_path,
                old_sharpe=old_sharpe,
                new_sharpe=None,
                drift=None,
                threshold=threshold,
                status="skipped",
                message=msg,
            )

        # Re-run the trial script
        new_sharpe = self._run_trial(script_path)
        if new_sharpe is None:
            msg = f"[WARN] Champion {cid}: trial re-run failed — skipped"
            print(msg, file=sys.stderr)
            return MonitorResult(
                champion_id=cid,
                strategy_id=sid,
                artifact_path=artifact_path,
                old_sharpe=old_sharpe,
                new_sharpe=None,
                drift=None,
                threshold=threshold,
                status="skipped",
                message=msg,
            )

        drift = abs(new_sharpe - old_sharpe)

        if drift > threshold:
            return self._handle_degradation(
                store, cid, sid, artifact_path, old_sharpe, new_sharpe, drift, threshold
            )
        else:
            msg = (
                f"Champion {cid} ({sid}): drift={drift:.2f} within threshold={threshold:.2f} "
                f"(old_sharpe={old_sharpe:.2f}, new_sharpe={new_sharpe:.2f})"
            )
            return MonitorResult(
                champion_id=cid,
                strategy_id=sid,
                artifact_path=artifact_path,
                old_sharpe=old_sharpe,
                new_sharpe=new_sharpe,
                drift=drift,
                threshold=threshold,
                status="ok",
                message=msg,
            )

    def _handle_degradation(
        self,
        store: Any,
        champion_id: str,
        strategy_id: str,
        artifact_path: str,
        old_sharpe: float,
        new_sharpe: float,
        drift: float,
        threshold: float,
    ) -> MonitorResult:
        """Create FormerChampion + DEGRADED_TO edge and record notification blob."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        oos_reason = (
            f"Auto-detected by qw monitor on {today}: "
            f"Sharpe drifted from {old_sharpe:.2f} to {new_sharpe:.2f} "
            f"(drift={drift:.2f}, threshold={threshold:.2f})"
        )
        notification = (
            f"Strategy {strategy_id} hit decay threshold (drift={drift:.2f}). "
            f"Moved to FormerChampion. "
            f"Run `qw query --name former_champions` for context. "
            f"Options: pivot or retire."
        )

        print(notification)

        if self._dry_run:
            msg = (
                f"[DRY-RUN] Champion {champion_id}: drift={drift:.2f}"
                f" > threshold={threshold:.2f} — would degrade"
            )
            return MonitorResult(
                champion_id=champion_id,
                strategy_id=strategy_id,
                artifact_path=artifact_path,
                old_sharpe=old_sharpe,
                new_sharpe=new_sharpe,
                drift=drift,
                threshold=threshold,
                status="degraded",
                message=msg,
            )

        former_champion_id = store.degrade_champion(
            champion_id=champion_id,
            oos_reason=oos_reason,
            metrics_sharpe_at_degradation=new_sharpe,
        )

        # Attach notification as BlobArtifact to the FormerChampion
        store.attach_blob_to_former_champion(
            former_champion_id=former_champion_id,
            artifact_type="monitor_notification",
            content=notification,
        )

        msg = (
            f"Champion {champion_id} ({strategy_id}): DEGRADED "
            f"drift={drift:.2f} > threshold={threshold:.2f} "
            f"→ FormerChampion {former_champion_id}"
        )
        return MonitorResult(
            champion_id=champion_id,
            strategy_id=strategy_id,
            artifact_path=artifact_path,
            old_sharpe=old_sharpe,
            new_sharpe=new_sharpe,
            drift=drift,
            threshold=threshold,
            status="degraded",
            message=msg,
            former_champion_id=former_champion_id,
        )

    def _resolve_script(self, artifact_path: str) -> Path | None:
        """Return an absolute path to the trial script or None if unresolvable.

        The artifact_path on a Champion is a repo-relative POSIX path to the
        source CSV. The trial script lives alongside it with a .py extension
        (or is the file itself if it's already a .py).
        """
        if not artifact_path:
            return None

        candidates = []
        p = Path(artifact_path)

        # Try repo-relative .py sibling
        if p.suffix == ".py":
            script_rel = p
        else:
            script_rel = p.with_suffix(".py")

        # Resolve against repo root
        repo_abs = self._repo_root / script_rel
        candidates.append(repo_abs)

        for c in candidates:
            if c.exists() and c.is_file():
                return c
        return None

    def _run_trial(self, script_path: Path) -> float | None:
        """Invoke the trial script and parse the Sharpe ratio from its stdout.

        The script is invoked with ``QWS_MONITOR_LOOKBACK_DAYS`` set. It must
        print a line matching ``sharpe: <float>`` (case-insensitive) to stdout.

        Returns the parsed Sharpe or None on failure.
        """
        import os  # noqa: PLC0415

        env = {**os.environ, "QWS_MONITOR_LOOKBACK_DAYS": str(self._lookback_days)}
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )
        except subprocess.TimeoutExpired:
            print(
                f"[WARN] trial script timed out: {script_path}",
                file=sys.stderr,
            )
            return None
        except Exception as exc:  # noqa: BLE001
            print(
                f"[WARN] trial script error: {script_path}: {exc}",
                file=sys.stderr,
            )
            return None

        if result.returncode != 0:
            print(
                f"[WARN] trial script exited {result.returncode}: {script_path}",
                file=sys.stderr,
            )
            return None

        return self._parse_sharpe(result.stdout)

    @staticmethod
    def _parse_sharpe(stdout: str) -> float | None:
        """Parse ``sharpe: <float>`` from trial stdout."""
        for line in stdout.splitlines():
            low = line.strip().lower()
            if low.startswith("sharpe:"):
                parts = low.split(":", 1)
                try:
                    return float(parts[1].strip())
                except ValueError:
                    pass
        return None
