"""Unit tests for QWS-1404: Fix cartesian product bug in GET_CHECK_REDUNDANCY_V1_CYPHER.

Tests verify the Cypher string structure — no live Neo4j required.
"""

from __future__ import annotations

import re

from qws_graph.research.graph.query import GET_CHECK_REDUNDANCY_V1_CYPHER


class TestRedundancyCypherStructure:
    """Verify the fixed query has WITH breaks between OPTIONAL MATCH clauses."""

    def test_cypher_has_with_after_first_optional_match(self) -> None:
        """First OPTIONAL MATCH must be followed by a WITH that collects active_champion_matches."""
        pattern = (
            r"OPTIONAL MATCH \(active_s:Strategy\)-\[:PRODUCED_CHAMPION\]->\(active_ch:Champion\)"
            r".*?WITH h,\s*collect\(DISTINCT active_ch\.champion_id\) AS active_champion_matches"
        )
        assert re.search(pattern, GET_CHECK_REDUNDANCY_V1_CYPHER, re.DOTALL), (
            "Expected WITH break after first OPTIONAL MATCH collecting active_champion_matches"
        )

    def test_cypher_has_with_after_second_optional_match(self) -> None:
        """Second OPTIONAL MATCH must be followed by a WITH that carries active_champion_matches."""
        pattern = (
            r"OPTIONAL MATCH \(aborted_s:Strategy\)"
            r".*?WITH h,\s*active_champion_matches,\s*collect\(DISTINCT aborted_s\.strategy_id\) AS aborted_strategy_matches"
        )
        assert re.search(pattern, GET_CHECK_REDUNDANCY_V1_CYPHER, re.DOTALL), (
            "Expected WITH break after second OPTIONAL MATCH collecting aborted_strategy_matches"
        )

    def test_cypher_no_cartesian_product(self) -> None:
        """Three OPTIONAL MATCH clauses must NOT appear consecutively without a WITH between them."""
        # Find all OPTIONAL MATCH positions
        positions = [
            m.start() for m in re.finditer(r"OPTIONAL MATCH", GET_CHECK_REDUNDANCY_V1_CYPHER)
        ]
        assert len(positions) == 3, f"Expected 3 OPTIONAL MATCH clauses, got {len(positions)}"

        # Between each consecutive pair there must be a WITH keyword
        for i in range(len(positions) - 1):
            segment = GET_CHECK_REDUNDANCY_V1_CYPHER[positions[i] : positions[i + 1]]
            assert "WITH" in segment, (
                f"No WITH found between OPTIONAL MATCH #{i + 1} and #{i + 2} — "
                "cartesian product bug still present"
            )

    def test_cypher_return_uses_collected_variables(self) -> None:
        """RETURN must reference pre-collected variables, not re-collect from OPTIONAL MATCH."""
        # After the fix, RETURN uses active_champion_matches and aborted_strategy_matches directly
        assert "active_champion_matches: active_champion_matches" in GET_CHECK_REDUNDANCY_V1_CYPHER
        assert (
            "aborted_strategy_matches: aborted_strategy_matches" in GET_CHECK_REDUNDANCY_V1_CYPHER
        )

    def test_cypher_includes_hypothesis_id_and_title_in_return(self) -> None:
        """RETURN block must include hypothesis_id and title fields."""
        assert "hypothesis_id: h.hypothesis_id" in GET_CHECK_REDUNDANCY_V1_CYPHER
        assert "title: h.title" in GET_CHECK_REDUNDANCY_V1_CYPHER

    def test_cypher_has_limit_1(self) -> None:
        """Query must end with LIMIT 1 to guarantee single-row result."""
        assert "LIMIT 1" in GET_CHECK_REDUNDANCY_V1_CYPHER

    def test_cypher_semantic_match_still_present(self) -> None:
        """SEMANTICALLY_RELATED optional match must still be present after the fix."""
        assert "SEMANTICALLY_RELATED" in GET_CHECK_REDUNDANCY_V1_CYPHER
        assert "sem_h:Hypothesis" in GET_CHECK_REDUNDANCY_V1_CYPHER
