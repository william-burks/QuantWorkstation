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
    s.family_id = row.strategy.family_id,
    s.strategy_class = row.strategy.strategy_class,
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
     r.evidence_score = row.run.evidence_score,
     r.calmar = row.run.calmar,
     r.metrics_return = row.run.metrics_return,
     r.tier = row.run.tier,
     r.artifact_path = row.run.artifact_path,
     r.curator_note = row.run.curator_note,
     r.first_trade_ts = datetime(row.run.first_trade_ts),
     r.last_trade_ts = datetime(row.run.last_trade_ts),
     r.active_window_frequency = row.run.active_window_frequency,
     r.duty_cycle = row.run.duty_cycle,
     r.regime = row.run.regime,
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
SET c += row.config.params_dict

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

WITH s
WHERE $champion.tier <> 'fail'

MERGE (ch:Champion {champion_id: $champion.champion_id})
  ON CREATE SET ch.created_at = datetime()
  SET
    ch.strategy_id = $champion.strategy_id,
    ch.freeze_date = date($champion.freeze_date),
    ch.tier = $champion.tier,
    ch.metrics_summary = $champion.metrics_summary_text,
    ch.metrics_sharpe = $champion.metrics_sharpe,
    ch.metrics_return = $champion.metrics_return,
    ch.metrics_calmar = $champion.metrics_calmar,
    ch.metrics_profit_factor = $champion.metrics_profit_factor,
    ch.metrics_win_rate = $champion.metrics_win_rate,
    ch.metrics_max_drawdown_r = $champion.metrics_max_drawdown_r,
    ch.metrics_total_trades = $champion.metrics_total_trades,
    ch.oos_status = $champion.oos_status,
    ch.fragilities = $champion.fragilities,
    ch.promotion_rationale = $champion.promotion_rationale,
    ch.artifact_path = $champion.artifact_path,
    ch.artifact_hash = $champion.provenance.artifact_hash,
    ch.artifact_mtime_iso = $champion.provenance.artifact_mtime_iso,
    ch.ingested_at = datetime($champion.provenance.ingested_at),
    ch.parser_version = $champion.provenance.parser_version,
    ch.updated_at = datetime()

WITH s, ch
OPTIONAL MATCH (s)-[old:PRODUCED_CHAMPION]->(prev:Champion)
  WHERE prev.champion_id <> ch.champion_id

FOREACH (rel IN CASE WHEN old IS NULL THEN [] ELSE [old] END |
  DELETE rel
)
FOREACH (_ IN CASE WHEN prev IS NULL THEN [] ELSE [1] END |
  REMOVE prev:Champion
  SET prev:RetiredChampion
)

MERGE (s)-[:PRODUCED_CHAMPION]->(ch)
FOREACH (_ IN CASE WHEN prev IS NULL THEN [] ELSE [1] END |
  CREATE (ch)-[:WAS_CHAMPION]->(prev)
  CREATE (prev)-[:SUPERSEDED_BY]->(ch)
)

FOREACH (_ IN CASE WHEN $pivot_from_run_id IS NULL THEN [] ELSE [1] END |
  MERGE (r:Run {run_id: $pivot_from_run_id})
  MERGE (ch)-[:PIVOTED_FROM]->(r)
)
""".strip()


RUN_STATS_SUMMARY_QUERY = """
MERGE (s:Strategy {strategy_id: $summary.strategy_id})
  SET s.updated_at = datetime()
MERGE (rss:RunStatsSummary {summary_id: $summary.summary_id})
  ON CREATE SET
    rss.created_at = datetime(),
    rss.trial_number = $summary.trial_number
  SET
    rss.strategy_id = $summary.strategy_id,
    rss.artifact_path = $summary.artifact_path,
    rss.total_run_count = $summary.total_run_count,
    rss.selected_run_count = $summary.selected_run_count,
    rss.rolled_up_run_count = $summary.rolled_up_run_count,
    rss.sharpe_mean = $summary.sharpe_mean,
    rss.sharpe_max = $summary.sharpe_max,
    rss.sharpe_min = $summary.sharpe_min,
    rss.max_drawdown_worst = $summary.max_drawdown_worst,
    rss.ingested_at = datetime($summary.ingested_at),
    rss.updated_at = datetime()
MERGE (s)-[:HAS_RUN_SUMMARY]->(rss)
""".strip()


ABORT_STRATEGY_QUERY = """
MATCH (s:Strategy {strategy_id: $strategy_id})
SET
  s.status = 'ABORTED',
  s.abort_reason = $reason,
  s.aborted_at = datetime(),
  s.updated_at = datetime()
RETURN s.strategy_id AS strategy_id
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


# ---------------------------------------------------------------------------
# Evolutionary dedup queries
# ---------------------------------------------------------------------------

RUN_REDUNDANCY_CHECK_CYPHER = """
MATCH (s:Strategy {strategy_id: $strategy_id})-[:HAS_RUN]->(r:Run)
WHERE r.run_id <> $new_run_id
  AND r.total_trades = $new_trades
  AND r.sharpe >= $new_sharpe
  AND abs(toFloat(datetime($new_timestamp).epochSeconds - r.timestamp.epochSeconds)) / 86400.0 < 30
RETURN count(r) > 0 AS is_redundant
""".strip()


# ---------------------------------------------------------------------------
# family_id backfill queries (migration story)
# ---------------------------------------------------------------------------

AUDIT_NULL_FAMILY_ID_QUERY = """
MATCH (s:Strategy)
WHERE s.family_id IS NULL
RETURN s.strategy_id AS strategy_id,
       s.logic_type  AS logic_type,
       s.direction   AS direction,
       s.created_at  AS created_at
ORDER BY s.created_at ASC
""".strip()


