# mypy: ignore-errors
"""Integration tests for QWS-1302: research-navigator agent.

Tests:
- Agent file has all required phases and sections
- Guard script blocks prohibited commands
- Guard script allows permitted qw query commands
- Guard script blocks writes outside research/ideas/
- Cold-start scenario: agent produces 'No prior research' message (file content check)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
AGENT_FILE = REPO_ROOT / ".claude/agents/research-navigator.md"
GUARD_SCRIPT = REPO_ROOT / ".claude/scripts/agent-research-guard.sh"


# ---------------------------------------------------------------------------
# Agent file structure tests
# ---------------------------------------------------------------------------


class TestNavigatorAgentFile:
    """Validate agent file contains required phases and output contracts."""

    def test_agent_file_exists(self) -> None:
        assert AGENT_FILE.exists(), f"Agent file missing: {AGENT_FILE}"

    def test_has_four_phases(self) -> None:
        content = AGENT_FILE.read_text()
        assert "Phase 1" in content, "Missing Phase 1 (Session Start)"
        assert "Phase 2" in content, "Missing Phase 2 (Redundancy Check)"
        assert "Phase 3" in content, "Missing Phase 3 (Mid-Session Pivot)"
        assert "Phase 4" in content, "Missing Phase 4 (Session Wrap)"

    def test_phase1_ranked_shortlist_format(self) -> None:
        content = AGENT_FILE.read_text()
        # Phase 1 must define a numbered shortlist output (not raw table)
        assert "Next Direction Shortlist" in content, "Missing shortlist output format"
        assert "1." in content, "Missing numbered ranking in Phase 1 output"
        assert "rationale" in content.lower(), "Missing rationale in Phase 1 format"

    def test_phase1_cold_start_clause(self) -> None:
        content = AGENT_FILE.read_text()
        assert "cold start" in content.lower() or "cold-start" in content.lower(), (
            "Missing cold-start handling"
        )
        assert "No prior research" in content, "Missing 'No prior research — cold start' message"

    def test_phase2_redundancy_check(self) -> None:
        content = AGENT_FILE.read_text()
        assert "check_redundancy" in content, "Missing check_redundancy in Phase 2"
        assert "silently" in content.lower(), "Redundancy check must run silently"

    def test_phase3_bundle_json(self) -> None:
        content = AGENT_FILE.read_text()
        assert "bundle.json" in content, "Phase 3 must read bundle.json"
        assert "BRANCH" in content, "Missing BRANCH verdict in Phase 3"
        assert "ABANDON" in content, "Missing ABANDON verdict in Phase 3"
        assert "CONTINUE" in content, "Missing CONTINUE verdict in Phase 3"

    def test_phase4_findings_update(self) -> None:
        content = AGENT_FILE.read_text()
        assert "record --hypothesis" in content and "findings" in content, (
            "Phase 4 must update findings on hypothesis"
        )
        assert "research/ideas/session" in content, (
            "Phase 4 must write session notes to research/ideas/"
        )

    def test_reads_project_memory(self) -> None:
        content = AGENT_FILE.read_text()
        assert "agent-memory" in content or "MEMORY.md" in content, (
            "Agent must read project memory at session start"
        )

    def test_tool_list_scoped(self) -> None:
        content = AGENT_FILE.read_text()
        # Bash must be scoped to qw query and qw record --hypothesis only
        assert "qw query" in content, "Bash scope missing qw query"
        assert "qw record --hypothesis" in content, "Bash scope missing qw record --hypothesis"
        # Write must be scoped to research/ideas/
        assert "research/ideas/" in content, "Write scope missing research/ideas/"

    def test_queued_hypotheses_in_phase1(self) -> None:
        content = AGENT_FILE.read_text()
        assert "queued_hypotheses" in content, "Phase 1 must run queued_hypotheses query"


# ---------------------------------------------------------------------------
# Guard script tests — run guard with synthetic JSON inputs
# ---------------------------------------------------------------------------


def _run_guard(tool_name: str, **kwargs: str) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    """Run guard script with synthetic tool input JSON."""
    payload: dict = {"tool_name": tool_name, "tool_input": kwargs}
    return subprocess.run(
        ["bash", str(GUARD_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


class TestResearchGuardBlocks:
    """Guard script must block all prohibited commands."""

    def test_blocks_qw_degrade(self) -> None:
        result = _run_guard("Bash", command="qw degrade --champion abc123")
        assert result.returncode == 2, "Guard must block qw degrade"

    def test_blocks_qw_retire(self) -> None:
        result = _run_guard("Bash", command="qw retire --champion abc123")
        assert result.returncode == 2, "Guard must block qw retire"

    def test_blocks_qw_monitor(self) -> None:
        result = _run_guard("Bash", command="qw monitor --champion abc123")
        assert result.returncode == 2, "Guard must block qw monitor"

    def test_blocks_qw_abort(self) -> None:
        result = _run_guard("Bash", command="qw abort --strategy abc123")
        assert result.returncode == 2, "Guard must block qw abort"

    def test_blocks_qw_record_bundle(self) -> None:
        result = _run_guard("Bash", command="qw record --bundle /path/to/bundle")
        assert result.returncode == 2, "Guard must block qw record --bundle"

    def test_blocks_git_commit(self) -> None:
        result = _run_guard("Bash", command="git commit -m 'message'")
        assert result.returncode == 2, "Guard must block git commit"

    def test_blocks_git_push(self) -> None:
        result = _run_guard("Bash", command="git push origin main")
        assert result.returncode == 2, "Guard must block git push"

    def test_blocks_write_outside_ideas(self) -> None:
        result = _run_guard("Write", file_path="/some/other/path/file.md")
        assert result.returncode == 2, "Guard must block writes outside research/ideas/"

    def test_blocks_python_research(self) -> None:
        result = _run_guard("Bash", command="python research/runner.py")
        assert result.returncode == 2, "Guard must block python research/"

    def test_blocks_python_m_research(self) -> None:
        result = _run_guard("Bash", command="python -m research.runner")
        assert result.returncode == 2, "Guard must block python -m research"


class TestResearchGuardAllows:
    """Guard script must allow permitted operations."""

    def test_allows_qw_query(self) -> None:
        result = _run_guard("Bash", command="qw query --name recent_champions")
        assert result.returncode == 0, f"Guard must allow qw query; stderr={result.stderr}"

    def test_allows_qw_record_hypothesis(self) -> None:
        result = _run_guard("Bash", command='qw record --hypothesis "test idea" --queue')
        assert result.returncode == 0, (
            f"Guard must allow qw record --hypothesis; stderr={result.stderr}"
        )

    def test_allows_write_to_ideas(self) -> None:
        result = _run_guard("Write", file_path="/path/to/repo/research/ideas/session_2026-04-13.md")
        assert result.returncode == 0, (
            f"Guard must allow write to research/ideas/; stderr={result.stderr}"
        )

    def test_allows_qw_query_queued_hypotheses(self) -> None:
        result = _run_guard("Bash", command="qw query --name queued_hypotheses")
        assert result.returncode == 0, (
            f"Guard must allow queued_hypotheses query; stderr={result.stderr}"
        )
