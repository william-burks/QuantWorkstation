-- portfolio_by_class (QWS-1012)
-- Groups active (non-ABORTED) Strategy nodes by strategy_class.
-- Unclassified strategies appear under '__unclassified__'.
-- Used by: qw query --name portfolio_by_class

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