PATCH_FAMILY_ID_QUERY = """
MATCH (s:Strategy {strategy_id: $strategy_id})
SET
  s.family_id  = $family_id,
  s.updated_at = datetime()
RETURN s.strategy_id AS strategy_id
""".strip()


PATCH_RUN_HTML_PATH_QUERY = """
MATCH (r:Run {run_id: $run_id})
SET
  r.artifact_path_html = $html_path,
  r.updated_at = datetime()
RETURN r.run_id AS run_id
""".strip()


# ---------------------------------------------------------------------------
# ResearchTarget singleton queries (QWS-0408)
# ---------------------------------------------------------------------------

ENSURE_RESEARCH_TARGET_QUERY = """
MERGE (rt:ResearchTarget {target_id: "singleton"})
ON CREATE SET
  rt.sharpe_professional = $sharpe_professional,
  rt.sharpe_institutional = $sharpe_institutional,
  rt.max_holding_hours = $max_holding_hours,
  rt.min_trades = $min_trades,
  rt.min_active_window_frequency = $min_active_window_frequency,
  rt.profit_factor_min = $profit_factor_min,
  rt.calmar_min = $calmar_min,
  rt.max_drawdown_floor = $max_drawdown_floor,
  rt.correlation_gate = $correlation_gate,
  rt.decay_threshold = $decay_threshold,
  rt.created_at = datetime()
SET rt.updated_at = datetime()
""".strip()


PATCH_RESEARCH_TARGET_QUERY = """
MATCH (rt:ResearchTarget {target_id: "singleton"})
SET rt += $overrides
""".strip()


# ---------------------------------------------------------------------------
# Monitor champion queries (QWS-0803)
# ---------------------------------------------------------------------------

GET_ALL_ACTIVE_CHAMPIONS_QUERY = """
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
WHERE NOT EXISTS { (ch)-[:DEGRADED_TO]->() }
  AND NOT EXISTS { (ch)-[:RETIRED_TO]->() }
RETURN
  ch.champion_id AS champion_id,
  ch.strategy_id AS strategy_id,
  ch.metrics_sharpe AS metrics_sharpe,
  ch.artifact_path AS artifact_path
ORDER BY ch.champion_id
""".strip()


FORMER_CHAMPION_BLOB_QUERY = """
MATCH (fc:FormerChampion {former_champion_id: $former_champion_id})
MERGE (b:BlobArtifact {artifact_path: $artifact_path})
  ON CREATE SET
    b.artifact_type = $artifact_type,
    b.content = $content,
    b.created_at = datetime()
  ON MATCH SET
    b.artifact_type = $artifact_type,
    b.content = $content,
    b.updated_at = datetime()
MERGE (fc)-[:HAS_BLOB]->(b)
RETURN b.artifact_path AS artifact_path
""".strip()


# ---------------------------------------------------------------------------
# OOS outcome update queries (QWS-0402)
# ---------------------------------------------------------------------------

GET_CHAMPION_OOS_STATUS_QUERY = """
MATCH (ch:Champion {champion_id: $champion_id})
RETURN ch.champion_id AS champion_id, ch.oos_status AS oos_status
""".strip()


UPDATE_CHAMPION_OOS_STATUS_QUERY = """
MATCH (ch:Champion {champion_id: $champion_id})
SET
  ch.oos_status = $oos_status,
  ch.oos_date = date($oos_date),
  ch.metrics_oos_sharpe = $oos_sharpe,
  ch.updated_at = datetime()
RETURN ch.champion_id AS champion_id
""".strip()


# ---------------------------------------------------------------------------
# Hypothesis journaling (QWS-0601)
# ---------------------------------------------------------------------------

HYPOTHESIS_CREATE_QUERY = """
MERGE (h:Hypothesis {hypothesis_id: $hypothesis_id})
  ON CREATE SET
    h.title = $title,
    h.status = 'open',
    h.created_at = datetime(),
    h.updated_at = datetime()
  ON MATCH SET
    h.updated_at = datetime()
RETURN h.hypothesis_id AS hypothesis_id
""".strip()

HYPOTHESIS_SUGGESTED_EDGE_QUERY = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
MERGE (src:HypothesisSource {source_key: $source})
  ON CREATE SET src.created_at = datetime()
MERGE (src)-[:SUGGESTED {source: $source}]->(h)
RETURN h.hypothesis_id AS hypothesis_id
""".strip()

HYPOTHESIS_TESTED_AS_QUERY = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
MATCH (s:Strategy {strategy_id: $strategy_id})
MERGE (h)-[:TESTED_AS]->(s)
RETURN h.hypothesis_id AS hypothesis_id, s.strategy_id AS strategy_id
""".strip()

HYPOTHESIS_BRANCHED_FROM_QUERY = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
MATCH (n) WHERE n.hypothesis_id = $node_id
  OR n.strategy_id = $node_id
  OR n.run_id = $node_id
  OR n.champion_id = $node_id
  OR n.regime_id = $node_id
WITH h, n LIMIT 1
MERGE (h)-[:BRANCHED_FROM {rationale: $rationale}]->(n)
RETURN h.hypothesis_id AS hypothesis_id
""".strip()

HYPOTHESIS_UPDATE_STATUS_QUERY = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
SET h.status = $status, h.updated_at = datetime()
RETURN h.hypothesis_id AS hypothesis_id
""".strip()

HYPOTHESIS_UPDATE_FINDINGS_QUERY = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
SET h.findings = $findings, h.updated_at = datetime()
RETURN h.hypothesis_id AS hypothesis_id
""".strip()

GET_HYPOTHESIS_BY_ID_QUERY = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
RETURN h.hypothesis_id AS hypothesis_id, h.title AS title, h.status AS status,
       toString(h.created_at) AS created_at, toString(h.updated_at) AS updated_at
""".strip()

GET_LIST_HYPOTHESES_V1_CYPHER = """
MATCH (h:Hypothesis)
RETURN {
  hypothesis_id: h.hypothesis_id,
  title: h.title,
  status: h.status,
  created_at: toString(h.created_at)
} AS result
ORDER BY h.created_at DESC
""".strip()

