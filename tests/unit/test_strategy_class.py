"""Unit tests for strategy_class taxonomy (QWS-1012).

Tests cover:
- Strategy model accepts nullable strategy_class field
- bundle manifest strategy_class is passed through correctly
- query preset catalog registration
- store method signatures (no live Neo4j needed)
"""

from __future__ import annotations

from research.graph.models import Strategy
from research.graph.query_presets import PRESET_CATALOG, PresetSpec

# ---------------------------------------------------------------------------
# Strategy model
# ---------------------------------------------------------------------------


def test_strategy_model_accepts_null_strategy_class() -> None:
    """strategy_class is optional — Strategy without it must not raise."""
    s = Strategy(
        strategy_id="es-1h-bear-test",
        instrument="ES",
        timeframe="1h",
        direction="bear",
        logic_type="test",
    )
    assert s.strategy_class is None


def test_strategy_model_accepts_string_strategy_class() -> None:
    """strategy_class stores the supplied value."""
    s = Strategy(
        strategy_id="es-1h-bear-test",
        instrument="ES",
        timeframe="1h",
        direction="bear",
        logic_type="test",
        strategy_class="liquidity_sweep",
    )
    assert s.strategy_class == "liquidity_sweep"


def test_strategy_model_dump_includes_strategy_class() -> None:
    """model_dump includes strategy_class (needed for Cypher payload)."""
    s = Strategy(
        strategy_id="es-1h-bear-test",
        instrument="ES",
        timeframe="1h",
        direction="bear",
        logic_type="test",
        strategy_class="momentum_breakout",
    )
    payload = s.model_dump(mode="json")
    assert payload["strategy_class"] == "momentum_breakout"


def test_strategy_model_dump_null_strategy_class() -> None:
    """Null strategy_class serialises as None — not absent."""
    s = Strategy(
        strategy_id="es-1h-bear-test",
        instrument="ES",
        timeframe="1h",
        direction="bear",
        logic_type="test",
    )
    payload = s.model_dump(mode="json")
    assert "strategy_class" in payload
    assert payload["strategy_class"] is None


# ---------------------------------------------------------------------------
# Preset catalog
# ---------------------------------------------------------------------------


def test_portfolio_by_class_preset_registered() -> None:
    """portfolio_by_class preset appears in PRESET_CATALOG."""
    assert "portfolio_by_class" in PRESET_CATALOG


def test_portfolio_by_class_preset_spec() -> None:
    """portfolio_by_class preset has correct spec fields."""
    spec: PresetSpec = PRESET_CATALOG["portfolio_by_class"]
    assert spec.name == "portfolio_by_class"
    assert spec.requires_graph is True
    assert len(spec.params) == 0  # no required params


def test_portfolio_by_class_no_required_params() -> None:
    """portfolio_by_class accepts empty params dict without error."""
    from research.graph.query_presets import validate_params

    spec = PRESET_CATALOG["portfolio_by_class"]
    errors = validate_params(spec, {})
    assert errors == []


# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------


def test_portfolio_by_class_cypher_constant() -> None:
    """PORTFOLIO_BY_CLASS_CYPHER is importable and non-empty."""
    from research.graph.cypher import PORTFOLIO_BY_CLASS_CYPHER

    assert isinstance(PORTFOLIO_BY_CLASS_CYPHER, str)
    assert "strategy_class" in PORTFOLIO_BY_CLASS_CYPHER
    assert "Strategy" in PORTFOLIO_BY_CLASS_CYPHER


def test_patch_strategy_class_cypher_constant() -> None:
    """PATCH_STRATEGY_CLASS_QUERY references correct parameters."""
    from research.graph.cypher import PATCH_STRATEGY_CLASS_QUERY

    assert "$strategy_id" in PATCH_STRATEGY_CLASS_QUERY
    assert "$strategy_class" in PATCH_STRATEGY_CLASS_QUERY


def test_get_unclassified_strategies_cypher_constant() -> None:
    """GET_UNCLASSIFIED_STRATEGIES_QUERY filters NULL strategy_class."""
    from research.graph.cypher import GET_UNCLASSIFIED_STRATEGIES_QUERY

    assert "strategy_class IS NULL" in GET_UNCLASSIFIED_STRATEGIES_QUERY


# ---------------------------------------------------------------------------
# CSV_INGEST_QUERY includes strategy_class
# ---------------------------------------------------------------------------


def test_csv_ingest_query_sets_strategy_class() -> None:
    """CSV_INGEST_QUERY sets strategy_class from strategy payload."""
    from research.graph.cypher import CSV_INGEST_QUERY

    assert "s.strategy_class" in CSV_INGEST_QUERY


# ---------------------------------------------------------------------------
# store method signatures
# ---------------------------------------------------------------------------


def test_store_has_patch_strategy_class_method() -> None:
    """GraphStore exposes patch_strategy_class method."""
    from research.graph.store import GraphStore

    assert hasattr(GraphStore, "patch_strategy_class")
    assert callable(GraphStore.patch_strategy_class)


def test_store_has_get_unclassified_strategies_method() -> None:
    """GraphStore exposes get_unclassified_strategies method."""
    from research.graph.store import GraphStore

    assert hasattr(GraphStore, "get_unclassified_strategies")
    assert callable(GraphStore.get_unclassified_strategies)


# ---------------------------------------------------------------------------
# data_dictionary.yaml
# ---------------------------------------------------------------------------


def test_data_dictionary_contains_strategy_class() -> None:
    """data_dictionary.yaml registers strategy_class under Strategy.properties."""
    from pathlib import Path

    yaml_path = Path(__file__).parents[2] / "docs" / "graph" / "data_dictionary.yaml"
    content = yaml_path.read_text(encoding="utf-8")
    assert "strategy_class:" in content
    assert "liquidity_sweep" in content
