"""Strategy class backfill helper (QWS-1012).

The interactive ``qw backfill --strategy-class`` command is implemented in
``qws_graph.research.graph.cli._cmd_backfill_strategy_class``.

This module documents the expected GraphStore API surface used by the backfill command:

    store.get_unclassified_strategies() -> list[dict]
        Returns Strategy nodes where strategy_class IS NULL (non-ABORTED), ordered
        by created_at DESC.  Each dict contains:
            strategy_id, instrument, timeframe, direction, logic_type.

    store.patch_strategy_class(strategy_id: str, strategy_class: str) -> bool
        Sets strategy_class on the Strategy node.  Returns True if found.

    store.run_adhoc_cypher(cypher: str) -> list[dict]
        Read-only passthrough; used here to fetch distinct existing classes.

Example bundle.json fragment that sets strategy_class at ingest time::

    {
        "files": {"csv": "results.csv", "csv_kind": "baseline_csv"},
        "strategy_class": "liquidity_sweep"
    }
"""