GET_HYPOTHESIS_AUDIT_V1_CYPHER = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
OPTIONAL MATCH (h)-[:TESTED_AS]->(s:Strategy)
OPTIONAL MATCH (s)-[:PRODUCED_CHAMPION]->(ch:Champion)
OPTIONAL MATCH (s)-[:HAS_RUN]->(r:Run)
RETURN {
  hypothesis_id: h.hypothesis_id,
  title: h.title,
  status: h.status,
  strategy_id: s.strategy_id,
  champion_id: ch.champion_id,
  run_id: r.run_id,
  run_sharpe: r.sharpe,
  oos_status: ch.oos_status
} AS result
""".strip()

GET_CHECK_REDUNDANCY_V1_CYPHER = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
OPTIONAL MATCH (active_s:Strategy)-[:PRODUCED_CHAMPION]->(active_ch:Champion)
  WHERE coalesce(active_s.status, '') <> 'ABORTED'
    AND toLower(active_s.strategy_id) CONTAINS toLower(h.title)
OPTIONAL MATCH (aborted_s:Strategy)
  WHERE aborted_s.status = 'ABORTED'
    AND toLower(aborted_s.strategy_id) CONTAINS toLower(h.title)
OPTIONAL MATCH (h)-[sem:SEMANTICALLY_RELATED]->(sem_h:Hypothesis)
RETURN {
  hypothesis_id: h.hypothesis_id,
  title: h.title,
  active_champion_matches: collect(DISTINCT active_ch.champion_id),
  aborted_strategy_matches: collect(DISTINCT aborted_s.strategy_id),
  semantic_matches: collect(DISTINCT {
    hypothesis_id: sem_h.hypothesis_id,
    title: sem_h.title,
    similarity: sem.similarity
  })
} AS result
LIMIT 1
""".strip()


# ---------------------------------------------------------------------------
# Semantic hypothesis deduplication (QWS-0604)
# ---------------------------------------------------------------------------

HYPOTHESIS_SET_EMBEDDING_QUERY = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
SET h.embedding = $embedding, h.updated_at = datetime()
RETURN h.hypothesis_id AS hypothesis_id
""".strip()

GET_ALL_HYPOTHESIS_EMBEDDINGS_QUERY = """
MATCH (h:Hypothesis)
WHERE h.embedding IS NOT NULL
RETURN h.hypothesis_id AS hypothesis_id, h.title AS title,
       h.embedding AS embedding
""".strip()

GET_HYPOTHESES_WITHOUT_EMBEDDINGS_QUERY = """
MATCH (h:Hypothesis)
WHERE h.embedding IS NULL
RETURN h.hypothesis_id AS hypothesis_id, h.title AS title
""".strip()

SEMANTICALLY_RELATED_MERGE_QUERY = """
UNWIND $pairs AS pair
MATCH (a:Hypothesis {hypothesis_id: pair.hypothesis_id_a})
MATCH (b:Hypothesis {hypothesis_id: pair.hypothesis_id_b})
MERGE (a)-[r1:SEMANTICALLY_RELATED {pair_key: pair.pair_key}]->(b)
  SET r1.similarity = pair.similarity, r1.computed_at = datetime()
MERGE (b)-[r2:SEMANTICALLY_RELATED {pair_key: pair.pair_key}]->(a)
  SET r2.similarity = pair.similarity, r2.computed_at = datetime()
""".strip()

GET_SIMILAR_HYPOTHESES_V1_CYPHER = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})-[r:SEMANTICALLY_RELATED]->(other:Hypothesis)
RETURN {
  hypothesis_id: other.hypothesis_id,
  title: other.title,
  similarity: r.similarity,
  status: other.status
} AS result
ORDER BY r.similarity DESC
""".strip()

GET_HYPOTHESES_BY_STATUS_V1_CYPHER = """
MATCH (h:Hypothesis)
RETURN {
  hypothesis_id: h.hypothesis_id,
  title: h.title,
  status: h.status,
  findings: left(coalesce(h.findings, ''), 80),
  created_at: toString(h.created_at)
} AS result
ORDER BY h.status ASC, h.created_at DESC
""".strip()

GET_HYPOTHESIS_SEARCH_V1_CYPHER = """
MATCH (h:Hypothesis)
WHERE toLower(h.title) CONTAINS toLower($title_fragment)
RETURN {
  hypothesis_id: h.hypothesis_id,
  title: h.title,
  status: h.status,
  findings: h.findings
} AS result
ORDER BY h.created_at DESC
""".strip()


# ---------------------------------------------------------------------------
# Queued hypotheses (QWS-1301)
# ---------------------------------------------------------------------------

HYPOTHESIS_SET_QUEUED_QUERY = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
SET h.queued = $queued, h.updated_at = datetime()
RETURN h.hypothesis_id AS hypothesis_id
""".strip()

HYPOTHESIS_DEQUEUE_ON_STATUS_QUERY = """
MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
SET h.status = $status, h.queued = false, h.updated_at = datetime()
RETURN h.hypothesis_id AS hypothesis_id
""".strip()

GET_QUEUED_HYPOTHESES_V1_CYPHER = """
MATCH (h:Hypothesis {queued: true})
OPTIONAL MATCH (h)-[:BRANCHED_FROM]->(src)
RETURN {
  hypothesis_id: h.hypothesis_id,
  title: h.title,
  findings: left(coalesce(h.findings, ''), 200),
  branched_from_id: coalesce(src.hypothesis_id, src.run_id),
  created_at: toString(h.created_at)
} AS result
ORDER BY h.created_at DESC
""".strip()


# ---------------------------------------------------------------------------
# Regime node + IN_REGIME edge merge (QWS-0502)
# ---------------------------------------------------------------------------

REGIME_MERGE_QUERY = """
UNWIND $regime_rows AS row
MATCH (r:Run {run_id: row.run_id})
MERGE (reg:Regime {regime_id: row.regime_id})
  ON CREATE SET reg.created_at = datetime()
  SET reg.updated_at = datetime()
