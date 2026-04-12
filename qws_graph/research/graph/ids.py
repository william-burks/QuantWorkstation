"""Canonical ID generation and normalization utilities.

Reference: docs/graph_v1_contract.md - Canonical ID Strategy
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class CriticalIDError(RuntimeError):
    """Raised when deterministic ID collision is detected."""

    pass


def normalize_text(value: str) -> str:
    """Normalize text for deterministic ID generation.

    Steps:
    1. Lowercase
    2. Strip leading/trailing whitespace
    3. Replace spaces and underscores with `-`
    4. Remove characters outside [a-z0-9-]
    5. Collapse repeated `-`
    6. Strip leading/trailing `-`
    """
    s = value.strip().lower().replace("_", " ")
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def canonical_json(value: Any) -> str:
    """Serialize to canonical JSON (sorted keys, minimal separators)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def hash12(*parts: str) -> str:
    """Hash parts with SHA-256 and return first 12 hex characters."""
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def strategy_id(instrument: str, timeframe: str, direction: str, logic_type: str) -> str:
    """Generate canonical strategy_id from components.

    Pattern: <normalized instrument>-<normalized timeframe>-<normalized direction>
    -<normalized logic_type>
    """
    slug = "-".join(
        [
            normalize_text(instrument),
            normalize_text(timeframe),
            normalize_text(direction),
            normalize_text(logic_type),
        ]
    )
    return slug


def run_id(strategy_id_value: str, artifact_path: str, artifact_mtime_iso: str) -> str:
    """Generate deterministic run_id from strategy, artifact path, and mtime.

    Ensures same artifact is always hashed to same run_id.
    """
    return hash12(strategy_id_value, normalize_text(artifact_path), artifact_mtime_iso)


def config_id(params: dict[str, Any], risk_params: dict[str, Any]) -> str:
    """Generate deterministic config_id from parameter dictionaries.

    Uses canonical JSON serialization to ensure same params always hash identically.
    """
    return hash12(canonical_json(params), canonical_json(risk_params))


def champion_id(strategy_id_value: str, freeze_date_iso: str) -> str:
    """Generate deterministic champion_id from strategy and freeze date.

    Pattern: hash12(strategy_id, freeze_date_iso)
    """
    return hash12(strategy_id_value, freeze_date_iso)


def source_hash(source_bytes: bytes) -> str:
    """Hash raw strategy source file bytes to a 12-character hex string.

    Used as the ``source_hash`` input to ``family_id``. Changing the source
    content (i.e., the logic) produces a different hash; changing parameters
    in a config file does not.
    """
    return hashlib.sha256(source_bytes).hexdigest()[:12]


def family_id(logic_type: str, direction: str, src_hash: str) -> str:
    """Deterministic family identifier from logic type, direction, and source hash.

    A Strategy Family is defined by its core signal logic, not by instrument,
    timeframe, or parameter choices.  Two strategies that share the same
    ``logic_type``, ``direction``, and source code hash will share a
    ``family_id`` even when deployed on different instruments or timeframes.

    Args:
        logic_type:  Canonical logic category (e.g. ``"MeanReversion"``).
        direction:   Trade direction (e.g. ``"bear"``).
        src_hash:    12-character hex digest from :func:`source_hash`.

    Returns:
        12-character hex string stable across filenames and paths.
    """
    return hash12(normalize_text(logic_type), normalize_text(direction), src_hash)


def run_stats_summary_id(
    strategy_id_value: str, artifact_path: str, artifact_mtime_iso: str
) -> str:
    """Deterministic summary_id for a RunStatsSummary node.

    Merges naturally when the same CSV is re-ingested after modification
    (mtime changes → new summary replaces old).
    """
    return hash12(strategy_id_value, normalize_text(artifact_path), artifact_mtime_iso)

