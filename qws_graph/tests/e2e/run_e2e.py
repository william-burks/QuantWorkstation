#!/usr/bin/env python3
"""
E2E functional test runner for `qw record`.

Runs every fixture through the real qw CLI against live Neo4j,
verifies expected stdout and graph state, then prompts before cleanup.

Usage (from repo root):
    python qws_graph/tests/e2e/run_e2e.py
    python qws_graph/tests/e2e/run_e2e.py --no-cleanup
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]  # QuantWorkstation/
QWS_GRAPH_ROOT = REPO_ROOT / "qws_graph"
FIXTURES = QWS_GRAPH_ROOT / "tests" / "fixtures" / "artifacts"

NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

# ---------------------------------------------------------------------------
# Test case definitions
# ---------------------------------------------------------------------------

@dataclass
class E2ECase:
    name: str
    kind: str
    fixture: Path
    strategy_id: str                     # used for targeted graph queries
    expect_promotion: bool               # at least one PROMOTION CANDIDATE in stdout
    expect_institutional: bool = False   # tier=institutional in stdout
    expect_run_count: int = 0            # delta Run nodes expected (0 = skip)
    expect_pivot: bool = False           # this strategy's champion has PIVOTED_FROM
    expect_no_pivot: bool = False        # this strategy's champion has no PIVOTED_FROM
    expect_blob: bool = False            # BlobArtifact node created for this strategy
    pivot_from_strategy: str = ""        # if set, runner queries a real run_id for this
                                         # strategy and passes it as --pivot-from at ingest


CASES: list[E2ECase] = [
    E2ECase(
        name="qualifying baseline → professional alert",
        kind="baseline_csv",
        fixture=FIXTURES / "baseline" / "promotion_alert_qualifying.csv",
        strategy_id="cl-1h-bear-liquidity-sweep",
        expect_promotion=True,
        expect_run_count=1,
    ),
    E2ECase(
        name="multi-run mixed tiers → institutional + professional alerts",
        kind="baseline_csv",
        fixture=FIXTURES / "baseline" / "multi_run_mixed_tiers.csv",
        strategy_id="cl-1h-bear-liquidity-sweep",
        expect_promotion=True,
        expect_institutional=True,
        expect_run_count=2,  # institutional + professional rows (low-sharpe + null-AWF skipped)
    ),
    E2ECase(
        # run may be skipped by significance gate if a matching run already exists;
        # the only assertion is that no alert fires
        name="low sharpe baseline → no alert",
        kind="baseline_csv",
        fixture=FIXTURES / "baseline" / "promotion_alert_low_sharpe.csv",
        strategy_id="cl-1h-bear-liquidity-sweep",
        expect_promotion=False,
    ),
    E2ECase(
        name="with duty cycle baseline → no alert (pf below threshold)",
        kind="baseline_csv",
        fixture=FIXTURES / "baseline" / "with_duty_cycle.csv",
        strategy_id="es-1h-bear-baseline",
        expect_promotion=False,
        expect_run_count=1,
    ),
    E2ECase(
        name="grid with explicit strategy cols → no alert",
        kind="grid_csv",
        fixture=FIXTURES / "grid" / "explicit_strategy_cols.csv",
        strategy_id="es-1h-bear-liquidity-sweep",
        expect_promotion=False,
        expect_run_count=3,
    ),
    E2ECase(
        # ingest ES sweep grid to create runs so champion_md can reference a real run_id
        name="es-1h-bear-sweep grid → runs exist for champion pivot",
        kind="grid_csv",
        fixture=FIXTURES / "grid" / "es_bear_sweep_1h_grid_nypre_london_v1_fixture.txt",
        strategy_id="es-1h-bear-sweep",
        expect_promotion=False,
        expect_run_count=3,
    ),
    E2ECase(
        # runner queries a real run_id for es-1h-bear-sweep and passes --pivot-from at ingest
        name="champion_md → es-1h-bear-sweep has PIVOTED_FROM edge",
        kind="champion_md",
        fixture=FIXTURES / "champion" / "es_bear_sweep_1h_v1.md",
        strategy_id="es-1h-bear-sweep",
        expect_promotion=False,
        expect_pivot=True,
        pivot_from_strategy="es-1h-bear-sweep",
    ),
    E2ECase(
        # cl auto-promoted in case 1 with PIVOTED_FROM; champion_md without pivot_from
        # must not remove that existing edge — verify edge is still present after ingest
        name="champion_md without pivot_from → existing PIVOTED_FROM preserved",
        kind="champion_md",
        fixture=FIXTURES / "champion" / "cl_bear_sweep_1h_no_pivot.md",
        strategy_id="cl-1h-bear-liquidity-sweep",
        expect_promotion=False,
        expect_pivot=True,
    ),
    E2ECase(
        name="tracker blob → BlobArtifact node for es-1h-bear-sweep",
        kind="tracker_md",
        fixture=FIXTURES / "tracker" / "es_bear_sweep_1h_tracker.md",
        strategy_id="es-1h-bear-sweep",
        expect_promotion=False,
        expect_blob=True,
    ),
]

# ---------------------------------------------------------------------------
# Neo4j helpers
# ---------------------------------------------------------------------------

def _connect():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        _fatal("neo4j driver not installed: pip install neo4j")
        raise SystemExit(1)  # unreachable; satisfies type checker
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), connection_timeout=3)
    try:
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        _fatal(f"Neo4j not reachable at {NEO4J_URI}: {exc}")
    return driver


def _node_element_ids(driver) -> set[str]:
    """Return element IDs of every node currently in the graph."""
    with driver.session(database="neo4j") as s:
        records = s.run("MATCH (n) RETURN elementId(n) AS eid").data()
    return {r["eid"] for r in records}


def _query_counts(driver) -> dict[str, int]:
    """Node and relationship counts for reporting.

    Uses OPTIONAL MATCH throughout to avoid unknown-label notifications from Neo4j
    when a label hasn't been created yet (e.g. BlobArtifact on first run).
    """
    with driver.session(database="neo4j") as s:
        def c(q):
            return s.run(q).single()["c"]
        return {
            "Strategy": c("OPTIONAL MATCH (n:Strategy) RETURN count(n) AS c"),
            "Run": c("OPTIONAL MATCH (n:Run) RETURN count(n) AS c"),
            "Config": c("OPTIONAL MATCH (n:Config) RETURN count(n) AS c"),
            "Champion": c("OPTIONAL MATCH (n:Champion) RETURN count(n) AS c"),
            "BlobArtifact": c("OPTIONAL MATCH (n:BlobArtifact) RETURN count(n) AS c"),
            "HAS_RUN": c("OPTIONAL MATCH ()-[r:HAS_RUN]->() RETURN count(r) AS c"),
            "PIVOTED_FROM": c("OPTIONAL MATCH ()-[r:PIVOTED_FROM]->() RETURN count(r) AS c"),
        }


def _strategy_pivot_count(driver, strategy_id: str) -> int:
    """Count PIVOTED_FROM edges on the Champion for this strategy."""
    with driver.session(database="neo4j") as s:
        result = s.run(
            "OPTIONAL MATCH (:Strategy {strategy_id: $sid})-[:PRODUCED_CHAMPION]->(c:Champion)-[:PIVOTED_FROM]->() "
            "RETURN count(c) AS c",
            sid=strategy_id,
        ).single()
        return result["c"]


def _latest_run_id(driver, strategy_id: str) -> str | None:
    """Return any run_id for this strategy (used to populate --pivot-from at ingest time)."""
    with driver.session(database="neo4j") as s:
        result = s.run(
            "OPTIONAL MATCH (:Strategy {strategy_id: $sid})-[:HAS_RUN]->(r:Run) "
            "RETURN r.run_id AS rid LIMIT 1",
            sid=strategy_id,
        ).single()
        return result["rid"] if result else None


def _strategy_blob_count(driver, strategy_id: str) -> int:
    """Count BlobArtifact nodes for this strategy."""
    with driver.session(database="neo4j") as s:
        result = s.run(
            "OPTIONAL MATCH (:Strategy {strategy_id: $sid})-[:HAS_BLOB]->(b:BlobArtifact) "
            "RETURN count(b) AS c",
            sid=strategy_id,
        ).single()
        return result["c"]


def _delete_nodes_by_element_ids(driver, eids: set[str]) -> int:
    if not eids:
        return 0
    with driver.session(database="neo4j") as s:
        result = s.run(
            "MATCH (n) WHERE elementId(n) IN $eids DETACH DELETE n RETURN count(*) AS c",
            eids=list(eids),
        ).single()
        return result["c"] if result else 0

# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"


@dataclass
class CaseResult:
    case: E2ECase
    stdout: str
    exit_code: int
    before: dict[str, int]
    after: dict[str, int]
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and len(self.failures) == 0

    def delta(self) -> dict[str, int]:
        return {k: self.after[k] - self.before[k] for k in self.before}


def _fatal(msg: str) -> None:
    print(f"\n{FAIL} {msg}", file=sys.stderr)
    sys.exit(1)


def _check(result: CaseResult, driver) -> None:
    stdout = result.stdout
    case = result.case
    delta = result.delta()

    if result.exit_code != 0:
        result.failures.append(f"non-zero exit code: {result.exit_code}")

    # Promotion alert checks
    if case.expect_promotion and "[PROMOTION CANDIDATE]" not in stdout:
        result.failures.append("expected [PROMOTION CANDIDATE] in stdout — not found")
    if not case.expect_promotion and "[PROMOTION CANDIDATE]" in stdout:
        result.failures.append("unexpected [PROMOTION CANDIDATE] in stdout")
    if case.expect_institutional and "tier=institutional" not in stdout:
        result.failures.append("expected tier=institutional in stdout — not found")

    # Run count delta — valid on a clean graph (cleanup always runs between test sessions)
    if case.expect_run_count > 0:
        actual = delta.get("Run", 0)
        if actual < case.expect_run_count:
            result.failures.append(f"expected ≥{case.expect_run_count} new Run nodes, got {actual}")

    # Champion checks — query graph state directly; delta is unreliable because champion_md
    # MERGEs a node that auto-promotion may have already created from an earlier baseline ingest
    if case.kind == "champion_md":
        if result.after.get("Champion", 0) < 1:
            result.failures.append("expected at least one Champion node in graph")
    if case.expect_pivot:
        if _strategy_pivot_count(driver, case.strategy_id) < 1:
            result.failures.append(f"expected PIVOTED_FROM edge on champion for {case.strategy_id}")
    if case.expect_no_pivot:
        if _strategy_pivot_count(driver, case.strategy_id) > 0:
            result.failures.append(f"expected no PIVOTED_FROM edge on champion for {case.strategy_id}")

    # BlobArtifact — query by strategy to avoid cross-strategy false positives
    if case.expect_blob:
        if _strategy_blob_count(driver, case.strategy_id) < 1:
            result.failures.append(f"expected BlobArtifact node for {case.strategy_id}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_case(case: E2ECase, driver) -> CaseResult:
    before = _query_counts(driver)
    before_eids = _node_element_ids(driver)

    cmd = ["qw", "record", "--kind", case.kind, "--file", str(case.fixture)]
    if case.pivot_from_strategy:
        run_id = _latest_run_id(driver, case.pivot_from_strategy)
        if run_id:
            cmd += ["--pivot-from", run_id]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stdout = proc.stdout + proc.stderr

    after = _query_counts(driver)
    after_eids = _node_element_ids(driver)

    result = CaseResult(
        case=case,
        stdout=stdout,
        exit_code=proc.returncode,
        before=before,
        after=after,
    )
    _check(result, driver)

    # Attach new eids to result for cleanup tracking
    result._new_eids = after_eids - before_eids  # type: ignore[attr-defined]
    return result


def print_result(i: int, total: int, result: CaseResult) -> None:
    tag = PASS if result.passed else FAIL
    delta = result.delta()
    delta_str = "  ".join(f"+{v} {k}" for k, v in delta.items() if v > 0)

    print(f"\n[{i}/{total}] {result.case.name}")
    print(f"  fixture : {result.case.fixture.name}")
    print(f"  kind    : {result.case.kind}")
    print(f"  exit    : {result.exit_code}")
    if delta_str:
        print(f"  nodes   : {delta_str}")

    # Show relevant stdout lines
    relevant = [
        ln for ln in result.stdout.splitlines()
        if any(kw in ln for kw in ("[PROMOTION", "[PROMOTED]", "[SKIPPED]", "OK:", "ERROR"))
    ]
    for ln in relevant[:8]:
        print(f"  │ {ln}")

    if result.failures:
        for f in result.failures:
            print(f"  {FAIL}  {f}")
    else:
        print(f"  {tag}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _wipe_graph(driver) -> None:
    with driver.session(database="neo4j") as s:
        s.run("MATCH (n) DETACH DELETE n").consume()

def _cleanup_nodes(driver, eids: set[str]) -> None:
    deleted = _delete_nodes_by_element_ids(driver, eids)
    print(f"Deleted {deleted} nodes.")


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E test runner for qw record")
    parser.add_argument("--no-cleanup", action="store_true", help="Ask User cleanup prompt after run")
    parser.add_argument("--clean", action="store_true", help="Wipe graph before running (required for delta checks)")
    args = parser.parse_args()

    print("=" * 60)
    print("E2E Test Runner — qw record")
    print(f"Neo4j: {NEO4J_URI}")
    print(f"Fixtures: {FIXTURES}")
    print("=" * 60)

    driver = _connect()

    if args.clean:
        counts = _query_counts(driver)
        total = sum(v for k, v in counts.items() if "_" not in k)
        if total > 0:
            print(f"\nGraph has {total} nodes. Wiping before run...")
            _wipe_graph(driver)
            print("Graph cleared.")
        else:
            print("\nGraph already empty.")
    try:
        results: list[CaseResult] = []
        all_new_eids: set[str] = set()

        for i, case in enumerate(CASES, 1):
            if not case.fixture.exists():
                print(f"\n[{i}/{len(CASES)}] SKIP — fixture missing: {case.fixture}")
                continue
            result = run_case(case, driver)
            print_result(i, len(CASES), result)
            results.append(result)
            all_new_eids |= getattr(result, "_new_eids", set())

        # Summary
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        print(f"\n{'=' * 60}")
        print(f"Results: {passed}/{total} passed")

        failed = [r for r in results if not r.passed]
        if failed:
            print(f"\nFailed cases:")
            for r in failed:
                print(f"  - {r.case.name}")
                for f in r.failures:
                    print(f"      {f}")

        final_counts = _query_counts(driver)
        print(f"\nNodes added during test run: {len(all_new_eids)}")
        for label, count in {k: v for k, v in final_counts.items() if "_" not in k}.items():
            print(f"  {label}: {count}")

        print()
        if args.no_cleanup:
            answer = input("Delete test nodes? [y/N]: ").strip().lower()
            if answer == "y":
                _cleanup_nodes(driver, all_new_eids)
            else:
                print("Nodes preserved.")
        else:
            _cleanup_nodes(driver, all_new_eids)

    finally:
        driver.close()

    if any(not r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()