MERGE (r)-[:IN_REGIME]->(reg)
""".strip()


# ---------------------------------------------------------------------------
# trial_metadata map write (QWS-0907)
# Writes a free-form map property onto existing Run nodes.
# Called after CSV ingest when bundle.json contains a trial_metadata key.
# ---------------------------------------------------------------------------

TRIAL_METADATA_WRITE_QUERY = """
UNWIND $run_ids AS run_id
MATCH (r:Run {run_id: run_id})
SET r.trial_metadata = $trial_metadata
""".strip()


# ---------------------------------------------------------------------------
# strategy_class property writes (QWS-1012)
# ---------------------------------------------------------------------------

PATCH_STRATEGY_CLASS_QUERY = """
MATCH (s:Strategy {strategy_id: $strategy_id})
SET s.strategy_class = $strategy_class, s.updated_at = datetime()
RETURN s.strategy_id AS strategy_id
""".strip()

GET_UNCLASSIFIED_STRATEGIES_QUERY = """
MATCH (s:Strategy)
WHERE s.strategy_class IS NULL AND s.status <> 'ABORTED'
RETURN s.strategy_id AS strategy_id, s.instrument AS instrument,
       s.timeframe AS timeframe, s.direction AS direction,
       s.logic_type AS logic_type
ORDER BY s.created_at DESC
""".strip()

PORTFOLIO_BY_CLASS_CYPHER = """
MATCH (s:Strategy)
WHERE s.status <> 'ABORTED'
WITH s.strategy_class AS cls, collect({
  strategy_id: s.strategy_id,
  instrument: s.instrument,
  timeframe: s.timeframe,
  direction: s.direction,
  logic_type: s.logic_type,
  has_champion: exists((s)-[:PRODUCED_CHAMPION]->(:Champion)),
  strategy_class: s.strategy_class
}) AS strategies
RETURN {
  strategy_class: coalesce(cls, '__unclassified__'),
  count: size(strategies),
  strategies: strategies
} AS result
ORDER BY result.strategy_class ASC
""".strip()


# ---------------------------------------------------------------------------
# CORRELATED_WITH edge write (QWS-0603)
# Symmetric: written in both directions so queries can match either endpoint.
# ---------------------------------------------------------------------------

CORRELATED_WITH_CHAMPION_QUERY = """
MATCH (ca:Champion {champion_id: $champion_id_a})
MATCH (cb:Champion {champion_id: $champion_id_b})
MERGE (ca)-[e1:CORRELATED_WITH {pair_key: $pair_key}]->(cb)
  SET e1.coefficient  = $coefficient,
      e1.threshold    = $threshold,
      e1.lookback     = $lookback,
      e1.computed_at  = datetime()
MERGE (cb)-[e2:CORRELATED_WITH {pair_key: $pair_key}]->(ca)
  SET e2.coefficient  = $coefficient,
      e2.threshold    = $threshold,
      e2.lookback     = $lookback,
      e2.computed_at  = datetime()
""".strip()

CORRELATED_WITH_STRATEGY_QUERY = """
MATCH (sa:Strategy {strategy_id: $strategy_id_a})
MATCH (sb:Strategy {strategy_id: $strategy_id_b})
MERGE (sa)-[e1:CORRELATED_WITH {pair_key: $pair_key}]->(sb)
  SET e1.coefficient  = $coefficient,
      e1.threshold    = $threshold,
      e1.lookback     = $lookback,
      e1.computed_at  = datetime()
MERGE (sb)-[e2:CORRELATED_WITH {pair_key: $pair_key}]->(sa)
  SET e2.coefficient  = $coefficient,
      e2.threshold    = $threshold,
      e2.lookback     = $lookback,
      e2.computed_at  = datetime()
""".strip()

GET_PORTFOLIO_ALPHA_CHAMPIONS_QUERY = """
MATCH (s:Strategy)-[:PRODUCED_CHAMPION]->(ch:Champion)
WHERE ch.oos_status = 'oos_pass'
  AND ch.tier IN ['professional', 'institutional']
  AND s.status <> 'ABORTED'
