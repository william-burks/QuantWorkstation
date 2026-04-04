"""Cypher statements for Graph V1 artifact persistence.

These mappings mirror docs/graph_v1_contract.md.
"""

CSV_INGEST_QUERY = """
UNWIND $rows AS row
MERGE (s:Strategy {strategy_id: row.strategy.strategy_id})
  ON CREATE SET
    s.instrument = row.strategy.instrument,
    s.timeframe = row.strategy.timeframe,
    s.direction = row.strategy.direction,
    s.logic_type = row.strategy.logic_type,
    s.created_at = datetime()
  SET
    s.updated_at = datetime()

MERGE (r:Run {run_id: row.run.run_id})
  ON CREATE SET
    r.created_at = datetime()
  SET
    r.timestamp = datetime(row.run.timestamp),
    r.sharpe = row.run.sharpe,
    r.profit_factor = row.run.profit_factor,
    r.win_rate = row.run.win_rate,
    r.max_drawdown = row.run.max_drawdown,
    r.total_trades = row.run.total_trades,
    r.total_r = row.run.total_r,
    r.artifact_path = row.run.artifact_path,
    r.artifact_hash = row.run.provenance.artifact_hash,
    r.artifact_mtime_iso = row.run.provenance.artifact_mtime_iso,
    r.ingested_at = datetime(row.run.provenance.ingested_at),
    r.parser_version = row.run.provenance.parser_version,
    r.updated_at = datetime()

MERGE (c:Config {config_id: row.config.config_id})
  ON CREATE SET
    c.created_at = datetime()
  SET
    c.params_json = row.config.params_json_text,
    c.risk_params = row.config.risk_params_text,
    c.updated_at = datetime()

MERGE (s)-[:HAS_RUN]->(r)
MERGE (r)-[:USES_CONFIG]->(c)
""".strip()


CHAMPION_INGEST_QUERY = """
MERGE (s:Strategy {strategy_id: $champion.strategy_id})
  ON CREATE SET
    s.instrument = $strategy.instrument,
    s.timeframe = $strategy.timeframe,
    s.direction = $strategy.direction,
    s.logic_type = $strategy.logic_type,
    s.created_at = datetime()
  SET s.updated_at = datetime()

MERGE (ch:Champion {champion_id: $champion.champion_id})
  ON CREATE SET ch.created_at = datetime()
  SET
    ch.freeze_date = date($champion.freeze_date),
    ch.metrics_summary = $champion.metrics_summary_text,
    ch.oos_status = $champion.oos_status,
    ch.fragilities = $champion.fragilities,
    ch.artifact_path = $champion.artifact_path,
    ch.artifact_hash = $champion.provenance.artifact_hash,
    ch.artifact_mtime_iso = $champion.provenance.artifact_mtime_iso,
    ch.ingested_at = datetime($champion.provenance.ingested_at),
    ch.parser_version = $champion.provenance.parser_version,
    ch.updated_at = datetime()

MERGE (s)-[:PRODUCED_CHAMPION]->(ch)

FOREACH (_ IN CASE WHEN $pivot_from_run_id IS NULL THEN [] ELSE [1] END |
  MERGE (r:Run {run_id: $pivot_from_run_id})
  MERGE (ch)-[:PIVOTED_FROM]->(r)
)
""".strip()


BLOB_INGEST_QUERY = """
MERGE (s:Strategy {strategy_id: $blob.strategy_id})
  ON CREATE SET
    s.instrument = $strategy.instrument,
    s.timeframe = $strategy.timeframe,
    s.direction = $strategy.direction,
    s.logic_type = $strategy.logic_type,
    s.created_at = datetime()
  SET s.updated_at = datetime()

MERGE (b:BlobArtifact {artifact_path: $blob.artifact_path})
  ON CREATE SET b.created_at = datetime()
  SET
    b.artifact_kind = $blob.artifact_kind,
    b.raw_text_sha256 = $blob.raw_text_sha256,
    b.artifact_hash = $blob.provenance.artifact_hash,
    b.ingested_at = datetime($blob.provenance.ingested_at),
    b.updated_at = datetime()
MERGE (s)-[:HAS_BLOB]->(b)
""".strip()


