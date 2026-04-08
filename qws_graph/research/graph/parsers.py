"""Parsers for V1 artifact formats (CSV and Markdown)."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .ids import canonical_json, champion_id, config_id, run_id, strategy_id
from .models import Champion, Config, Provenance, ResearchArtifact, Run, Strategy
from .schema_registry import (
    CORE_RISK_PARAM_COLUMNS,
    IGNORED_COLUMNS,
    RUN_PROPERTIES,
    all_config_keys,
    get_config_keys,
)

CSV_REQUIRED_ALIASES: dict[str, tuple[str, ...]] = {
    "total_trades": ("total_trades", "n"),
    "win_rate": ("win_rate",),
    "profit_factor": ("profit_factor",),
    "sharpe": ("sharpe",),
    "max_drawdown": ("max_drawdown", "max_dd"),
    "first_trade_ts": ("first_trade_ts",),
    "last_trade_ts": ("last_trade_ts",),
}

CSV_OPTIONAL_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": ("timestamp", "recorded_at", "run_at"),
    "total_r": ("total_r",),
    "avg_r": ("avg_r", "avg_r_per_trade"),
    "calmar": ("calmar",),
    "metrics_return": ("return",),  # "return" is a Python reserved word
    "tier": ("tier",),
    "params_json": ("params_json",),
    "risk_params": ("risk_params",),
}

STRATEGY_COLUMNS = {"strategy_id", "instrument", "timeframe", "direction", "logic_type"}
SECTION_ALIASES = {
    "config": "config",
    "is metrics": "is_metrics",
    "known fragilities": "known_fragilities",
    "oos command": "oos_command",
}
REQUIRED_CHAMPION_SECTIONS = {"config", "is_metrics", "known_fragilities", "oos_command"}
METRIC_KEY_ALIASES = {
    "avg_r_trade": "avg_r_per_trade",
    "max_drawdown": "max_drawdown_r",
}
TIMEFRAME_TOKEN_RE = re.compile(r"^\d+[mhdw]$", re.IGNORECASE)
LIST_ITEM_RE = re.compile(r"^(?:[-*]|\d+\.)\s+(.*)$")
METADATA_RE = re.compile(r"^\*\*(.+?)\*\*:\s*(.+)$")
PIVOT_RE = re.compile(r"--pivot-from\s+([a-f0-9]{12})", re.IGNORECASE)


def _file_hash(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _file_mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat().replace("+00:00", "Z")


def _artifact_path_text(path: Path, repo_root: Path | None = None) -> str:
    """Return a stable string representation of *path* for graph storage.

    When *repo_root* is provided, the path is normalized to a repo-relative
    POSIX string (e.g. ``research/results/futures/.../baseline.csv``).
    Absolute paths that fall outside the repo root are stored as-is.
    """
    if repo_root is not None:
        try:
            return path.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def _normalize_key(value: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", "", value.strip().lower())
    cleaned = cleaned.replace("/", " ")
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    return cleaned.strip("_")


def _normalize_section_name(value: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", "", value.strip().lower())
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return cleaned.strip()


def _strip_inline_commentary(value: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", value).strip()


def _parse_scalar(value: str) -> Any:
    text = value.strip()
    if not text:
        return None
    if text.startswith("{") or text.startswith("["):
        try:
            return _sorted_mapping(json.loads(text))
        except json.JSONDecodeError:
            return text
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if "," in text and not text.startswith("http"):
        parts = [part.strip() for part in text.split(",") if part.strip()]
        if len(parts) > 1:
            return [_parse_scalar(part) for part in parts]
    numeric_candidate = text.rstrip("%")
    try:
        if re.fullmatch(r"[-+]?\d+", numeric_candidate):
            return int(numeric_candidate)
        if re.fullmatch(r"[-+]?\d*\.\d+", numeric_candidate) or re.fullmatch(r"[-+]?\d+\.\d*", numeric_candidate):
            number = float(numeric_candidate)
            return number / 100 if text.endswith("%") else number
    except ValueError:
        return text
    return text


def _sorted_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sorted_mapping(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sorted_mapping(item) for item in value]
    return value


def _find_column(fieldnames: Iterable[str], aliases: Iterable[str]) -> str | None:
    field_lookup = {name.lower(): name for name in fieldnames}
    for alias in aliases:
        if alias.lower() in field_lookup:
            return field_lookup[alias.lower()]
    return None


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if not text:
        raise ValueError("timestamp is empty")
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        return datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.replace(tzinfo=UTC) if fmt == "%Y-%m-%d" else parsed
            except ValueError:
                continue
    raise ValueError(f"could not parse timestamp {value!r}")


def _compute_frequency_stats(
    total_trades: int,
    first_trade_ts: datetime,
    last_trade_ts: datetime,
    backtest_start: datetime | None,
    backtest_end: datetime | None,
) -> tuple[float | None, float | None]:
    """Compute active_window_frequency and duty_cycle from trade timestamps.

    active_window_frequency = total_trades / active_days
        where active_days = (last_trade_ts - first_trade_ts).total_seconds() / 86400

    duty_cycle = active_days / total_backtest_days
        where total_backtest_days = (backtest_end - backtest_start).total_seconds() / 86400
        Only computed when backtest_start and backtest_end are present.

    active_window_frequency is None on the zero-duration edge case (first == last).
    """
    active_seconds = (last_trade_ts - first_trade_ts).total_seconds()
    active_days = active_seconds / 86400.0

    if active_days <= 0.0:
        # Zero-duration: first and last trade at the same instant — frequency undefined.
        return None, None

    active_window_frequency = total_trades / active_days

    duty_cycle: float | None = None
    if backtest_start is not None and backtest_end is not None:
        total_seconds = (backtest_end - backtest_start).total_seconds()
        total_backtest_days = total_seconds / 86400.0
        if total_backtest_days > 0.0:
            duty_cycle = active_days / total_backtest_days

    return active_window_frequency, duty_cycle


def _payload_for_hash(artifact: ResearchArtifact) -> dict[str, Any]:
    payload = artifact.model_dump(mode="json")
    for run in payload.get("runs", []):
        run["provenance"]["ingested_at"] = "<normalized>"
    if payload.get("champion"):
        payload["champion"]["provenance"]["ingested_at"] = "<normalized>"
    if payload.get("blob"):
        payload["blob"]["provenance"]["ingested_at"] = "<normalized>"
    return payload


def research_artifact_payload_hash(artifact: ResearchArtifact) -> str:
    normalized = canonical_json(_payload_for_hash(artifact))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class UnknownFieldWarning:
    """Container for ignored fields encountered during parsing."""

    def __init__(self) -> None:
        self.fields: dict[str, set[str]] = {}

    def add_many(self, source: str, fields: Iterable[str]) -> None:
        unknown_fields = {field for field in fields if field}
        if not unknown_fields:
            return
        self.fields.setdefault(source, set()).update(unknown_fields)

    def messages(self) -> list[str]:
        return [
            f"Unknown columns in {source}: {', '.join(sorted(fields))}"
            for source, fields in sorted(self.fields.items())
        ]


class CSVParser:
    """Parser for baseline and grid CSV artifacts."""

    def __init__(
        self,
        artifact_path: Path,
        kind: str,
        ingested_at: datetime | None = None,
        repo_root: Path | None = None,
    ):
        if kind not in {"baseline_csv", "grid_csv"}:
            raise ValueError(f"kind must be baseline_csv or grid_csv, got {kind}")
        self.artifact_path = Path(artifact_path)
        self.kind = kind
        self.ingested_at = ingested_at or datetime.now(UTC)
        self.repo_root = repo_root
        self.unknown_warnings = UnknownFieldWarning()

    def parse(self) -> tuple[ResearchArtifact, list[str]]:
        if not self.artifact_path.exists():
            raise FileNotFoundError(f"Artifact not found: {self.artifact_path}")

        artifact_path_text = _artifact_path_text(self.artifact_path, self.repo_root)
        provenance = Provenance(
            artifact_path=artifact_path_text,
            artifact_hash=_file_hash(self.artifact_path),
            artifact_mtime_iso=_file_mtime_iso(self.artifact_path),
            ingested_at=self.ingested_at,
            parser_version="v1",
        )

        with self.artifact_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("CSV has no header row")

            self._validate_required_columns(reader.fieldnames)
            self._collect_unknown_columns(reader.fieldnames)

            rows = [row for row in reader if any((value or "").strip() for value in row.values())]
            if not rows:
                raise ValueError("CSV has no data rows")

        runs: list[Run] = []
        configs: list[Config] = []
        strategy_obj: Strategy | None = None

        for row_number, row in enumerate(rows, start=1):
            strategy = self._resolve_strategy(row)
            if strategy_obj is None:
                strategy_obj = strategy
            elif strategy.model_dump() != strategy_obj.model_dump():
                raise ValueError("CSV rows resolve to inconsistent strategy metadata")

            params_json, risk_params = self._parse_config_payload(row, strategy.logic_type)
            config_obj = Config(
                config_id=config_id(params_json, risk_params),
                params_json=params_json,
                risk_params=risk_params,
            )
            timestamp = self._resolve_timestamp(row, provenance.artifact_mtime_iso)
            run_total_trades = self._read_int(row, reader.fieldnames, "total_trades")
            first_trade_ts = self._read_required_datetime(row, reader.fieldnames, "first_trade_ts")
            last_trade_ts = self._read_required_datetime(row, reader.fieldnames, "last_trade_ts")
            backtest_start = self._read_raw_datetime(row, "backtest_start")
            backtest_end = self._read_raw_datetime(row, "backtest_end")
            active_window_frequency, duty_cycle = _compute_frequency_stats(
                run_total_trades, first_trade_ts, last_trade_ts, backtest_start, backtest_end
            )
            run_obj = Run(
                run_id=run_id(
                    strategy.strategy_id,
                    artifact_path_text,
                    f"{provenance.artifact_mtime_iso}:{row_number}:{config_obj.config_id}",
                ),
                strategy_id=strategy.strategy_id,
                timestamp=timestamp,
                sharpe=self._read_float(row, reader.fieldnames, "sharpe"),
                profit_factor=self._read_float(row, reader.fieldnames, "profit_factor"),
                win_rate=self._read_fraction(row, reader.fieldnames, "win_rate"),
                max_drawdown=self._read_float(row, reader.fieldnames, "max_drawdown"),
                total_trades=run_total_trades,
                total_r=self._read_optional_float(row, reader.fieldnames, "total_r"),
                calmar=self._read_optional_float(row, reader.fieldnames, "calmar"),
                metrics_return=self._read_optional_float(row, reader.fieldnames, "metrics_return"),
                tier=self._read_optional_str(row, reader.fieldnames, "tier"),
                first_trade_ts=first_trade_ts,
                last_trade_ts=last_trade_ts,
                active_window_frequency=active_window_frequency,
                duty_cycle=duty_cycle,
                artifact_path=artifact_path_text,
                provenance=provenance,
            )
            configs.append(config_obj)
            runs.append(run_obj)

        artifact = ResearchArtifact(
            kind=self.kind,
            strategy=strategy_obj,
            runs=runs,
            configs=configs,
        )
        return artifact, self.unknown_warnings.messages()

    def _validate_required_columns(self, fieldnames: list[str]) -> None:
        missing = [
            field
            for field, aliases in CSV_REQUIRED_ALIASES.items()
            if _find_column(fieldnames, aliases) is None
        ]
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")

    def _collect_unknown_columns(self, fieldnames: list[str]) -> None:
        recognized = set(STRATEGY_COLUMNS) | all_config_keys() | IGNORED_COLUMNS
        for aliases in CSV_REQUIRED_ALIASES.values():
            recognized.update(aliases)
        for aliases in CSV_OPTIONAL_ALIASES.values():
            recognized.update(aliases)
        # RUN_PROPERTIES uses the raw CSV column names (e.g. "return", not "metrics_return")
        recognized.update(RUN_PROPERTIES)
        unknown = sorted(field for field in fieldnames if field not in recognized)
        self.unknown_warnings.add_many(self.artifact_path.name, unknown)

    def _resolve_strategy(self, row: dict[str, str]) -> Strategy:
        inferred = _infer_strategy_from_artifact_name(self.artifact_path.stem)
        instrument = _clean_instrument(row.get("instrument")) or inferred["instrument"]
        timeframe = _normalize_timeframe(row.get("timeframe")) or inferred["timeframe"]
        direction = (row.get("direction") or inferred["direction"] or "").strip().lower()
        logic_type = (row.get("logic_type") or inferred["logic_type"] or "").strip().lower().replace("_", "-")

        missing = [
            name
            for name, value in {
                "instrument": instrument,
                "timeframe": timeframe,
                "direction": direction,
                "logic_type": logic_type,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"could not resolve strategy fields: {', '.join(missing)}")

        canonical_strategy_id = strategy_id(instrument, timeframe, direction, logic_type)
        provided_strategy_id = (row.get("strategy_id") or "").strip()
        if provided_strategy_id and provided_strategy_id != canonical_strategy_id:
            raise ValueError(
                "provided strategy_id does not match canonical strategy_id "
                f"({provided_strategy_id!r} != {canonical_strategy_id!r})"
            )

        return Strategy(
            strategy_id=canonical_strategy_id,
            instrument=instrument,
            timeframe=timeframe,
            direction=direction,
            logic_type=logic_type,
        )

    def _parse_config_payload(
        self, row: dict[str, str], logic_type: str | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        params_json: dict[str, Any] = {}
        risk_params: dict[str, Any] = {}

        if row.get("params_json"):
            parsed = _parse_scalar(row["params_json"])
            if not isinstance(parsed, dict):
                raise ValueError("params_json must decode to an object")
            params_json.update(parsed)
        if row.get("risk_params"):
            parsed = _parse_scalar(row["risk_params"])
            if not isinstance(parsed, dict):
                raise ValueError("risk_params must decode to an object")
            risk_params.update(parsed)

        for column in sorted(get_config_keys(logic_type)):
            if column not in row or not (row[column] or "").strip():
                continue
            parsed_value = _parse_scalar(row[column])
            if parsed_value is None:
                continue
            target = risk_params if column in CORE_RISK_PARAM_COLUMNS else params_json
            target[column] = parsed_value

        return _sorted_mapping(params_json), _sorted_mapping(risk_params)

    def _resolve_timestamp(self, row: dict[str, str], artifact_mtime_iso: str) -> datetime:
        timestamp_column = _find_column(row.keys(), CSV_OPTIONAL_ALIASES["timestamp"])
        if timestamp_column and (row[timestamp_column] or "").strip():
            return _parse_datetime(row[timestamp_column])
        return _parse_datetime(artifact_mtime_iso)

    def _read_float(self, row: dict[str, str], fieldnames: Iterable[str], field: str) -> float:
        column = _find_column(fieldnames, CSV_REQUIRED_ALIASES.get(field, CSV_OPTIONAL_ALIASES.get(field, (field,))))
        if column is None or not (row.get(column) or "").strip():
            raise ValueError(f"missing required field value: {field}")
        value = _parse_scalar(_strip_inline_commentary(row[column]))
        if isinstance(value, (int, float)):
            return float(value)
        raise ValueError(f"invalid float value for {field}: {row[column]!r}")

    def _read_optional_float(self, row: dict[str, str], fieldnames: Iterable[str], field: str) -> float | None:
        column = _find_column(fieldnames, CSV_OPTIONAL_ALIASES[field])
        if column is None or not (row.get(column) or "").strip():
            return None
        value = _parse_scalar(_strip_inline_commentary(row[column]))
        if isinstance(value, (int, float)):
            return float(value)
        raise ValueError(f"invalid float value for {field}: {row[column]!r}")

    def _read_fraction(self, row: dict[str, str], fieldnames: Iterable[str], field: str) -> float:
        value = self._read_float(row, fieldnames, field)
        return value / 100 if value > 1.0 else value

    def _read_int(self, row: dict[str, str], fieldnames: Iterable[str], field: str) -> int:
        column = _find_column(fieldnames, CSV_REQUIRED_ALIASES[field])
        if column is None or not (row.get(column) or "").strip():
            raise ValueError(f"missing required field value: {field}")
        value = _parse_scalar(_strip_inline_commentary(row[column]))
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        raise ValueError(f"invalid integer value for {field}: {row[column]!r}")

    def _read_optional_str(self, row: dict[str, str], fieldnames: Iterable[str], field: str) -> str | None:
        column = _find_column(fieldnames, CSV_OPTIONAL_ALIASES[field])
        if column is None:
            return None
        value = (row.get(column) or "").strip()
        return value or None

    def _read_required_datetime(self, row: dict[str, str], fieldnames: Iterable[str], field: str) -> datetime:
        """Read a required ISO-8601 datetime from a recognized required alias column."""
        column = _find_column(fieldnames, CSV_REQUIRED_ALIASES[field])
        if column is None or not (row.get(column) or "").strip():
            raise ValueError(f"missing required field value: {field}")
        return _parse_datetime(row[column])

    def _read_raw_datetime(self, row: dict[str, str], column_name: str) -> datetime | None:
        """Read an optional datetime from a column accessed by exact name (ignored columns)."""
        col = _find_column(row.keys(), (column_name,))
        if col is None or not (row.get(col) or "").strip():
            return None
        return _parse_datetime(row[col])


class ChampionMarkdownParser:
    """Parser for champion Markdown artifacts."""

    def __init__(
        self,
        artifact_path: Path,
        registry_path: Path | None = None,
        pivot_from_run_id: str | None = None,
        ingested_at: datetime | None = None,
        repo_root: Path | None = None,
    ):
        self.artifact_path = Path(artifact_path)
        self.registry_path = Path(registry_path) if registry_path else _default_registry_path(self.artifact_path)
        self.explicit_pivot_from_run_id = pivot_from_run_id
        self.ingested_at = ingested_at or datetime.now(UTC)
        self.repo_root = repo_root

    def parse(self) -> tuple[ResearchArtifact, list[str]]:
        if not self.artifact_path.exists():
            raise FileNotFoundError(f"Artifact not found: {self.artifact_path}")

        content = self.artifact_path.read_text(encoding="utf-8")
        provenance = Provenance(
            artifact_path=_artifact_path_text(self.artifact_path, self.repo_root),
            artifact_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            artifact_mtime_iso=_file_mtime_iso(self.artifact_path),
            ingested_at=self.ingested_at,
            parser_version="v1",
        )

        metadata = self._extract_metadata(content)
        sections = self._extract_sections(content)
        missing_sections = sorted(REQUIRED_CHAMPION_SECTIONS - set(sections))
        if missing_sections:
            raise ValueError(f"missing required champion sections: {', '.join(missing_sections)}")
        if "freeze_date" not in metadata:
            raise ValueError("missing required champion metadata: freeze_date")

        freeze_date = date.fromisoformat(metadata["freeze_date"])
        config_values = self._parse_markdown_mapping(sections["config"])
        metrics_summary = self._parse_metrics_section(sections["is_metrics"])
        fragilities = self._parse_fragilities(sections["known_fragilities"])
        strategy_obj = self._resolve_strategy(config_values)
        pivot_from_run_id = self.explicit_pivot_from_run_id or self._extract_pivot_from_run_id(sections["oos_command"])

        champion_obj = Champion(
            champion_id=champion_id(strategy_obj.strategy_id, freeze_date.isoformat()),
            strategy_id=strategy_obj.strategy_id,
            freeze_date=freeze_date,
            metrics_summary=metrics_summary,
            oos_status=self._resolve_oos_status(),
            fragilities=fragilities,
            artifact_path=_artifact_path_text(self.artifact_path, self.repo_root),
            pivot_from_run_id=pivot_from_run_id,
            provenance=provenance,
        )
        artifact = ResearchArtifact(kind="champion_md", strategy=strategy_obj, champion=champion_obj)
        return artifact, []

    def _extract_metadata(self, content: str) -> dict[str, str]:
        metadata: dict[str, str] = {}
        for line in content.splitlines():
            match = METADATA_RE.match(line.strip())
            if not match:
                continue
            key = _normalize_key(match.group(1))
            metadata[key] = match.group(2).strip()
        return metadata

    def _extract_sections(self, content: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        current_name: str | None = None
        current_lines: list[str] = []
        for line in content.splitlines():
            if line.startswith("## "):
                if current_name is not None:
                    sections[current_name] = "\n".join(current_lines).strip()
                raw_name = line[3:].strip()
                normalized = SECTION_ALIASES.get(_normalize_section_name(raw_name))
                current_name = normalized
                current_lines = []
                continue
            if current_name is not None:
                current_lines.append(line)
        if current_name is not None:
            sections[current_name] = "\n".join(current_lines).strip()
        return {key: value for key, value in sections.items() if key}

    def _parse_markdown_mapping(self, section: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in section.splitlines():
            match = LIST_ITEM_RE.match(line.strip())
            if not match:
                continue
            item = match.group(1)
            if ":" not in item:
                continue
            key, value = item.split(":", 1)
            values[_normalize_key(key)] = value.strip()
        return values

    def _parse_metrics_section(self, section: str) -> dict[str, float | int | str]:
        metrics: dict[str, float | int | str] = {}
        for key, raw_value in self._parse_markdown_mapping(section).items():
            key = METRIC_KEY_ALIASES.get(key, key)
            cleaned = _strip_inline_commentary(raw_value)
            parsed = _parse_scalar(cleaned)
            if parsed is None:
                continue
            metrics[key] = parsed
        if not metrics:
            raise ValueError("champion metrics section did not contain any metrics")
        return metrics

    def _parse_fragilities(self, section: str) -> list[str]:
        fragilities: list[str] = []
        for line in section.splitlines():
            match = LIST_ITEM_RE.match(line.strip())
            if match:
                fragilities.append(match.group(1).strip())
        if not fragilities:
            raise ValueError("champion fragilities section must contain at least one list item")
        return fragilities

    def _resolve_strategy(self, config_values: dict[str, str]) -> Strategy:
        inferred = _infer_strategy_from_artifact_name(self.artifact_path.stem)
        instrument = _clean_instrument(config_values.get("instrument")) or inferred["instrument"]
        timeframe = _normalize_timeframe(config_values.get("sweep_timeframe") or config_values.get("timeframe")) or inferred["timeframe"]
        direction = (config_values.get("direction") or inferred["direction"] or "").strip().lower()
        logic_type = inferred["logic_type"]
        missing = [
            name
            for name, value in {
                "instrument": instrument,
                "timeframe": timeframe,
                "direction": direction,
                "logic_type": logic_type,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"could not resolve champion strategy fields: {', '.join(missing)}")
        return Strategy(
            strategy_id=strategy_id(instrument, timeframe, direction, logic_type),
            instrument=instrument,
            timeframe=timeframe,
            direction=direction,
            logic_type=logic_type,
        )

    def _extract_pivot_from_run_id(self, section: str) -> str | None:
        match = PIVOT_RE.search(section)
        return match.group(1).lower() if match else None

    def _resolve_oos_status(self) -> str:
        if not self.registry_path or not self.registry_path.exists():
            return "oos_pending"
        try:
            registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid registry.json: {exc}") from exc
        if not isinstance(registry, list):
            return "oos_pending"
        artifact_name = self.artifact_path.name
        artifact_path = _artifact_path_text(self.artifact_path, self.repo_root)
        for entry in registry:
            if not isinstance(entry, dict):
                continue
            champion_file = entry.get("champion_file")
            if not isinstance(champion_file, str):
                continue
            champion_path = champion_file.replace("\\", "/")
            if champion_path.endswith(artifact_name) or champion_path == artifact_path:
                status = entry.get("status")
                if isinstance(status, str) and status.strip():
                    return status.strip()
        return "oos_pending"


def _clean_instrument(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    match = re.search(r"[A-Za-z]{1,4}", raw_value)
    return match.group(0).upper() if match else ""


def _normalize_timeframe(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    token = raw_value.strip().upper().replace(" ", "")
    return token


def _infer_strategy_from_artifact_name(stem: str) -> dict[str, str]:
    tokens = [token for token in re.split(r"[_\-]+", stem.lower()) if token]
    instrument = tokens[0].upper() if tokens else ""
    direction_index = next((index for index, token in enumerate(tokens) if token in {"bull", "bear", "long", "short"}), None)
    timeframe_index = next((index for index, token in enumerate(tokens) if TIMEFRAME_TOKEN_RE.match(token)), None)
    direction = tokens[direction_index] if direction_index is not None else ""
    timeframe = tokens[timeframe_index].upper() if timeframe_index is not None else ""

    logic_tokens: list[str] = []
    if direction_index is not None and timeframe_index is not None and direction_index < timeframe_index:
        logic_tokens = tokens[direction_index + 1:timeframe_index]
    elif direction_index is not None:
        logic_tokens = [
            token
            for token in tokens[direction_index + 1:]
            if not TIMEFRAME_TOKEN_RE.match(token) and not re.fullmatch(r"v\d+", token)
        ]
    logic_type = "-".join(logic_tokens)
    return {
        "instrument": instrument,
        "timeframe": timeframe,
        "direction": direction,
        "logic_type": logic_type,
    }


def _default_registry_path(artifact_path: Path) -> Path | None:
    for parent in artifact_path.parents:
        candidate = parent / "registry.json"
        if candidate.exists():
            return candidate
        candidate = parent / "research" / "results" / "registry.json"
        if candidate.exists():
            return candidate
    return None