RETURN {
  champion_id:       ch.champion_id,
  strategy_id:       ch.strategy_id,
  artifact_path:     ch.artifact_path,
  metrics_sharpe:    ch.metrics_sharpe,
  metrics_oos_sharpe: ch.metrics_oos_sharpe,
  metrics_max_drawdown_r: ch.metrics_max_drawdown_r,
  metrics_return:    ch.metrics_return,
  metrics_total_trades: ch.metrics_total_trades,
  tier:              ch.tier,
  oos_status:        ch.oos_status
} AS result
ORDER BY ch.best_evidence_score DESC
""".strip()


# ---------------------------------------------------------------------------
# Demo graph seed / teardown (qw seed --demo)
#
# Deterministic, idempotent dummy provenance graph. Covers:
#   cross_artifact_correlation  — alpha + beta share family_id (same logic, two instruments)
#   runs_by_regime              — high_vol x2, trend_down, mean_reverting labels
#   regime_performance          — multiple regimes across two strategies
#   compare_strategy_performance — champions on ES and CL
#   downstream_champions        — PIVOTED_FROM edges on all champions
#   portfolio_alpha             — demo_champ_002 has oos_pass; MaxDD/Calmar/is_oos_drift columns
#   list_oos_pending            — demo_champ_001 has oos_pending
#   promotion_candidates        — demo_run_004: dual-hurdle pass, not yet promoted
#   list_aborted                — demo-strategy-gamma: ABORTED with abort_reason
#   run_history                 — multiple runs on alpha (3 runs)
#   instrument_concentration    — ES champion + CL champion
#   recent_champions            — two active champions
#   list_hypotheses             — demo_hyp_001: open; demo_hyp_002: confirmed + TESTED_AS alpha
#   hypothesis_audit            — demo_hyp_002 → alpha → champion lineage
#   check_redundancy            — demo_hyp_001 title matches no active champions
#   portfolio_correlation       — CORRELATED_WITH demo_champ_001 ↔ demo_champ_002 (r=0.72)
#
# ---------------------------------------------------------------------------
# FormerChampion lifecycle queries (QWS-0801)
# ---------------------------------------------------------------------------

GET_CHAMPION_BY_ID_QUERY = """
MATCH (c:Champion {champion_id: $champion_id})
RETURN c.champion_id AS champion_id, c.strategy_id AS strategy_id
"""

DEGRADE_CHAMPION_QUERY = """
MATCH (c:Champion {champion_id: $champion_id})
MERGE (fc:FormerChampion {former_champion_id: $former_champion_id})
  ON CREATE SET fc.created_at = datetime()
  SET fc.strategy_id     = $strategy_id,
      fc.champion_id     = $champion_id,
      fc.degraded_at     = datetime($degraded_at),
      fc.oos_reason      = $oos_reason,
      fc.degrade_reason  = $degrade_reason,
      fc.metrics_sharpe_at_degradation = $metrics_sharpe_at_degradation,
      fc.updated_at      = datetime()
MERGE (c)-[e:DEGRADED_TO]->(fc)
  SET e.detected_at = datetime($degraded_at)
RETURN fc.former_champion_id AS former_champion_id
"""

AUDIT_LINEAGE_QUERY = """
MATCH (c:Champion)-[:PIVOTED_FROM]->(r:Run)<-[:HAS_RUN]-(s:Strategy)<-[:TESTED_AS]-(h:Hypothesis)
WHERE h.status = 'rejected'
  AND c.metrics_total_trades < 10
  AND c.oos_status = 'oos_pending'
RETURN c.champion_id   AS champion_id,
       c.name          AS name,
       c.metrics_total_trades AS metrics_total_trades,
       c.oos_status    AS oos_status,
       h.hypothesis_id AS hypothesis_id,
       h.status        AS hypothesis_status
"""

GET_FORMER_CHAMPION_BY_ID_QUERY = """
MATCH (fc:FormerChampion {former_champion_id: $former_champion_id})
RETURN fc.former_champion_id AS former_champion_id,
       fc.champion_id        AS champion_id,
       fc.strategy_id        AS strategy_id,
       fc.oos_reason         AS oos_reason
"""

RETIRE_FORMER_CHAMPION_QUERY = """
MATCH (fc:FormerChampion {former_champion_id: $former_champion_id})
MERGE (rc:RetiredChampion {champion_id: $retired_champion_id})
  ON CREATE SET rc.created_at = datetime()
  SET rc.strategy_id      = fc.strategy_id,
      rc.oos_reason       = fc.oos_reason,
      rc.retirement_note  = $retirement_note,
      rc.retired_at       = datetime($retired_at),
      rc.updated_at       = datetime()
MERGE (fc)-[e:RETIRED_TO]->(rc)
  SET e.retired_at = datetime($retired_at)
RETURN rc.champion_id AS retired_champion_id
"""

# ---------------------------------------------------------------------------
# Ad-hoc Cypher passthrough + qw patch (QWS-0906)
# ---------------------------------------------------------------------------

RUN_ADHOC_CYPHER_QUERY = "{cypher}"  # sentinel — caller substitutes at runtime

GET_RUN_BY_ID_QUERY = """
MATCH (r:Run {run_id: $run_id})
RETURN r.run_id AS run_id
""".strip()

PATCH_RUN_QUERY = """
MATCH (r:Run {run_id: $run_id})
SET r[$key] = $value, r.updated_at = datetime()
RETURN r.run_id AS run_id
""".strip()

GET_FORMER_CHAMPIONS_V1_CYPHER = """
MATCH (fc:FormerChampion)
OPTIONAL MATCH (fc)-[:RETIRED_TO]->(rc:RetiredChampion)
OPTIONAL MATCH (s:Strategy {strategy_id: fc.strategy_id})
RETURN fc.former_champion_id AS former_champion_id,
       fc.strategy_id        AS strategy_id,
       s.instrument          AS instrument,
       fc.degraded_at        AS degraded_at,
       fc.oos_reason         AS oos_reason,
       rc.retirement_note    AS retirement_note,
       CASE WHEN rc IS NOT NULL THEN 'RETIRED' ELSE 'DEGRADED' END AS status
ORDER BY fc.degraded_at DESC
"""

# All nodes carry is_demo=true for clean teardown via DEMO_TEARDOWN_CYPHER.
# ---------------------------------------------------------------------------

DEMO_SEED_CYPHER = """
// ── Strategies ──────────────────────────────────────────────────────────────

// Demo Strategy Alpha — ES, active, family A
MERGE (s1:Strategy {strategy_id: 'demo-strategy-alpha'})
  ON CREATE SET s1.created_at = datetime()
  SET s1.instrument = 'ES',
      s1.timeframe = '1h',
      s1.direction = 'bear',
      s1.logic_type = 'demo-logic',
      s1.family_id = 'demo_family_001',
      s1.strategy_class = 'liquidity_sweep',
      s1.is_demo = true,
      s1.updated_at = datetime()

// Demo Strategy Beta — CL, active, same family_id as alpha → cross_artifact_correlation
MERGE (s2:Strategy {strategy_id: 'demo-strategy-beta'})
  ON CREATE SET s2.created_at = datetime()
  SET s2.instrument = 'CL',
      s2.timeframe = '1h',
      s2.direction = 'bear',
      s2.logic_type = 'demo-logic',
      s2.family_id = 'demo_family_001',
      s2.strategy_class = 'liquidity_sweep',
      s2.is_demo = true,
      s2.updated_at = datetime()

