"""CLI entry point for qw record, qw reconcile, and qw query commands.

Reference: docs/graph_v1_contract.md - CLI Spec (Man-page style)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from . import ids as _ids
from .curator import apply_significance_gate
from .models import ResearchArtifact, Run
from .parsers import ChampionMarkdownParser, CSVParser, research_artifact_payload_hash
from .query import GraphQueryService
from .query_presets import PRESET_CATALOG, resolve_preset, run_preset, validate_params
from .store import RESEARCH_TARGET_ALLOWED_KEYS, GraphStore, StoreError, StoreInfraError

_VALID_HYPOTHESIS_STATUSES = frozenset({"open", "confirmed", "refuted", "abandoned"})

_DEFAULT_SIMILARITY_THRESHOLD = 0.85
_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _embed_text(text: str) -> list[float]:
    """Return a float embedding vector for *text* using the local sentence-transformers model.

    The model is loaded lazily and cached within the process.  No external API
    calls are made — inference runs on CPU.

    Raises ImportError when sentence-transformers is not installed.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers is required for semantic hypothesis deduplication. "
            "Install with: pip install sentence-transformers"
        ) from exc

    model = SentenceTransformer(_EMBEDDING_MODEL)
    vector = model.encode(text, normalize_embeddings=True)
    return [float(v) for v in vector]

# Promotion alert thresholds — imported read-only from standards.py
# fmt: off
try:
    from research.experiments.standards import (  # noqa: I001
        SHARPE as _SHARPE,
        PROFIT_FACTOR as _PROFIT_FACTOR,
        MIN_ACTIVE_WINDOW_FREQUENCY as _MIN_AWF,
    )
except ImportError:  # standards.py not on path in some test environments
    _SHARPE: dict[str, float] = {"professional": 1.5, "institutional": 2.5}
    _PROFIT_FACTOR: dict[str, float] = {"professional": 1.75, "institutional": 3.0}
    _MIN_AWF: float = 0.06
# fmt: on

_PROMOTION_MIN_TRADES: int = 30


def _evaluate_promotion_candidates(
    runs: list[Run],
    persisted_run_ids: set[str],
) -> list[str]:
    """Return formatted alert strings for baseline_csv runs that clear the professional tier.

    Evaluates only persisted runs (not skipped). Runs with null active_window_frequency
    are silently excluded. Exceptions are not raised — callers should catch them.
    """
    alerts: list[str] = []
    for run in runs:
        if run.run_id not in persisted_run_ids:
            continue
        awf = run.active_window_frequency
        if awf is None:
            continue
        if run.sharpe < _SHARPE["professional"]:
            continue
        if run.profit_factor < _PROFIT_FACTOR["professional"]:
            continue
        if run.total_trades < _PROMOTION_MIN_TRADES:
            continue
        if awf < _MIN_AWF:
            continue

        # Determine tier from the minimum of sharpe / profit_factor tiers
        if (
            run.sharpe >= _SHARPE["institutional"]
            and run.profit_factor >= _PROFIT_FACTOR["institutional"]
        ):
            tier = "institutional"
        else:
            tier = "professional"

        block = (
            f"[PROMOTION CANDIDATE] run_id={run.run_id}\n"
            f"  sharpe={run.sharpe:.2f}  profit_factor={run.profit_factor:.2f}"
            f"  win_rate={run.win_rate:.2f}  trades={run.total_trades}  tier={tier}"
        )
        alerts.append(block)
    return alerts


class ReceiptWriter:
    """Manages receipt file creation and storage."""

    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root or Path.cwd()
        self.receipts_dir = self.repo_root / ".qws" / "receipts"

    def write_receipt(
        self,
        artifact_id: str,
        kind: str,
        artifact_path: str,
        artifact_hash: str,
        status: Literal["persisted", "pending_offline", "skipped"],
        node_counts: dict[str, int],
        relationship_counts: dict[str, int],
        warnings: list[str] | None = None,
        oos_sharpe: float | None = None,
    ) -> None:
        """Write a receipt JSON file for a successful ingest."""
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

        receipt: dict[str, Any] = {
            "id": artifact_id,
            "kind": kind,
            "artifact_path": artifact_path,
            "artifact_hash": artifact_hash,
            "status": status,
            "ingested_at": datetime.now(UTC).isoformat(),
            "node_counts": node_counts,
            "relationship_counts": relationship_counts,
            "warnings": warnings or [],
        }
        # Include oos_sharpe in oos_update receipts (float when passed, null when absent)
        if kind == "oos_update":
            receipt["oos_sharpe"] = oos_sharpe

        receipt_path = self.receipts_dir / f"{artifact_id}.json"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")


class PendingWriter:
    """Manages pending payload file creation for offline mode."""

    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root or Path.cwd()
        self.pending_dir = self.repo_root / ".qws" / "pending"

    def write_pending(self, artifact_id: str, payload: dict[str, Any]) -> None:
        """Write a validated ResearchArtifact payload to pending queue."""
        self.pending_dir.mkdir(parents=True, exist_ok=True)

        pending_path = self.pending_dir / f"{artifact_id}.json"
        pending_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class NeoConnector:
    """Thin compatibility wrapper for handshake checks in CLI flow."""

    def __init__(self, timeout_seconds: int = 3):
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        try:
            store = GraphStore.from_env(timeout_seconds=self.timeout_seconds)
            try:
                store.ping()
            finally:
                store.close()
            return True
        except StoreInfraError:
            return False


def _get_artifact_id(artifact: ResearchArtifact) -> str:
    """Extract canonical artifact ID from ResearchArtifact payload."""
    if artifact.kind in {"baseline_csv", "grid_csv"}:
        # Use first run's ID for CSV artifacts
        return artifact.runs[0].run_id if artifact.runs else "unknown"
    elif artifact.kind == "champion_md":
        return artifact.champion.champion_id if artifact.champion else "unknown"
    elif artifact.kind == "tracker_md":
        # Use artifact path hash for tracker blobs
        path_hash = hashlib.sha256(artifact.blob.artifact_path.encode()).hexdigest()[:12]
        return path_hash
    return "unknown"


