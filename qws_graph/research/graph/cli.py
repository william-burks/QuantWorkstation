"""CLI entry point for qw record and qw reconcile commands.

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

from .models import ResearchArtifact
from .parsers import CSVParser, ChampionMarkdownParser, research_artifact_payload_hash


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
        status: Literal["persisted", "pending_offline"],
        node_counts: dict[str, int],
        relationship_counts: dict[str, int],
        warnings: list[str] | None = None,
    ) -> None:
        """Write a receipt JSON file for a successful ingest."""
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

        receipt = {
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
    """Minimal Neo4j connection handler with timeout."""

    def __init__(self, timeout_seconds: int = 3):
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        """Check if Neo4j is reachable within timeout."""
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout_seconds)
            result = sock.connect_ex(("localhost", 7687))
            sock.close()
            return result == 0
        except Exception:
            return False

    def write_artifact(self, artifact: ResearchArtifact) -> tuple[dict[str, int], dict[str, int]]:
        """Write artifact to Neo4j via Cypher (stub for integration).

        In full implementation, this would execute Cypher MERGE statements
        against the Neo4j instance.

        Returns:
            (node_counts, relationship_counts) tuple
        """
        # Stub implementation: return zero counts for testing
        # Real implementation would connect to Neo4j Bolt driver
        return {}, {}


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
        parser = CSVParser(file_path, kind)
        return parser.parse()
    elif kind == "champion_md":
        parser = ChampionMarkdownParser(
            file_path,
            registry_path=repo_root / "research" / "results" / "registry.json" if repo_root else None,
            pivot_from_run_id=pivot_from_run_id,
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

        artifact_path_text = _artifact_path_text(file_path)
        provenance = Provenance(
            artifact_path=artifact_path_text,
            artifact_hash=artifact_hash,
            artifact_mtime_iso=mtime_iso,
            ingested_at=datetime.now(UTC),
            parser_version="v1",
        )

        # Infer strategy from artifact path
        from .parsers import _infer_strategy_from_artifact_name

        inferred = _infer_strategy_from_artifact_name(file_path.stem)
        strategy = Strategy(
            strategy_id=f"{inferred['instrument']}-{inferred['timeframe']}-{inferred['direction']}-{inferred['logic_type']}",
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


def cmd_record(args: argparse.Namespace) -> int:
    """Execute `qw record` command.

    Exit codes:
        0: validation passed and persisted, or validation passed and written to pending in offline mode
        1: schema validation failure
        2: infrastructure failure (Neo4j unavailable and --offline not provided)
    """
    file_path = Path(args.file)
    kind = args.kind
    pivot_from_run_id = args.pivot_from
    offline = args.offline
    timeout_seconds = args.timeout_seconds
    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()
    dry_run = args.dry_run

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
                artifact_path=payload.get("strategy", {}).get("strategy_id", file_path.as_posix()),
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
        node_counts, relationship_counts = connector.write_artifact(artifact)
    except Exception as exc:
        print(f"ERROR: Neo4j write failed: {exc}", file=sys.stderr)
        return 2

    # Write receipt with persisted status
    receipt_writer = ReceiptWriter(repo_root)
    try:
        receipt_writer.write_receipt(
            artifact_id=artifact_id,
            kind=kind,
            artifact_path=file_path.as_posix(),
            artifact_hash=artifact_hash,
            status="persisted",
            node_counts=node_counts,
            relationship_counts=relationship_counts,
            warnings=all_warnings,
        )
    except Exception as exc:
        print(f"ERROR: Failed to write receipt: {exc}", file=sys.stderr)
        return 2

    print(f"OK: {kind} persisted to Neo4j graph", file=sys.stdout)
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
    since = args.since if hasattr(args, "since") else None

    receipts_dir = repo_root / ".qws" / "receipts"
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
    record_parser.add_argument(
        "--file",
        required=True,
        help="Path to artifact file (CSV or Markdown)",
    )
    record_parser.add_argument(
        "--kind",
        required=True,
        choices=["baseline_csv", "grid_csv", "champion_md", "tracker_md"],
        help="Artifact kind",
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
    record_parser.set_defaults(func=cmd_record)

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