// Demo Strategy Gamma — ABORTED; surfaces in list_aborted
MERGE (s3:Strategy {strategy_id: 'demo-strategy-gamma'})
  ON CREATE SET s3.created_at = datetime()
  SET s3.instrument = 'NQ',
      s3.timeframe = '1h',
      s3.direction = 'bull',
      s3.logic_type = 'demo-logic-2',
      s3.family_id = 'demo_family_002',
      s3.status = 'ABORTED',
      s3.abort_reason = 'Look-ahead bias detected in signal window calculation',
      s3.aborted_at = datetime('2026-03-15T10:00:00'),
      s3.is_demo = true,
      s3.updated_at = datetime()

// ── Runs — Alpha ────────────────────────────────────────────────────────────

// Demo Run 001 — alpha, high_vol, professional; becomes RetiredChampion pivot run
MERGE (r1:Run {run_id: 'demo_run_001'})
  ON CREATE SET r1.created_at = datetime()
  SET r1.sharpe = 2.3,
      r1.total_trades = 38,
      r1.evidence_score = 14.18,
      r1.tier = 'professional',
      r1.regime = 'high_vol',
  r1.trial_metadata = '{"atr_bucket": "high", "avg_atr": "2.3", "regime_label": "high_vol"}',
      r1.profit_factor = 1.45,
      r1.win_rate = 0.58,
      r1.max_drawdown = -0.082,
      r1.metrics_return = 0.048,
      r1.oos_status = 'oos_pass',
      r1.artifact_path = 'demo/run_001.csv',
      r1.peaked_as_best = false,
      r1.first_trade_ts = datetime('2025-01-06T09:30:00'),
      r1.last_trade_ts = datetime('2025-07-31T14:00:00'),
      r1.active_window_frequency = 0.21,
      r1.duty_cycle = 0.62,
      r1.is_demo = true
MERGE (s1)-[:HAS_RUN]->(r1)

// Demo Run 002 — alpha, trend_down, institutional; current champion pivot run
MERGE (r2:Run {run_id: 'demo_run_002'})
  ON CREATE SET r2.created_at = datetime()
  SET r2.sharpe = 3.1,
      r2.total_trades = 55,
      r2.evidence_score = 23.0,
      r2.tier = 'institutional',
      r2.regime = 'trend_down',
      r2.profit_factor = 1.92,
      r2.win_rate = 0.62,
      r2.max_drawdown = -0.055,
      r2.metrics_return = 0.087,
      r2.oos_status = 'oos_pending',
      r2.artifact_path = 'demo/run_002.csv',
      r2.peaked_as_best = true,
      r2.first_trade_ts = datetime('2025-01-06T09:30:00'),
      r2.last_trade_ts = datetime('2025-10-31T14:00:00'),
      r2.active_window_frequency = 0.24,
      r2.duty_cycle = 0.71,
      r2.is_demo = true
MERGE (s1)-[:HAS_RUN]->(r2)

// Demo Run 004 — alpha, mean_reverting, professional;
//   PROMOTION CANDIDATE — dual-hurdle pass (sharpe≥2.0, trades≥30, freq≥0.06), not yet promoted
MERGE (r4:Run {run_id: 'demo_run_004'})
  ON CREATE SET r4.created_at = datetime()
  SET r4.sharpe = 2.5,
      r4.total_trades = 40,
      r4.evidence_score = 15.81,
      r4.tier = 'professional',
      r4.regime = 'mean_reverting',
      r4.profit_factor = 1.55,
      r4.win_rate = 0.60,
      r4.max_drawdown = -0.071,
      r4.metrics_return = 0.052,
      r4.oos_status = 'oos_pending',
      r4.artifact_path = 'demo/run_004.csv',
      r4.peaked_as_best = false,
      r4.first_trade_ts = datetime('2025-03-01T09:30:00'),
      r4.last_trade_ts = datetime('2025-11-30T14:00:00'),
      r4.active_window_frequency = 0.14,
      r4.duty_cycle = 0.58,
      r4.is_demo = true
MERGE (s1)-[:HAS_RUN]->(r4)

// ── Runs — Beta ─────────────────────────────────────────────────────────────

// Demo Run 003 — beta, high_vol, institutional; beta champion pivot run
MERGE (r3:Run {run_id: 'demo_run_003'})
  ON CREATE SET r3.created_at = datetime()
  SET r3.sharpe = 4.6,
      r3.total_trades = 32,
      r3.evidence_score = 26.03,
      r3.tier = 'institutional',
      r3.regime = 'high_vol',
      r3.profit_factor = 2.14,
      r3.win_rate = 0.66,
      r3.max_drawdown = -0.029,
      r3.metrics_return = 0.099,
      r3.oos_status = 'oos_pending',
      r3.artifact_path = 'demo/run_003.csv',
      r3.peaked_as_best = true,
      r3.first_trade_ts = datetime('2025-01-06T09:30:00'),
      r3.last_trade_ts = datetime('2025-10-31T14:00:00'),
      r3.active_window_frequency = 0.16,
      r3.duty_cycle = 0.55,
      r3.is_demo = true
MERGE (s2)-[:HAS_RUN]->(r3)

// ── Champion lineage — Alpha ─────────────────────────────────────────────────

// Demo Retired Champion 001 — alpha displaced; pivoted from run 001
MERGE (rc1:RetiredChampion {champion_id: 'demo_retired_champ_001'})
  ON CREATE SET rc1.created_at = datetime()
  SET rc1.strategy_id = 'demo-strategy-alpha',
      rc1.metrics_sharpe = 2.3,
      rc1.metrics_return = 0.048,
      rc1.oos_status = 'oos_pass',
      rc1.is_demo = true
