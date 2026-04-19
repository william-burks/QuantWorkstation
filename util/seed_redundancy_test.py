"""Seed script for QWS-1404: known-overlap fixture for check_redundancy testing.

Creates a Hypothesis with:
  - 2 active champion strategies whose strategy_id contains the hypothesis title keyword
  - 1 aborted strategy whose strategy_id contains the hypothesis title keyword
  - 1 SEMANTICALLY_RELATED hypothesis

Usage:
    source .venv/bin/activate
    python util/seed_redundancy_test.py --seed    # create fixture
    python util/seed_redundancy_test.py --teardown  # remove fixture

Environment: requires GRAPH_URI, GRAPH_USER, GRAPH_PASSWORD in .env or environment.
"""

from __future__ import annotations

import argparse
import os
import sys

from neo4j import Driver, GraphDatabase

SEED_CYPHER = """
// Hypothesis under test
MERGE (h:Hypothesis {hypothesis_id: 'redundancy_test_h001'})
SET h.title = 'redundancy-test-sweep-liquidity',
    h.status = 'open',
    h.queued = false,
    h.is_demo = true,
    h.created_at = datetime(),
    h.updated_at = datetime()

// Active strategy 1 — strategy_id contains 'redundancy-test-sweep-liquidity'
MERGE (s1:Strategy {strategy_id: 'redundancy-test-sweep-liquidity-mes-1h-long'})
SET s1.is_demo = true, s1.status = 'ACTIVE'

// Champion for s1
MERGE (ch1:Champion {champion_id: 'redundancy_test_ch001'})
SET ch1.strategy_id = s1.strategy_id, ch1.is_demo = true,
    ch1.metrics_sharpe = 2.5, ch1.tier = 'professional'
MERGE (s1)-[:PRODUCED_CHAMPION]->(ch1)

// Active strategy 2 — also contains the keyword
MERGE (s2:Strategy {strategy_id: 'redundancy-test-sweep-liquidity-cl-1h-short'})
SET s2.is_demo = true, s2.status = 'ACTIVE'

// Champion for s2
MERGE (ch2:Champion {champion_id: 'redundancy_test_ch002'})
SET ch2.strategy_id = s2.strategy_id, ch2.is_demo = true,
    ch2.metrics_sharpe = 2.1, ch2.tier = 'professional'
MERGE (s2)-[:PRODUCED_CHAMPION]->(ch2)

// Aborted strategy — contains the keyword
MERGE (sa:Strategy {strategy_id: 'redundancy-test-sweep-liquidity-mnq-1h-long'})
SET sa.is_demo = true, sa.status = 'ABORTED', sa.abort_reason = 'test fixture'

// Semantically related hypothesis
MERGE (h2:Hypothesis {hypothesis_id: 'redundancy_test_h002'})
SET h2.title = 'redundancy-test-related-hypothesis',
    h2.status = 'open',
    h2.queued = false,
    h2.is_demo = true,
    h2.created_at = datetime(),
    h2.updated_at = datetime()
MERGE (h)-[sr:SEMANTICALLY_RELATED]->(h2)
SET sr.similarity = 0.87,
    sr.pair_key = 'redundancy_test_h001|redundancy_test_h002',
    sr.computed_at = datetime()
"""

TEARDOWN_CYPHER = """
MATCH (h:Hypothesis) WHERE h.hypothesis_id IN ['redundancy_test_h001', 'redundancy_test_h002'] DETACH DELETE h
MATCH (s:Strategy) WHERE s.strategy_id STARTS WITH 'redundancy-test-sweep-liquidity' DETACH DELETE s
MATCH (ch:Champion) WHERE ch.champion_id IN ['redundancy_test_ch001', 'redundancy_test_ch002'] DETACH DELETE ch
"""


def _driver() -> Driver:
    uri = os.environ.get("GRAPH_URI", "bolt://localhost:7687")
    user = os.environ.get("GRAPH_USER", "neo4j")
    password = os.environ.get("GRAPH_PASSWORD", "")
    if not password:
        print("ERROR: GRAPH_PASSWORD not set", file=sys.stderr)
        sys.exit(1)
    return GraphDatabase.driver(uri, auth=(user, password))


def seed() -> None:
    driver = _driver()
    with driver.session() as session:
        session.run(SEED_CYPHER)
    driver.close()
    print("Seeded redundancy test fixture.")
    print("  hypothesis_id: redundancy_test_h001")
    print("  active champions: redundancy_test_ch001, redundancy_test_ch002")
    print("  aborted strategy: redundancy-test-sweep-liquidity-mnq-1h-long")
    print("  semantic match: redundancy_test_h002")


def teardown() -> None:
    driver = _driver()
    with driver.session() as session:
        session.run(TEARDOWN_CYPHER)
    driver.close()
    print("Teardown complete — redundancy test fixture removed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed/teardown redundancy test fixture.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--seed", action="store_true", help="Create test fixture nodes")
    group.add_argument("--teardown", action="store_true", help="Remove test fixture nodes")
    args = parser.parse_args()

    if args.seed:
        seed()
    else:
        teardown()


if __name__ == "__main__":
    main()
