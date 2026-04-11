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
  rt.created_at = datetime()
SET rt.updated_at = datetime()
""".strip()


PATCH_RESEARCH_TARGET_QUERY = """
MATCH (rt:ResearchTarget {target_id: "singleton"})
SET rt += $overrides
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
RETURN {
  hypothesis_id: h.hypothesis_id,
  title: h.title,
  active_champion_matches: collect(DISTINCT active_ch.champion_id),
  aborted_strategy_matches: collect(DISTINCT aborted_s.strategy_id)
} AS result
LIMIT 1
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
# Demo graph seed / teardown (qw seed --demo)
#
# Deterministic, idempotent dummy provenance graph. Covers:
#   cross_artifact_correlation  — alpha + beta share family_id (same logic, two instruments)
#   runs_by_regime              — high_vol x2, trend_down, mean_reverting labels
#   regime_performance          — multiple regimes across two strategies
#   compare_strategy_performance — champions on ES and CL
#   downstream_champions        — PIVOTED_FROM edges on all champions
#   portfolio_alpha             — demo_champ_002 has oos_pass
#   list_oos_pending            — demo_champ_001 has oos_pending
#   promotion_candidates        — demo_run_004: dual-hurdle pass, not yet promoted
#   list_aborted                — demo-strategy-gamma: ABORTED with abort_reason
#   run_history                 — multiple runs on alpha (3 runs)
#   instrument_concentration    — ES champion + CL champion
#   recent_champions            — two active champions
#   list_hypotheses             — demo_hyp_001: open; demo_hyp_002: confirmed + TESTED_AS alpha
#   hypothesis_audit            — demo_hyp_002 → alpha → champion lineage
#   check_redundancy            — demo_hyp_001 title matches no active champions
#
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
      ch1.metrics_return = 0.087,
      ch1.metrics_total_trades = 55,
      ch1.metrics_win_rate = 0.62,
      ch1.metrics_profit_factor = 1.92,
      ch1.best_evidence_score = 23.0,
      ch1.tier = 'institutional',
      ch1.oos_status = 'oos_pending',
      ch1.auto_promoted = true,
      ch1.freeze_date = date('2026-04-01'),
      ch1.updated_at = datetime(),
      ch1.is_demo = true
MERGE (s1)-[:PRODUCED_CHAMPION]->(ch1)
MERGE (ch1)-[:PIVOTED_FROM]->(r2)
MERGE (ch1)-[:WAS_CHAMPION]->(rc1)

// ── Champion lineage — Beta ──────────────────────────────────────────────────

// Demo Champion 002 — beta current; oos_pass; appears in portfolio_alpha
MERGE (ch2:Champion {champion_id: 'demo_champ_002'})
  ON CREATE SET ch2.created_at = datetime()
  SET ch2.strategy_id = 'demo-strategy-beta',
      ch2.metrics_sharpe = 4.6,
      ch2.metrics_return = 0.099,
      ch2.metrics_total_trades = 32,
      ch2.metrics_win_rate = 0.66,
      ch2.metrics_profit_factor = 2.14,
      ch2.best_evidence_score = 26.03,
      ch2.tier = 'institutional',
      ch2.oos_status = 'oos_pass',
      ch2.oos_date = date('2026-04-05'),
      ch2.auto_promoted = true,
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
      h1.updated_at = datetime()
MERGE (hsrc1:HypothesisSource {source_key: 'user'})
  ON CREATE SET hsrc1.created_at = datetime()
MERGE (hsrc1)-[:SUGGESTED {source: 'user'}]->(h1)

// Demo Hypothesis 002 — confirmed + TESTED_AS demo-strategy-alpha; for hypothesis_audit
MERGE (h2:Hypothesis {hypothesis_id: 'demo_hyp_002'})
  ON CREATE SET h2.created_at = datetime('2026-02-01T10:00:00'), h2.is_demo = true
  SET h2.title = 'Demo alpha bear logic exploits London open liquidity imbalance',
      h2.status = 'confirmed',
      h2.updated_at = datetime()
MERGE (hsrc2:HypothesisSource {source_key: 'llm'})
  ON CREATE SET hsrc2.created_at = datetime()
MERGE (hsrc2)-[:SUGGESTED {source: 'llm'}]->(h2)
MERGE (h2)-[:TESTED_AS]->(s1)
""".strip()


DEMO_TEARDOWN_CYPHER = """
MATCH (n) WHERE n.is_demo = true DETACH DELETE n
""".strip()