MERGE (rc1)-[:PIVOTED_FROM]->(r1)

// Demo Champion 001 — alpha current; oos_pending; pivoted from run 002; WAS_CHAMPION → retired
MERGE (ch1:Champion {champion_id: 'demo_champ_001'})
  ON CREATE SET ch1.created_at = datetime()
  SET ch1.strategy_id = 'demo-strategy-alpha',
      ch1.metrics_sharpe = 3.1,
      ch1.metrics_oos_sharpe = null,
      ch1.metrics_return = 0.087,
      ch1.metrics_total_trades = 55,
      ch1.metrics_win_rate = 0.62,
      ch1.metrics_profit_factor = 1.92,
      ch1.metrics_max_drawdown_r = -2.1,
      ch1.best_evidence_score = 23.0,
      ch1.tier = 'institutional',
      ch1.oos_status = 'oos_pending',
      ch1.auto_promoted = true,
      ch1.promotion_rationale = 'Dominated ES bear candidates; Sharpe 3.1 vs next-best 2.5',
      ch1.freeze_date = date('2026-04-01'),
      ch1.updated_at = datetime(),
      ch1.is_demo = true
MERGE (s1)-[:PRODUCED_CHAMPION]->(ch1)
MERGE (ch1)-[:PIVOTED_FROM]->(r2)
MERGE (ch1)-[:WAS_CHAMPION]->(rc1)
MERGE (rc1)-[:SUPERSEDED_BY]->(ch1)

// ── Champion lineage — Beta ──────────────────────────────────────────────────

// Demo Champion 002 — beta current; oos_pass; appears in portfolio_alpha
MERGE (ch2:Champion {champion_id: 'demo_champ_002'})
  ON CREATE SET ch2.created_at = datetime()
  SET ch2.strategy_id = 'demo-strategy-beta',
      ch2.metrics_sharpe = 4.6,
      ch2.metrics_oos_sharpe = 3.8,
      ch2.metrics_return = 0.099,
      ch2.metrics_total_trades = 32,
      ch2.metrics_win_rate = 0.66,
      ch2.metrics_profit_factor = 2.14,
      ch2.metrics_max_drawdown_r = -1.4,
      ch2.best_evidence_score = 26.03,
      ch2.tier = 'institutional',
      ch2.oos_status = 'oos_pass',
      ch2.oos_date = date('2026-04-05'),
      ch2.auto_promoted = true,
      ch2.promotion_rationale = 'Only CL strategy passing corr gate; Sharpe 4.6 OOS 3.8',
      ch2.freeze_date = date('2026-03-20'),
      ch2.updated_at = datetime(),
      ch2.is_demo = true
MERGE (s2)-[:PRODUCED_CHAMPION]->(ch2)
MERGE (ch2)-[:PIVOTED_FROM]->(r3)

// ── Regime nodes + IN_REGIME edges ──────────────────────────────────────────

MERGE (reg_hv:Regime {regime_id: 'high_vol'})
  ON CREATE SET reg_hv.created_at = datetime(), reg_hv.is_demo = true
  SET reg_hv.updated_at = datetime()
MERGE (r1)-[:IN_REGIME]->(reg_hv)
MERGE (r3)-[:IN_REGIME]->(reg_hv)

MERGE (reg_td:Regime {regime_id: 'trend_down'})
  ON CREATE SET reg_td.created_at = datetime(), reg_td.is_demo = true
  SET reg_td.updated_at = datetime()
MERGE (r2)-[:IN_REGIME]->(reg_td)

MERGE (reg_mr:Regime {regime_id: 'mean_reverting'})
  ON CREATE SET reg_mr.created_at = datetime(), reg_mr.is_demo = true
  SET reg_mr.updated_at = datetime()
MERGE (r4)-[:IN_REGIME]->(reg_mr)

// ── Demo Hypothesis nodes ────────────────────────────────────────────────────

// Demo Hypothesis 001 — open; no TESTED_AS link; for list_hypotheses + check_redundancy
MERGE (h1:Hypothesis {hypothesis_id: 'demo_hyp_001'})
  ON CREATE SET h1.created_at = datetime('2026-01-10T09:00:00'), h1.is_demo = true
  SET h1.title = 'ES bear high_vol regime has elevated win rate in first 30 min',
      h1.status = 'open',
      h1.findings = 'Parked after session 3 — needs CL data extension before retry.',
      h1.queued = false,
      h1.updated_at = datetime()
MERGE (hsrc1:HypothesisSource {source_key: 'user'})
  ON CREATE SET hsrc1.created_at = datetime()
MERGE (hsrc1)-[:SUGGESTED {source: 'user'}]->(h1)

// Demo Hypothesis 002 — confirmed + TESTED_AS demo-strategy-alpha; for hypothesis_audit
MERGE (h2:Hypothesis {hypothesis_id: 'demo_hyp_002'})
  ON CREATE SET h2.created_at = datetime('2026-02-01T10:00:00'), h2.is_demo = true
  SET h2.title = 'Demo alpha bear logic exploits London open liquidity imbalance',
      h2.status = 'confirmed',
      h2.queued = false,
      h2.updated_at = datetime()
MERGE (hsrc2:HypothesisSource {source_key: 'llm'})
  ON CREATE SET hsrc2.created_at = datetime()
MERGE (hsrc2)-[:SUGGESTED {source: 'llm'}]->(h2)
MERGE (h2)-[:TESTED_AS]->(s1)

// ── SEMANTICALLY_RELATED edges — semantic dedup (QWS-0604) ──────────────────