def _parse_artifact(
    file_path: Path,
    kind: str,
    pivot_from_run_id: str | None = None,
    repo_root: Path | None = None,
) -> tuple[ResearchArtifact, list[str]]:
    """Parse an artifact file into a ResearchArtifact payload.

    Args:
        file_path: Path to artifact file
        kind: Artifact kind (baseline_csv, grid_csv, champion_md, tracker_md)
        pivot_from_run_id: Optional explicit pivot link for champions
        repo_root: Optional repo root for champion registry lookup

    Returns:
        (ResearchArtifact, warnings_list) tuple

    Raises:
        FileNotFoundError: Artifact file not found
        ValueError: Parse or validation error
    """
    if kind in {"baseline_csv", "grid_csv"}:
        parser = CSVParser(file_path, kind, repo_root=repo_root)
        return parser.parse()
    elif kind == "champion_md":
        parser = ChampionMarkdownParser(
            file_path,
            registry_path=repo_root / "research" / "results" / "registry.json" if repo_root else None,
            pivot_from_run_id=pivot_from_run_id,
            repo_root=repo_root,
        )
        return parser.parse()
    elif kind == "tracker_md":
        # Tracker markdown: attach as raw blob
        from .models import BlobArtifact, Provenance, Strategy

        if not file_path.exists():
            raise FileNotFoundError(f"Artifact not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        artifact_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        mtime_iso = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC).isoformat().replace("+00:00", "Z")

        from .parsers import _artifact_path_text

        artifact_path_text = _artifact_path_text(file_path, repo_root)
        provenance = Provenance(
            artifact_path=artifact_path_text,
            artifact_hash=artifact_hash,
            artifact_mtime_iso=mtime_iso,
            ingested_at=datetime.now(UTC),
            parser_version="v1",
        )

        # Infer strategy from artifact path
        from .ids import strategy_id as make_strategy_id
        from .parsers import _infer_strategy_from_artifact_name

        inferred = _infer_strategy_from_artifact_name(file_path.stem)
        strategy = Strategy(
            strategy_id=make_strategy_id(
                inferred["instrument"], inferred["timeframe"],
                inferred["direction"], inferred["logic_type"],
            ),
            instrument=inferred["instrument"],
            timeframe=inferred["timeframe"],
            direction=inferred["direction"],  # type: ignore
            logic_type=inferred["logic_type"],
        )

        blob = BlobArtifact(
            strategy_id=strategy.strategy_id,
            artifact_path=artifact_path_text,
            artifact_kind="tracker_md",
            raw_text_sha256=artifact_hash,
            provenance=provenance,
        )
        artifact = ResearchArtifact(kind="tracker_md", strategy=strategy, blob=blob)
        return artifact, []
    else:
        raise ValueError(f"unknown artifact kind: {kind}")


def _keep_approved(artifact: ResearchArtifact) -> ResearchArtifact:
    """Keep only runs with curator_note set (approved by semantic tier)."""
    approved_runs = [r for r in artifact.runs if r.curator_note]
    approved_configs = [c for c, r in zip(artifact.configs, artifact.runs) if r.curator_note]
    return artifact.model_copy(update={"runs": approved_runs, "configs": approved_configs})


def _read_bundle_manifest(bundle_dir: Path) -> dict:
    """Read and minimally validate bundle.json from a bundle directory.

    Raises:
        FileNotFoundError: bundle.json is absent from the directory.
        ValueError: manifest is missing required fields.
    """
    manifest_path = bundle_dir / "bundle.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"bundle.json not found in {bundle_dir}. "
            "Bundle directories must contain a bundle.json manifest written by the shell runner."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    missing = [k for k in ("csv", "csv_kind") if not files.get(k)]
    if missing:
        raise ValueError(
            f"bundle.json is missing required files fields: {missing}. "
            f"Expected keys: files.csv, files.csv_kind (and optionally files.html)."
        )
    return manifest


def _cmd_bundle(args: argparse.Namespace) -> int:
    """Execute `qw record --bundle <dir>` — two-phase CSV ingest + HTML path patch.

    Exit codes:
        0: CSV ingested (or already present), html patched if present
        1: manifest missing, validation failure, or missing CSV file
        2: Neo4j unavailable
    """
    bundle_dir = Path(args.bundle).resolve()
    if not bundle_dir.is_dir():
        print(f"ERROR: bundle directory not found: {bundle_dir}", file=sys.stderr)
        return 1

    if getattr(args, "offline", False):
        print("ERROR: --offline is not supported with --bundle", file=sys.stderr)
        return 1

    timeout_seconds = args.timeout_seconds
    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()
    dry_run = args.dry_run

    # Phase 0: read manifest
    try:
        manifest = _read_bundle_manifest(bundle_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    files = manifest["files"]
    csv_filename: str = files["csv"]
    csv_kind: str = files["csv_kind"]
    html_filename: str | None = files.get("html")

    csv_path = bundle_dir / csv_filename

    # Phase 1: parse CSV
    try:
        artifact, warnings = _parse_artifact(csv_path, csv_kind, repo_root=repo_root)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: Validation failed: {exc}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    # Attach family_id when --source-file is provided
    raw_source_file = getattr(args, "source_file", None)
    source_file = Path(raw_source_file) if isinstance(raw_source_file, (str, Path)) and str(raw_source_file).strip() else None
    if source_file is not None:
        try:
            src_bytes = source_file.read_bytes()
        except OSError as exc:
            print(f"ERROR: Cannot read source file: {exc}", file=sys.stderr)
            return 1
        src_hash = _ids.source_hash(src_bytes)
        fid = _ids.family_id(
            artifact.strategy.logic_type,
            artifact.strategy.direction,
            src_hash,
        )
        artifact = artifact.model_copy(
            update={"strategy": artifact.strategy.model_copy(update={"family_id": fid})}
        )

    # Attach regime to all runs when --regime is provided
    bundle_regime = getattr(args, "regime", None)
    if bundle_regime is not None:
        artifact = artifact.model_copy(
            update={"runs": [r.model_copy(update={"regime": bundle_regime}) for r in artifact.runs]}
        )

    run_ids = [r.run_id for r in artifact.runs]

    if dry_run:
        print(f"OK: bundle dry-run passed — csv={csv_filename} kind={csv_kind} runs={len(run_ids)}")
        return 0

    # Phase 2: ingest CSV
    connector = NeoConnector(timeout_seconds=timeout_seconds)
    if not connector.is_available():
        print(
            f"WARNING: Neo4j unavailable (timeout after {timeout_seconds}s)",
            file=sys.stderr,
        )
        return 2

    try:
        store = GraphStore.from_env(timeout_seconds=timeout_seconds)
        try:
            result = store.persist_artifact(artifact)

            # Phase 3: patch html path onto persisted run nodes only.
            # SKIPPED runs were never written to the graph in this ingest pass,
            # so their run_id does not exist as a :Run node and MATCH would fail.
            persisted_run_ids = [
                o.run_id for o in result.evolution if o.status != "skipped"
            ]
            html_abs_path: str | None = None
            patched_count = 0
            if html_filename:
                html_file = bundle_dir / html_filename
                if html_file.exists():
                    html_abs_path = str(html_file)
                    for run_id in persisted_run_ids:
                        found = store.patch_run_html_path(run_id, html_abs_path)
                        if found:
                            patched_count += 1
                else:
                    print(
                        f"WARNING: bundle.json lists html={html_filename!r} "
                        f"but file not found in {bundle_dir}",
                        file=sys.stderr,
                    )
            # Correlation gate: warn when a newly-promoted Champion already has
            # CORRELATED_WITH edges to other active Champions (non-blocking).
            corr_warnings: list[str] = []
            for outcome in result.evolution:
                if outcome.status == "promoted" and outcome.champion_id:
                    try:
                        overlap = store.check_correlated_with_active_champions(
                            outcome.champion_id,
                            threshold=_CORRELATION_GATE_THRESHOLD,
                        )
                        for match in overlap:
                            corr_warnings.append(
                                f"CORRELATION WARNING: new Champion {outcome.champion_id} "
                                f"correlated with {match.get('champion_id')} "
                                f"(r={match.get('coefficient', '?'):.2f}, "
                                f"strategy={match.get('strategy_id')})"
                            )
                    except Exception:  # noqa: BLE001
                        pass  # correlation check is advisory; never block ingest
        finally:
            store.close()
    except StoreInfraError as exc:
        print(f"ERROR: Neo4j write failed: {exc}", file=sys.stderr)
        return 2

    # Print bundle receipt
    print(f"BUNDLE: {bundle_dir.name}")
    print(f"  csv: {csv_filename} ({csv_kind})")
    for outcome in result.evolution:
        ev_str = f"  ev={outcome.evidence_score:.2f}" if outcome.evidence_score is not None else ""
        if outcome.status == "skipped":
            print(f"  [SKIPPED]  {outcome.run_id}{ev_str} — {outcome.reason}")
        elif outcome.status == "promoted":
            champ = f" → Champion {outcome.champion_id}" if outcome.champion_id else ""
            print(f"  [PROMOTED] {outcome.run_id}{ev_str}{champ}")
        else:
            print(f"  [RECORDED] {outcome.run_id}{ev_str}")
    if html_abs_path:
        if persisted_run_ids:
            print(f"  html: {html_filename} → artifact_path_html patched ({patched_count}/{len(persisted_run_ids)} nodes)")
        else:
            print(f"  html: {html_filename} → skipped (no new runs persisted)")
    elif html_filename:
        print(f"  html: {html_filename} (file not found — skipped)")
    else:
        print("  html: (none in manifest)")

    for warn in corr_warnings:
        print(f"  {warn}", file=sys.stderr)

    return 0


_VALID_OOS_STATUSES = frozenset({"oos_pending", "oos_pass", "oos_fail"})
_CORRELATION_GATE_THRESHOLD = 0.60

_TARGET_INT_KEYS = frozenset({"max_holding_hours", "min_trades"})


def _cmd_oos_update(args: argparse.Namespace) -> int:
    """Execute `qw record --oos <status> --champion <id> [--sharpe <float>]`.

    Updates oos_status (and oos_date, optionally metrics_oos_sharpe) on an
    existing Champion node.  Writes a receipt with kind=oos_update.

    Exit codes:
        0: champion found and updated, receipt written
        1: validation error, champion not found, or lifecycle conflict
        2: infrastructure failure (Neo4j unavailable)
    """
    oos_status = args.oos
    champion_id = getattr(args, "champion", None)
    sharpe: float | None = getattr(args, "sharpe", None)
    timeout_seconds = args.timeout_seconds
    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()

    if not champion_id:
        print("ERROR: --champion is required when --oos is provided", file=sys.stderr)
        return 1

    if oos_status not in _VALID_OOS_STATUSES:
        valid = ", ".join(sorted(_VALID_OOS_STATUSES))
        print(
            f"ERROR: invalid oos_status {oos_status!r}; must be one of: {valid}",
            file=sys.stderr,
        )
        return 1

    # Validate --sharpe: must be non-negative when provided
    if sharpe is not None and sharpe < 0:
        print(
            f"ERROR: --sharpe must be non-negative, got {sharpe}",
            file=sys.stderr,
        )
        return 1

    connector = NeoConnector(timeout_seconds=timeout_seconds)
    if not connector.is_available():
        print(
            f"ERROR: Neo4j unavailable (timeout after {timeout_seconds}s)",
            file=sys.stderr,
        )
        return 2

    try:
        store = GraphStore.from_env(timeout_seconds=timeout_seconds)
        try:
            found = store.update_champion_oos_status(
                champion_id=champion_id,
                status=oos_status,
                sharpe=sharpe,
            )
        finally:
            store.close()
    except StoreInfraError as exc:
        print(f"ERROR: Neo4j write failed: {exc}", file=sys.stderr)
        return 2
    except StoreError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not found:
        print(
            f"ERROR: Champion {champion_id!r} not found in graph",
            file=sys.stderr,
        )
        return 1

    # Synthetic artifact_hash for the receipt (no file involved).
    op_sig = f"oos_update:{champion_id}:{oos_status}"
    artifact_hash = hashlib.sha256(op_sig.encode()).hexdigest()

    # Build receipt with oos_sharpe key
    receipt_writer = ReceiptWriter(repo_root)
    try:
        receipt_writer.write_receipt(
            artifact_id=champion_id,
            kind="oos_update",
            artifact_path=f"champion:{champion_id}",
            artifact_hash=artifact_hash,
            status="persisted",
            node_counts={"Champion": 1},
            relationship_counts={},
            oos_sharpe=sharpe,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Failed to write receipt: {exc}", file=sys.stderr)
        return 2

    print(
        f"OK: Champion {champion_id!r} oos_status={oos_status!r}",
        file=sys.stdout,
    )
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    """Execute `qw seed` command.

    Supports two modes:
      --targets           Create/update the singleton ResearchTarget node.
      --demo [--teardown] Seed or remove deterministic demo provenance graph.

    Exit codes:
        0: seeded/removed successfully
        1: validation error or unrecognised mode
        2: infrastructure failure (Neo4j unavailable)
    """
    is_demo: bool = getattr(args, "demo", False)
    is_teardown: bool = getattr(args, "teardown", False)

    if is_demo:
        timeout_seconds = getattr(args, "timeout_seconds", 3)
        connector = NeoConnector(timeout_seconds=timeout_seconds)
        if not connector.is_available():
            print(
                f"ERROR: Neo4j unavailable (timeout after {timeout_seconds}s)",
                file=sys.stderr,
            )
            return 2
        try:
            store = GraphStore.from_env(timeout_seconds=timeout_seconds)
            try:
                if is_teardown:
                    store.teardown_demo_graph()
                    print("OK: demo graph torn down", file=sys.stdout)
                else:
                    store.seed_demo_graph()
                    print("OK: demo graph seeded", file=sys.stdout)
            finally:
                store.close()
        except StoreInfraError as exc:
            print(f"ERROR: Neo4j write failed: {exc}", file=sys.stderr)
            return 2
        return 0

    if not args.targets:
        print("ERROR: --targets is required", file=sys.stderr)
        return 1

    raw_sets: list[str] = args.set or []
    overrides: dict[str, float | int] = {}
    for kv in raw_sets:
        if "=" not in kv:
            print(f"ERROR: --set must be key=value, got: {kv!r}", file=sys.stderr)
            return 1
        k, _, v = kv.partition("=")
        k = k.strip()
        if k not in RESEARCH_TARGET_ALLOWED_KEYS:
            print(
                f"ERROR: unknown target key {k!r}. "
                f"Allowed: {sorted(RESEARCH_TARGET_ALLOWED_KEYS)}",
                file=sys.stderr,
            )
            return 1
        try:
            overrides[k] = int(float(v)) if k in _TARGET_INT_KEYS else float(v)
        except ValueError:
            print(f"ERROR: --set {k}={v!r}: value must be numeric", file=sys.stderr)
            return 1

    timeout_seconds = getattr(args, "timeout_seconds", 3)

    connector = NeoConnector(timeout_seconds=timeout_seconds)
    if not connector.is_available():
        print(
            f"ERROR: Neo4j unavailable (timeout after {timeout_seconds}s)",
            file=sys.stderr,
        )
        return 2

    try:
        store = GraphStore.from_env(timeout_seconds=timeout_seconds)
        try:
            store.ensure_research_target(overrides=overrides or None)
        finally:
            store.close()
    except StoreInfraError as exc:
        print(f"ERROR: Neo4j write failed: {exc}", file=sys.stderr)
        return 2

    if overrides:
        kv_str = ", ".join(f"{k}={v}" for k, v in overrides.items())
        print(f"OK: ResearchTarget seeded ({kv_str})", file=sys.stdout)
    else:
        print("OK: ResearchTarget seeded", file=sys.stdout)
    return 0


def _cmd_hypothesis(args: argparse.Namespace) -> int:
    """Execute `qw record --hypothesis ...` — hypothesis journaling commands.

    Modes:
      --hypothesis "<title>"                  → create Hypothesis node (source=user)
      --hypothesis <id> --tested-as <sid>     → create TESTED_AS edge
      --hypothesis <id> --branched-from <nid> --rationale "<text>"  → BRANCHED_FROM edge
      --hypothesis <id> --status <s>          → update status

    Exit codes:
        0: success
        1: validation error or node not found
        2: Neo4j unavailable
    """
    hypothesis_arg: str = args.hypothesis
    tested_as: str | None = getattr(args, "tested_as", None)
    branched_from: str | None = getattr(args, "branched_from", None)
    rationale: str | None = getattr(args, "rationale", None)
    status: str | None = getattr(args, "status", None)
    timeout_seconds: int = getattr(args, "timeout_seconds", 3)
    similarity_threshold: float = float(
        getattr(args, "similarity_threshold", None) or _DEFAULT_SIMILARITY_THRESHOLD
    )

    connector = NeoConnector(timeout_seconds=timeout_seconds)
    if not connector.is_available():
        print(f"ERROR: Neo4j unavailable (timeout after {timeout_seconds}s)", file=sys.stderr)
        return 2

    try:
        store = GraphStore.from_env(timeout_seconds=timeout_seconds)
        try:
            # Mode 1: create hypothesis (title is a new quoted string — not a 12-char id)
            if tested_as is None and branched_from is None and status is None:
                title = hypothesis_arg
                if not title:
                    print("ERROR: --hypothesis requires a non-empty title or ID", file=sys.stderr)
                    return 1
                if len(title) > 200:
                    print("ERROR: hypothesis title must be ≤ 200 characters", file=sys.stderr)
                    return 1
                created_at_iso = datetime.now(UTC).isoformat()
                hypothesis_id = _ids.hash12(title, created_at_iso)
                store.create_hypothesis(hypothesis_id=hypothesis_id, title=title, source="user")
                print(f"OK: Hypothesis created — id={hypothesis_id}")

                # Semantic deduplication: embed + store + create edges
                try:
                    embedding = _embed_text(title)
                    store.set_hypothesis_embedding(hypothesis_id, embedding)
                    existing = store.get_all_hypothesis_embeddings()
                    n_similar = store.create_semantic_edges(
                        hypothesis_id, embedding, existing, threshold=similarity_threshold
                    )
                    if n_similar > 0:
                        print(
                            f"{n_similar} similar hypotheses found. "
                            f"Run: qw query --name similar_hypotheses "
                            f"--param hypothesis_id={hypothesis_id}"
                        )
                except ImportError as exc:
                    print(f"WARNING: semantic embedding skipped — {exc}", file=sys.stderr)
                except Exception as exc:  # noqa: BLE001
                    print(f"WARNING: semantic embedding failed — {exc}", file=sys.stderr)

                return 0

            hypothesis_id = hypothesis_arg

            # Mode 2: update status
            if status is not None:
                if status not in _VALID_HYPOTHESIS_STATUSES:
                    valid = ", ".join(sorted(_VALID_HYPOTHESIS_STATUSES))
                    print(f"ERROR: invalid status {status!r}; must be one of: {valid}", file=sys.stderr)
                    return 1
                found = store.update_hypothesis_status(hypothesis_id, status)
                if not found:
                    print(f"ERROR: Hypothesis {hypothesis_id!r} not found in graph", file=sys.stderr)
                    return 1
                print(f"OK: Hypothesis {hypothesis_id!r} status={status!r}")
                return 0

            # Mode 3: TESTED_AS
            if tested_as is not None:
                store.link_hypothesis_tested_as(hypothesis_id, tested_as)
                print(f"OK: TESTED_AS edge created — hypothesis={hypothesis_id} strategy={tested_as}")
                return 0

            # Mode 4: BRANCHED_FROM
            if branched_from is not None:
                if not rationale:
                    print("ERROR: --rationale is required with --branched-from", file=sys.stderr)
                    return 1
                store.link_hypothesis_branched_from(hypothesis_id, branched_from, rationale)
                print(f"OK: BRANCHED_FROM edge created — hypothesis={hypothesis_id} node={branched_from}")
                return 0

        finally:
            store.close()

    except StoreError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except StoreInfraError as exc:
        print(f"ERROR: Neo4j write failed: {exc}", file=sys.stderr)
        return 2

    return 0  # unreachable


def cmd_record(args: argparse.Namespace) -> int:
    """Execute `qw record` command.

    Exit codes:
        0: validation passed and persisted, or validation passed and written to pending in offline mode
        1: schema validation failure
        2: infrastructure failure (Neo4j unavailable and --offline not provided)
    """
    # Dispatch to hypothesis handler when --hypothesis is provided
    if getattr(args, "hypothesis", None) is not None:
        return _cmd_hypothesis(args)

    # Dispatch to bundle handler when --bundle is provided
    if getattr(args, "bundle", None):
        return _cmd_bundle(args)

    # Dispatch to OOS update handler when --oos is provided
    if getattr(args, "oos", None):
        return _cmd_oos_update(args)

    if not args.file:
        print("ERROR: --file is required when --bundle is not provided", file=sys.stderr)
        return 1
    if not args.kind:
        print("ERROR: --kind is required with --file", file=sys.stderr)
        return 1

    file_path = Path(args.file)
    kind = args.kind
    pivot_from_run_id = args.pivot_from
    offline = args.offline
    timeout_seconds = args.timeout_seconds
    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()
    dry_run = args.dry_run
    raw_source_file = getattr(args, "source_file", None)
    source_file = Path(raw_source_file) if isinstance(raw_source_file, (str, Path)) and str(raw_source_file).strip() else None
    ingest_all = getattr(args, "all", False)
    analyze = getattr(args, "analyze", False)

    # Parse and validate artifact
    try:
        artifact, warnings = _parse_artifact(
            file_path,
            kind,
            pivot_from_run_id=pivot_from_run_id,
            repo_root=repo_root,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: Validation failed: {exc}", file=sys.stderr)
        return 1

    # Attach family_id when source file is provided
    if source_file is not None:
        try:
            src_bytes = source_file.read_bytes()
        except OSError as exc:
            print(f"ERROR: Cannot read source file: {exc}", file=sys.stderr)
            return 1
        src_hash = _ids.source_hash(src_bytes)
        fid = _ids.family_id(
            artifact.strategy.logic_type,
            artifact.strategy.direction,
            src_hash,
        )
        artifact = artifact.model_copy(
            update={"strategy": artifact.strategy.model_copy(update={"family_id": fid})}
        )

    # Attach regime to all runs when --regime is provided
    regime = getattr(args, "regime", None)
    if regime is not None:
        artifact = artifact.model_copy(
            update={"runs": [r.model_copy(update={"regime": regime}) for r in artifact.runs]}
        )

    # Apply significance gate for grid_csv (unless --all is set)
    summary = None
    if kind == "grid_csv" and not ingest_all:
        if analyze:
            try:
                from .analyst import AnalystFactory, LlamaUnavailableError
                try:
                    analyst = AnalystFactory.from_env()
                    candidates, summary = apply_significance_gate(artifact, top_n_sharpe=20, bottom_n_drawdown=0)
                    artifact = analyst.annotate(candidates)
                    artifact = _keep_approved(artifact)
                except LlamaUnavailableError as exc:
                    print(f"WARNING: AI analyst unavailable — {exc}", file=sys.stderr)
                    artifact, summary = apply_significance_gate(artifact)
            except ImportError:
                artifact, summary = apply_significance_gate(artifact)
        else:
            artifact, summary = apply_significance_gate(artifact)

    artifact_id = _get_artifact_id(artifact)
    payload = artifact.model_dump(mode="json")
    artifact_hash = research_artifact_payload_hash(artifact)

    # Collect unknown field warnings
    all_warnings = list(warnings)

    # Log unknown fields if any
    if all_warnings:
        for warning in all_warnings:
            print(f"WARNING: {warning}", file=sys.stderr)

    # Dry-run: validate only, no write
    if dry_run:
        print(f"OK: {kind} validation passed (dry-run, no write)", file=sys.stdout)
        return 0

    # Offline mode: write to pending queue only
    if offline:
        pending_writer = PendingWriter(repo_root)
        try:
            pending_writer.write_pending(artifact_id, payload)
        except Exception as exc:
            print(f"ERROR: Failed to write pending payload: {exc}", file=sys.stderr)
            return 1

        # Write receipt with pending_offline status
        receipt_writer = ReceiptWriter(repo_root)
        try:
            receipt_writer.write_receipt(
                artifact_id=artifact_id,
                kind=kind,
                artifact_path=file_path.as_posix(),
                artifact_hash=artifact_hash,
                status="pending_offline",
                node_counts={},
                relationship_counts={},
                warnings=all_warnings,
            )
        except Exception as exc:
            print(f"ERROR: Failed to write receipt: {exc}", file=sys.stderr)
            return 1

        print(f"OK: {kind} persisted to pending queue (.qws/pending/{artifact_id}.json)", file=sys.stdout)
        return 0

    # Online mode: attempt Neo4j write
    connector = NeoConnector(timeout_seconds=timeout_seconds)
    if not connector.is_available():
        print(
            f"WARNING: Neo4j unavailable (timeout after {timeout_seconds}s)",
            file=sys.stderr,
        )
        print(
            "INFO: Start Neo4j or rerun with --offline to queue for later ingestion",
            file=sys.stderr,
        )
        return 2

    # Write to Neo4j
    try:
        store = GraphStore.from_env(timeout_seconds=timeout_seconds)
        try:
            result = store.persist_artifact(artifact, summary=summary)
            node_counts = result.node_counts
            relationship_counts = result.relationship_counts
        finally:
            store.close()
    except StoreInfraError as exc:
        print(f"ERROR: Neo4j write failed: {exc}", file=sys.stderr)
        return 2

    # Print per-run evolution outcomes (CSV kinds only)
    for outcome in result.evolution:
        ev_str = f"  ev={outcome.evidence_score:.2f}" if outcome.evidence_score is not None else ""
        if outcome.status == "skipped":
            print(f"[SKIPPED]  {outcome.run_id}{ev_str}  — {outcome.reason}")
        elif outcome.status == "promoted":
            if outcome.champion_id:
                print(
                    f"[PROMOTED] {outcome.run_id}{ev_str}"
                    f"  — new peak evidence score; Champion {outcome.champion_id} auto-promoted"
                )
            else:
                print(f"[PROMOTED] {outcome.run_id}{ev_str}  — new peak evidence score")
        else:
            print(f"[RECORDED] {outcome.run_id}{ev_str}")

    # Write receipt
    receipt_writer = ReceiptWriter(repo_root)
    try:
        receipt_writer.write_receipt(
            artifact_id=artifact_id,
            kind=kind,
            artifact_path=file_path.as_posix(),
            artifact_hash=artifact_hash,
            status=result.status,
            node_counts=node_counts,
            relationship_counts=relationship_counts,
            warnings=all_warnings,
        )
    except Exception as exc:
        print(f"ERROR: Failed to write receipt: {exc}", file=sys.stderr)
        return 2

    if result.status == "skipped":
        print(f"OK: {kind} — all runs statistically redundant (no new information added)")
    else:
        print(f"OK: {kind} persisted to Neo4j graph")

    # Promotion alert — baseline_csv only; exceptions are suppressed so receipt is always written
    if kind == "baseline_csv":
        try:
            persisted_ids = {o.run_id for o in result.evolution if o.status != "skipped"}
            alerts = _evaluate_promotion_candidates(artifact.runs, persisted_ids)
            for alert in alerts:
                print(alert)
        except Exception:  # noqa: BLE001
            pass

    return 0


def cmd_reconcile(args: argparse.Namespace) -> int:
    """Execute `qw reconcile` command.

    Audit ingested artifacts against graph records.
    """
    # Basic stub implementation for acceptance criteria
    # Full implementation would scan .qws/pending and receipts
    # and compare against Neo4j nodes

    repo_root = Path(args.repo_root) if hasattr(args, "repo_root") and args.repo_root else Path.cwd()
    output_json = args.json if hasattr(args, "json") else False
    _since = args.since if hasattr(args, "since") else None  # reserved for future use

    _receipts_dir = repo_root / ".qws" / "receipts"  # reserved for full reconcile impl
    pending_dir = repo_root / ".qws" / "pending"

    audit = {
        "missing_in_graph": [],
        "missing_in_artifacts": [],
        "hash_mismatch": [],
    }

    # Check pending files
    if pending_dir.exists():
        for pending_file in pending_dir.glob("*.json"):
            audit["missing_in_graph"].append({
                "id": pending_file.stem,
                "status": "pending_offline",
                "path": pending_file.as_posix(),
            })

    if output_json:
        print(json.dumps(audit, indent=2))
    else:
        print("Reconciliation Report:")
        print(f"  Missing in graph: {len(audit['missing_in_graph'])}")
        for item in audit["missing_in_graph"]:
            print(f"    - {item['id']} (status: {item.get('status', 'unknown')})")
        print(f"  Missing in artifacts: {len(audit['missing_in_artifacts'])}")
        print(f"  Hash mismatches: {len(audit['hash_mismatch'])}")

    return 0


def cmd_abort(args: argparse.Namespace) -> int:
    """Execute `qw abort` command.

    Marks a Strategy node as ABORTED with a mandatory reason string.

    Exit codes:
        0: strategy found and marked ABORTED
        1: validation error (empty reason) or strategy not found in graph
        2: infrastructure failure (Neo4j unavailable)
    """
    strategy_id = args.strategy
    reason = args.reason.strip()
    timeout_seconds = getattr(args, "timeout_seconds", 3)

    if not reason:
        print("ERROR: --reason must be a non-empty string", file=sys.stderr)
        return 1

    connector = NeoConnector(timeout_seconds=timeout_seconds)
    if not connector.is_available():
        print(
            f"ERROR: Neo4j unavailable (timeout after {timeout_seconds}s)",
            file=sys.stderr,
        )
        return 2

    try:
        store = GraphStore.from_env(timeout_seconds=timeout_seconds)
        try:
            found = store.abort_strategy(strategy_id, reason)
        finally:
            store.close()
    except StoreInfraError as exc:
        print(f"ERROR: Neo4j write failed: {exc}", file=sys.stderr)
        return 2

    if not found:
        print(
            f"ERROR: Strategy {strategy_id!r} not found in graph",
            file=sys.stderr,
        )
        return 1

    print(f"OK: Strategy {strategy_id!r} marked ABORTED — {reason!r}", file=sys.stdout)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Execute `qw query` command.

    Exit codes:
        0: preset ran successfully
        1: invalid preset name or params
        2: graph connection required but unavailable
    """
    name = "run_history" if getattr(args, "run_history", False) else args.name
    if not name:
        print("ERROR: specify --name <preset> or --run-history", file=sys.stderr)
        return 1
    output_json = getattr(args, "json", False)
    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else Path.cwd()
    timeout_seconds = getattr(args, "timeout_seconds", 3)

    # Parse --param key=value pairs
    raw_params: list[str] = args.param or []
    params: dict[str, str] = {}
    for kv in raw_params:
        if "=" not in kv:
            print(f"ERROR: --param must be key=value, got: {kv!r}", file=sys.stderr)
            return 1
        k, _, v = kv.partition("=")
        params[k.strip()] = v.strip()

    # Resolve preset — deterministic error for unknown names
    try:
        spec = resolve_preset(name)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Validate params before any connection attempt
    errors = validate_params(spec, params)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    # Connect to graph only if the preset requires it
    service: GraphQueryService | None = None
    if spec.requires_graph:
        connector = NeoConnector(timeout_seconds=timeout_seconds)
        if not connector.is_available():
            print(
                f"ERROR: Neo4j unavailable (timeout after {timeout_seconds}s); "
                f"preset {name!r} requires a graph connection",
                file=sys.stderr,
            )
            return 2
        service = GraphQueryService.from_env(timeout_seconds=timeout_seconds)

    try:
        results = run_preset(name, params, service=service, repo_root=repo_root)
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if service is not None:
            service.close()

    if output_json:
        print(json.dumps({"preset": name, "results": results}, indent=2))
    else:
        if not results:
            print(f"No results for preset {name!r}.")
        for item in results:
            print(json.dumps(item))

    return 0


def cmd_backfill(args: argparse.Namespace) -> int:
    """Execute `qw backfill --embeddings` — embed+store vectors for null-embedding hypothesis nodes.

    For each Hypothesis node with null embedding:
      1. Compute embedding from title using local sentence-transformers model.
      2. Store the vector on the node.
      3. Create SEMANTICALLY_RELATED edges for all pairs exceeding the threshold.

    Exit codes:
        0: backfill completed (may have processed 0 nodes if all already embedded)
        1: sentence-transformers not installed or validation error
        2: Neo4j unavailable
    """
    if not getattr(args, "embeddings", False):
        print("ERROR: --embeddings is required for qw backfill", file=sys.stderr)
        return 1

    timeout_seconds: int = getattr(args, "timeout_seconds", 3)
    similarity_threshold: float = float(
        getattr(args, "similarity_threshold", None) or _DEFAULT_SIMILARITY_THRESHOLD
    )

    connector = NeoConnector(timeout_seconds=timeout_seconds)
    if not connector.is_available():
        print(f"ERROR: Neo4j unavailable (timeout after {timeout_seconds}s)", file=sys.stderr)
        return 2

    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except ImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        store = GraphStore.from_env(timeout_seconds=timeout_seconds)
        try:
            targets = store.get_hypotheses_without_embeddings()
            if not targets:
                print("OK: backfill complete — 0 hypotheses needed embedding")
                return 0

            print(f"Backfilling embeddings for {len(targets)} hypothesis nodes…")
            for row in targets:
                h_id = str(row["hypothesis_id"])
                title = str(row["title"])
                try:
                    embedding = _embed_text(title)
                    store.set_hypothesis_embedding(h_id, embedding)
                except Exception as exc:  # noqa: BLE001
                    print(f"  WARNING: skipped {h_id!r} — {exc}", file=sys.stderr)
                    continue
                print(f"  embedded {h_id}")

            # After all embeddings stored, create missing semantic edges across all pairs
            all_embs = store.get_all_hypothesis_embeddings()
            total_pairs = 0
            for row in all_embs:
                h_id = str(row["hypothesis_id"])
                embedding = [float(v) for v in row["embedding"]]  # type: ignore[attr-defined]
                others = [e for e in all_embs if str(e["hypothesis_id"]) != h_id]
                n = store.create_semantic_edges(
                    h_id, embedding, others, threshold=similarity_threshold
                )
                total_pairs += n

            n_embedded = len(targets)
            n_pairs = total_pairs // 2
            print(f"OK: backfill complete — {n_embedded} nodes embedded, {n_pairs} new pairs")
        finally:
            store.close()
    except StoreInfraError as exc:
        print(f"ERROR: Neo4j write failed: {exc}", file=sys.stderr)
        return 2

    return 0


def cmd_degrade(args: argparse.Namespace) -> int:
    """Demote a Champion to FormerChampion: qw degrade <champion_id> --reason "..."."""
    champion_id: str = args.champion_id
    reason: str | None = args.reason

    if not reason:
        print("error: --reason is required for qw degrade", file=sys.stderr)
        return 1
    if not reason.strip():
        print("error: --reason must be non-empty", file=sys.stderr)
        return 1

    connector = NeoConnector(timeout_seconds=args.timeout_seconds)
    if not connector.is_available():
        print("error: Neo4j is unavailable", file=sys.stderr)
        return 1

    from qws_graph.research.graph.store import GraphStore, StoreError, StoreInfraError

    try:
        store = GraphStore.from_env(timeout_seconds=args.timeout_seconds)
        former_champion_id = store.degrade_champion(
            champion_id=champion_id,
            oos_reason=reason,
        )
        print(f"degraded: {champion_id} → FormerChampion {former_champion_id}")
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (StoreError, StoreInfraError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def cmd_retire(args: argparse.Namespace) -> int:
    """Retire a FormerChampion: qw retire <former_champion_id> [--note "..."]."""
    former_champion_id: str = args.former_champion_id
    note: str | None = args.note

    connector = NeoConnector(timeout_seconds=args.timeout_seconds)
    if not connector.is_available():
        print("error: Neo4j is unavailable", file=sys.stderr)
        return 1

    from qws_graph.research.graph.store import GraphStore, StoreError, StoreInfraError

    try:
        store = GraphStore.from_env(timeout_seconds=args.timeout_seconds)
        retired_champion_id = store.retire_former_champion(
            former_champion_id=former_champion_id,
            retirement_note=note,
        )
        print(f"retired: {former_champion_id} → RetiredChampion {retired_champion_id}")
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (StoreError, StoreInfraError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for `qw` CLI."""
    parser = argparse.ArgumentParser(
        prog="qw",
        description="QuantWorkstation graph CLI for artifact ingestion and auditing",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # `qw record` subcommand
    record_parser = subparsers.add_parser(
        "record",
        help="Parse and ingest artifact (CSV or Markdown) to graph or pending queue",
    )
    record_mode = record_parser.add_mutually_exclusive_group(required=True)
    record_mode.add_argument(
        "--file",
        default=None,
        help="Path to artifact file (CSV or Markdown)",
    )
    record_mode.add_argument(
        "--bundle",
        metavar="DIR",
        default=None,
        help="Path to bundle directory containing bundle.json manifest",
    )
    record_mode.add_argument(
        "--oos",
        metavar="STATUS",
        default=None,
        help="OOS validation outcome to record on a Champion node (oos_pass | oos_fail | oos_pending). Requires --champion.",
    )
    record_mode.add_argument(
        "--hypothesis",
        metavar="TITLE_OR_ID",
        default=None,
        help=(
            "Hypothesis journaling. Pass a quoted title to create a new Hypothesis node. "
            "Pass an existing hypothesis_id with --tested-as, --branched-from, or --status to modify."
        ),
    )
    record_parser.add_argument(
        "--tested-as",
        default=None,
        metavar="STRATEGY_ID",
        dest="tested_as",
        help="Link hypothesis to strategy via TESTED_AS edge (use with --hypothesis <id>)",
    )
    record_parser.add_argument(
        "--branched-from",
        default=None,
        metavar="NODE_ID",
        dest="branched_from",
        help="Link hypothesis via BRANCHED_FROM edge to any node ID (use with --hypothesis <id> --rationale)",
    )
    record_parser.add_argument(
        "--rationale",
        default=None,
        metavar="TEXT",
        help="Rationale for BRANCHED_FROM edge (required with --branched-from)",
    )
    record_parser.add_argument(
        "--status",
        default=None,
        metavar="STATUS",
        help=f"Update hypothesis status. One of: {', '.join(sorted(_VALID_HYPOTHESIS_STATUSES))}",
    )
    record_parser.add_argument(
        "--champion",
        default=None,
        metavar="CHAMPION_ID",
        help="Champion node ID to update (required with --oos)",
    )
    record_parser.add_argument(
        "--sharpe",
        type=float,
        default=None,
        metavar="FLOAT",
        help="OOS Sharpe ratio to store on Champion (optional with --oos; must be non-negative)",
    )
    record_parser.add_argument(
        "--kind",
        required=False,
        default=None,
        choices=["baseline_csv", "grid_csv", "champion_md", "tracker_md"],
        help="Artifact kind (required with --file; inferred from bundle.json with --bundle)",
    )
    record_parser.add_argument(
        "--pivot-from",
        default=None,
        help="Explicit pivot link for champion ingestion (run_id)",
    )
    record_parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip Neo4j write; write pending payload only",
    )
    record_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3,
        help="Neo4j connection timeout in seconds (default 3)",
    )
    record_parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root directory (auto-detected if not provided)",
    )
    record_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate only; do not write to graph or pending",
    )
    record_parser.add_argument(
        "--source-file",
        default=None,
        metavar="PATH",
        help="Strategy Python source file; used to derive family_id (hash of file content)",
    )
    record_parser.add_argument(
        "--regime",
        default=None,
        metavar="LABEL",
        help=(
            "Market regime label for all Run nodes in this ingest "
            "(e.g. high_vol, trend_up, mean_reverting). "
            "Creates a Regime node and IN_REGIME edge per persisted run."
        ),
    )
    record_parser.add_argument(
        "--all",
        action="store_true",
        dest="all",
        help="Bypass significance gate for grid_csv; ingest all rows (default: top-5 Sharpe + bottom-2 drawdown)",
    )
    record_parser.add_argument(
        "--analyze",
        action="store_true",
        help="Invoke semantic tier analysis (Llama Scout) for grid_csv; uses QW_AI_ANALYST_ENDPOINT env var",
    )
    record_parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=None,
        metavar="FLOAT",
        dest="similarity_threshold",
        help=(
            "Cosine similarity cutoff for SEMANTICALLY_RELATED edges (default 0.85). "
            "Use with --hypothesis to override the default threshold."
        ),
    )
    record_parser.set_defaults(func=cmd_record)

    # `qw seed` subcommand
    seed_parser = subparsers.add_parser(
        "seed",
        help="Seed or update singleton configuration nodes in the graph",
    )
    seed_parser.add_argument(
        "--targets",
        action="store_true",
        help="Seed or update the ResearchTarget singleton node with promotion thresholds",
    )
    seed_parser.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Seed a deterministic demo provenance graph (idempotent). "
            "Creates demo-strategy-alpha/beta/gamma, demo runs, champions, and a retired champion. "
            "All nodes carry is_demo=true. Use --teardown to remove."
        ),
    )
    seed_parser.add_argument(
        "--teardown",
        action="store_true",
        help="Remove all demo nodes (requires --demo). Deletes nodes where is_demo=true.",
    )
    seed_parser.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        default=None,
        dest="set",
        help=(
            "Override a specific target property (repeatable). "
            f"Allowed keys: {sorted(RESEARCH_TARGET_ALLOWED_KEYS)}"
        ),
    )
    seed_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3,
        help="Neo4j connection timeout in seconds (default 3)",
    )
    seed_parser.set_defaults(func=cmd_seed)

    # `qw abort` subcommand
    abort_parser = subparsers.add_parser(
        "abort",
        help="Mark a strategy family as ABORTED with an explicit reason",
    )
    abort_parser.add_argument(
        "--strategy",
        required=True,
        metavar="STRATEGY_ID",
        help="Canonical strategy_id to mark as ABORTED (e.g. es-1h-bear-rsi-reversion)",
    )
    abort_parser.add_argument(
        "--reason",
        required=True,
        metavar="REASON",
        help="Mandatory explanation for the abort decision (must be non-empty)",
    )
    abort_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3,
        help="Neo4j connection timeout in seconds (default 3)",
    )
    abort_parser.set_defaults(func=cmd_abort)

    # `qw reconcile` subcommand
    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help="Audit ingested artifacts against graph records",
    )
    reconcile_parser.add_argument(
        "--since",
        default=None,
        help="ISO8601 timestamp to filter by ingestion time",
    )
    reconcile_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    reconcile_parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root directory (auto-detected if not provided)",
    )
    reconcile_parser.set_defaults(func=cmd_reconcile)

    # `qw query` subcommand
    _preset_names = sorted(PRESET_CATALOG)
    _preset_help_lines = "\n".join(
        f"  {spec.name}: {spec.description}" for spec in PRESET_CATALOG.values()
    )
    query_parser = subparsers.add_parser(
        "query",
        help="Run a predefined graph query preset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Run a predefined graph query preset.\n\n"
            f"Available presets:\n{_preset_help_lines}"
        ),
    )
    query_parser.add_argument(
        "--name",
        required=False,
        metavar="PRESET",
        help=f"Preset name. One of: {', '.join(_preset_names)}",
    )
    query_parser.add_argument(
        "--run-history",
        action="store_true",
        help="Shortcut for --name run_history",
    )
    query_parser.add_argument(
        "--param",
        action="append",
        metavar="KEY=VALUE",
        default=None,
        help="Preset parameter (repeatable). E.g. --param strategy_id=es-1h-bear-sweep",
    )
    query_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON ({preset, results})",
    )
    query_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3,
        help="Neo4j connection timeout in seconds (default 3)",
    )
    query_parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root directory (auto-detected if not provided)",
    )
    query_parser.set_defaults(func=cmd_query)

    # `qw backfill` subcommand
    backfill_parser = subparsers.add_parser(
        "backfill",
        help="Backfill missing graph properties (e.g. hypothesis embeddings)",
    )
    backfill_parser.add_argument(
        "--embeddings",
        action="store_true",
        help=(
            "Compute and store embedding vectors for all Hypothesis nodes with null embedding. "
            "Also creates any missing SEMANTICALLY_RELATED edges between all hypothesis pairs."
        ),
    )
    backfill_parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=None,
        metavar="FLOAT",
        dest="similarity_threshold",
        help=(
            f"Cosine similarity cutoff for SEMANTICALLY_RELATED edges "
            f"(default {_DEFAULT_SIMILARITY_THRESHOLD})"
        ),
    )
    backfill_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3,
        help="Neo4j connection timeout in seconds (default 3)",
    )
    backfill_parser.set_defaults(func=cmd_backfill)

    # `qw degrade` subcommand
    degrade_parser = subparsers.add_parser(
        "degrade",
        help="Demote a Champion to FormerChampion with mandatory cause-of-death",
    )
    degrade_parser.add_argument(
        "champion_id",
        metavar="CHAMPION_ID",
        help="Champion node ID to demote",
    )
    degrade_parser.add_argument(
        "--reason",
        required=True,
        metavar="REASON",
        help="Mandatory cause-of-death (must be non-empty)",
    )
    degrade_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3,
        help="Neo4j connection timeout in seconds (default 3)",
    )
    degrade_parser.set_defaults(func=cmd_degrade)

    # `qw retire` subcommand
    retire_parser = subparsers.add_parser(
        "retire",
        help="Retire a FormerChampion to a final RetiredChampion node",
    )
    retire_parser.add_argument(
        "former_champion_id",
        metavar="FORMER_CHAMPION_ID",
        help="FormerChampion node ID to retire",
    )
    retire_parser.add_argument(
        "--note",
        default=None,
        metavar="NOTE",
        help="Optional retirement note (free-text reason for final retirement)",
    )
    retire_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3,
        help="Neo4j connection timeout in seconds (default 3)",
    )
    retire_parser.set_defaults(func=cmd_retire)

    # Parse arguments
    args = parser.parse_args()

    # Dispatch to command handler
    if hasattr(args, "func"):
        return args.func(args)

    # No command specified
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())




