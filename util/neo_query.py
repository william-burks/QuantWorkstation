"""Temporary read-only Cypher shell for ad-hoc graph exploration.

Usage:
    python util/neo_query.py "MATCH (s:Strategy) RETURN s.strategy_id LIMIT 10"
    python util/neo_query.py --pretty "MATCH (c:Champion) RETURN c LIMIT 5"
    python util/neo_query.py --csv "MATCH (s:Strategy) RETURN s.strategy_id, s.logic_type"

Delete this file when done. Not a permanent tool — use qw query for preset queries.
"""
import argparse
import csv
import json
import os
import sys

_WRITE_KEYWORDS = {"CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DROP", "CALL", "LOAD"}


def _check_readonly(cypher: str) -> None:
    first = cypher.strip().split()[0].upper()
    if first in _WRITE_KEYWORDS:
        print(f"ERROR: write operations not allowed (starts with {first!r})", file=sys.stderr)
        sys.exit(1)


def _get_driver():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("ERROR: neo4j driver not installed. Run: pip install neo4j", file=sys.stderr)
        sys.exit(1)

    scheme = os.getenv("QW_GRAPH_SCHEME", "bolt")
    host = os.getenv("QW_GRAPH_HOST", "localhost")
    port = os.getenv("QW_GRAPH_PORT", "7687")
    user = os.getenv("QW_GRAPH_USER", "neo4j")
    password = os.getenv("QW_GRAPH_PASSWORD", "password")
    database = os.getenv("QW_GRAPH_DATABASE", "neo4j")
    uri = f"{scheme}://{host}:{port}"

    driver = GraphDatabase.driver(uri, auth=(user, password))
    return driver, database


def run_query(cypher: str, params: dict | None = None) -> list[dict]:
    driver, database = _get_driver()
    try:
        with driver.session(database=database) as session:
            result = session.run(cypher, **(params or {}))
            return [dict(record) for record in result]
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only ad-hoc Cypher queries against Neo4j")
    parser.add_argument("cypher", help="Cypher query string (MATCH ... RETURN ...)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--csv", action="store_true", help="Output as CSV")
    parser.add_argument("--count", action="store_true", help="Print row count only")
    args = parser.parse_args()

    _check_readonly(args.cypher)

    try:
        rows = run_query(args.cypher)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print("(no results)")
        return

    if args.count:
        print(len(rows))
        return

    if args.csv:
        writer = csv.DictWriter(sys.stdout, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return

    indent = 2 if args.pretty else None
    for row in rows:
        print(json.dumps(row, indent=indent, default=str))


if __name__ == "__main__":
    main()
