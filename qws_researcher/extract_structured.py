"""
Structured extraction pipeline.

Takes a Paper and calls Claude to extract 7 fields into a markdown file
at data/extracts/<paper_id>.md. The quant-strategist companion agent reads
these files — not the raw papers.

Usage:
    from qws_researcher.extract_structured import extract_paper
    extract_paper(paper, data_dir="qws_researcher/data")
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import anthropic

from qws_researcher import Paper, id_safe

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_ABSTRACT_CHARS = 3_000
_MAX_FULL_TEXT_CHARS = 8_000

_SYSTEM = """\
You are a systematic quant finance researcher. Extract structured fields from an academic paper.
Respond with valid JSON only — no prose, no markdown fences, no explanation."""

_USER_TEMPLATE = """\
Extract these fields from the paper below. Be terse. Use "unknown" when the paper does not report a field.

Fields to extract:
- signal_type: one of [momentum, mean-reversion, carry, microstructure, volatility, macro, alternative, multi, other]
- instrument_class: one of [equity, futures, crypto, fx, rates, commodities, multi, other]
- timeframe: one of [tick, intraday, daily, weekly, monthly, multi]
- key_finding: one sentence — the core result (include Sharpe/alpha if reported)
- sample_period: e.g. "2000–2020" or "unknown"
- failure_mode: one sentence on when/why this strategy fails, or "not reported"
- replicated: one of [yes, no, partial, unknown]
- confidence: one of [high, medium, low] — high if paper has clear methodology + results, low if abstract only

Paper title: {title}
Published: {date}

Abstract:
{abstract}

{full_text_section}"""


def _build_prompt(paper: Paper) -> str:
    abstract = (paper.abstract or "")[:_MAX_ABSTRACT_CHARS]
    date = paper.published_date or "unknown"
    title = paper.title or paper.id

    full_text_section = ""
    if paper.full_text:
        snippet = paper.full_text[:_MAX_FULL_TEXT_CHARS]
        full_text_section = f"Full text (first {_MAX_FULL_TEXT_CHARS} chars):\n{snippet}"

    return _USER_TEMPLATE.format(
        title=title,
        date=date,
        abstract=abstract,
        full_text_section=full_text_section,
    )


def _parse_response(text: str) -> dict:
    # Strip markdown fences if model adds them despite instructions
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    return json.loads(text)


def extract_paper(paper: Paper, data_dir: str = "data") -> Path | None:
    """
    Extract structured fields from a paper using Claude.
    Writes to data/extracts/<paper_id>.md.
    Returns the path written, or None on failure.
    Skips if extract already exists.
    """
    extracts_dir = Path(data_dir) / "extracts"
    extracts_dir.mkdir(parents=True, exist_ok=True)

    out_path = extracts_dir / f"{id_safe(paper.id)}.md"
    if out_path.exists():
        logger.debug("Extract already exists: %s", out_path)
        return out_path

    if not paper.abstract and not paper.full_text:
        logger.warning("No content to extract from %s — skipping", paper.id)
        return None

    prompt = _build_prompt(paper)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
    except Exception as e:
        logger.error("Claude extraction failed for %s: %s", paper.id, e)
        return None

    try:
        fields = _parse_response(raw)
    except Exception as e:
        logger.error("Failed to parse Claude response for %s: %s\nRaw: %s", paper.id, e, raw[:200])
        return None

    # Write markdown extract
    title = paper.title or paper.id
    authors = ", ".join(paper.authors[:3]) + (" et al." if len(paper.authors) > 3 else "")
    date = paper.published_date or "unknown"

    md = f"""---
paper_id: {paper.id}
title: "{title}"
authors: "{authors}"
published: "{date}"
source: {paper.source}
url: {paper.url}
signal_type: {fields.get("signal_type", "unknown")}
instrument_class: {fields.get("instrument_class", "unknown")}
timeframe: {fields.get("timeframe", "unknown")}
replicated: {fields.get("replicated", "unknown")}
confidence: {fields.get("confidence", "low")}
---

## Key Finding
{fields.get("key_finding", "unknown")}

## Sample Period
{fields.get("sample_period", "unknown")}

## Failure Mode
{fields.get("failure_mode", "not reported")}

## Abstract
{paper.abstract or ""}
"""

    out_path.write_text(md, encoding="utf-8")
    logger.info("Extracted: %s → %s", paper.id, out_path.name)
    return out_path