// demo_hyp_001 ↔ demo_hyp_002: high semantic similarity (0.91 > 0.85 threshold)
// Both discuss ES bear regime/liquidity — same underlying idea in different words.
MERGE (h1_sem:Hypothesis {hypothesis_id: 'demo_hyp_001'})
MERGE (h2_sem:Hypothesis {hypothesis_id: 'demo_hyp_002'})
MERGE (h1_sem)-[sr1:SEMANTICALLY_RELATED {pair_key: 'demo_hyp_001|demo_hyp_002'}]->(h2_sem)
  SET sr1.similarity = 0.91,
      sr1.computed_at = datetime('2026-04-11T00:00:00'),
      sr1.is_demo     = true
MERGE (h2_sem)-[sr2:SEMANTICALLY_RELATED {pair_key: 'demo_hyp_001|demo_hyp_002'}]->(h1_sem)
  SET sr2.similarity = 0.91,
      sr2.computed_at = datetime('2026-04-11T00:00:00'),
      sr2.is_demo     = true

// ── CORRELATED_WITH edges — portfolio_correlation (QWS-0603) ─────────────────

// demo_champ_001 ↔ demo_champ_002: high correlation (|r|=0.72 > 0.60 threshold)
MERGE (ch1_corr:Champion {champion_id: 'demo_champ_001'})
MERGE (ch2_corr:Champion {champion_id: 'demo_champ_002'})
MERGE (ch1_corr)-[ec1:CORRELATED_WITH {pair_key: 'demo_champ_001|demo_champ_002'}]->(ch2_corr)
  SET ec1.coefficient = 0.72,
      ec1.threshold   = 0.60,
      ec1.lookback    = 'full',
      ec1.computed_at = datetime('2026-04-11T00:00:00'),
      ec1.is_demo     = true
MERGE (ch2_corr)-[ec2:CORRELATED_WITH {pair_key: 'demo_champ_001|demo_champ_002'}]->(ch1_corr)
  SET ec2.coefficient = 0.72,
      ec2.threshold   = 0.60,
      ec2.lookback    = 'full',
      ec2.computed_at = datetime('2026-04-11T00:00:00'),
      ec2.is_demo     = true

// Strategy-level CORRELATED_WITH mirrors champion-level
MERGE (sa_corr:Strategy {strategy_id: 'demo-strategy-alpha'})
MERGE (sb_corr:Strategy {strategy_id: 'demo-strategy-beta'})
MERGE (sa_corr)-[es1:CORRELATED_WITH
  {pair_key: 'demo-strategy-alpha|demo-strategy-beta'}]->(sb_corr)
  SET es1.coefficient = 0.72,
      es1.threshold   = 0.60,
      es1.lookback    = 'full',
      es1.computed_at = datetime('2026-04-11T00:00:00'),
      es1.is_demo     = true
MERGE (sb_corr)-[es2:CORRELATED_WITH
  {pair_key: 'demo-strategy-alpha|demo-strategy-beta'}]->(sa_corr)
  SET es2.coefficient = 0.72,
      es2.threshold   = 0.60,
      es2.lookback    = 'full',
      es2.computed_at = datetime('2026-04-11T00:00:00'),
      es2.is_demo     = true

// ── FormerChampion + DEGRADED_TO (QWS-0801) ─────────────────────────────────

// Demo FormerChampion 001 — alpha champion degraded; cemetery view row
MERGE (fc1:FormerChampion {former_champion_id: 'demo_former_champ_001'})
  ON CREATE SET fc1.created_at = datetime(), fc1.is_demo = true
  SET fc1.strategy_id     = 'demo-strategy-alpha',
      fc1.champion_id     = 'demo_retired_champ_001',
      fc1.degraded_at     = datetime('2026-03-25T10:00:00'),
      fc1.oos_reason      = 'MaxDD breached -15% in Feb CPI spike; OOS Sharpe dropped to 0.8',
      fc1.metrics_sharpe_at_degradation = 1.4,
      fc1.updated_at      = datetime()

// DEGRADED_TO edge from Champion → FormerChampion
MERGE (ch_demo:Champion {champion_id: 'demo_champ_001'})
MERGE (ch_demo)-[dg1:DEGRADED_TO]->(fc1)
  SET dg1.detected_at = datetime('2026-03-25T10:00:00'),
      dg1.is_demo     = true

// ── Monitor notification BlobArtifact (QWS-0803) ───────────────────────────
// Demo monitor notification blob attached to FormerChampion 001
MERGE (b_monitor:BlobArtifact
  {artifact_path: 'monitor:demo_former_champ_001:monitor_notification:demo_blob_001'})
  ON CREATE SET
    b_monitor.artifact_type = 'monitor_notification',
    b_monitor.content = 'Strategy demo-strategy-alpha hit decay threshold (drift=1.10).',
    b_monitor.is_demo = true,
    b_monitor.created_at = datetime()
  ON MATCH SET
    b_monitor.is_demo = true
WITH b_monitor
MATCH (fc_seed:FormerChampion {former_champion_id: 'demo_former_champ_001'})
MERGE (fc_seed)-[:HAS_BLOB]->(b_monitor)

// Demo Retired Champion 002 — result of retiring demo_former_champ_001
MERGE (rc2:RetiredChampion {champion_id: 'demo_retired_champ_002'})
  ON CREATE SET rc2.created_at = datetime(), rc2.is_demo = true
  SET rc2.strategy_id     = 'demo-strategy-alpha',
      rc2.oos_reason      = 'MaxDD breached -15% in Feb CPI spike; OOS Sharpe dropped to 0.8',
      rc2.retirement_note = 'No pivot hypothesis found; logic dead-ended',
      rc2.retired_at      = datetime('2026-04-01T09:00:00'),
      rc2.updated_at      = datetime()
MERGE (fc1)-[rt1:RETIRED_TO]->(rc2)
  SET rt1.retired_at = datetime('2026-04-01T09:00:00'),
      rt1.is_demo    = true
""".strip()


DEMO_TEARDOWN_CYPHER = """
MATCH (n) WHERE n.is_demo = true DETACH DELETE n
""".strip()
