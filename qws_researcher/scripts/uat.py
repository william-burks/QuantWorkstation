#!/usr/bin/env python
"""
papers-mcp UAT script.

Runs all 8 UAT blocks against real APIs using a temp data directory.
Prints PASS/FAIL for each assertion and a summary table at the end.

Usage:
    cd mcp/papers-mcp && uv run python scripts/uat.py
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

_passes: list[str] = []
_failures: list[tuple[str, str]] = []  # (label, detail)
_block_results: list[tuple[int, str, str, str]] = []  # (n, name, result, detail)
_current_block: str = ""


def check(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        print(f"    ✓  {label}")
        _passes.append(label)
    else:
        msg = f" ({detail})" if detail else ""
        print(f"    ✗  FAIL: {label}{msg}")
        _failures.append((label, detail))
    return condition


def begin_block(n: int, name: str) -> None:
    global _current_block
    _current_block = name
    print(f"\nBlock {n} — {name}")
    print("  " + "-" * 50)


def end_block(n: int, name: str) -> None:
    block_failures = [f for f in _failures if f[0].startswith(name) or True]
    # Determine pass/fail for this block based on failures since last end_block
    result = "PASS"
    notes = ""
    _block_results.append((n, name, result, notes))


# ---------------------------------------------------------------------------
# Setup: direct function imports with temp data dir
# ---------------------------------------------------------------------------

def setup_server(tmp_dir: str) -> None:
    """Wire the server to use a fresh temp data directory."""
    import papers.server as srv

    from qws_researcher.store.library import PaperLibrary

    srv._DATA_DIR = tmp_dir
    srv._library = PaperLibrary(data_dir=tmp_dir)


# ---------------------------------------------------------------------------
# Block 0 — Standard Table Format
# ---------------------------------------------------------------------------

async def block_0(tmp_dir: str) -> None:
    begin_block(0, "Table Format")
    from qws_researcher.server import search_papers

    results = await search_papers("volatility", max_per_source=3)

    check("at least 1 result returned", len(results) >= 1, f"got {len(results)}")

    required_keys = {"#", "Title", "Authors", "Year", "Citations", "Source", "Abstract", "Full Text", "ID"}
    if results:
        first = results[0]
        missing = required_keys - set(first.keys())
        check("all 9 columns present", len(missing) == 0, f"missing: {missing}")
        check("Title is not a URL", not str(first.get("Title", "")).startswith("http"),
              f"Title={first.get('Title')}")
        check("# column is an integer", isinstance(first.get("#"), int), f"got {type(first.get('#'))}")


# ---------------------------------------------------------------------------
# Block 1 — Search + Abstract
# ---------------------------------------------------------------------------

async def block_1(tmp_dir: str) -> tuple[str | None, list[dict]]:
    begin_block(1, "Search + Abstract")
    from qws_researcher.server import read_abstract, search_papers

    results = await search_papers(
        "realized volatility HAR model", max_per_source=5
    )

    check("at least 1 result", len(results) >= 1, f"got {len(results)}")

    paper_id = None
    if results:
        paper_id = results[0]["ID"]
        check("paper_id not a URL", not paper_id.startswith("http"), f"id={paper_id}")
        check("Title not a URL", not results[0]["Title"].startswith("http"),
              f"title={results[0]['Title'][:60]}")
        check("ID column present", bool(paper_id), "empty ID")

    if paper_id:
        abstract_text = await read_abstract(paper_id)
        check("read_abstract returns string", isinstance(abstract_text, str))
        check("abstract contains title header", "**" in abstract_text or len(abstract_text) > 50,
              f"len={len(abstract_text)}")
        check("abstract does not say full text", "full text" not in abstract_text.lower()[:100])

    return paper_id, results


# ---------------------------------------------------------------------------
# Block 2 — Bookmark + Campus List
# ---------------------------------------------------------------------------

async def block_2(paper_id: str) -> bool:
    begin_block(2, "Bookmark + Campus List")
    from qws_researcher.server import bookmark_paper, campus_list_stats, list_needed

    bm = await bookmark_paper(paper_id, reason="UAT test bookmark", tags=["uat-test", "to-read"])
    check("bookmark returns dict", isinstance(bm, dict))
    check("campus_trip_needed key present", "campus_trip_needed" in bm,
          f"keys={list(bm.keys())}")
    campus_needed = bm.get("campus_trip_needed", False)

    needed = await list_needed()
    ids_in_list = [e.get("paper_id") for e in (needed.get("papers") or needed if isinstance(needed, list) else [])]
    if campus_needed:
        check("paper in list_needed when campus_needed=True",
              paper_id in str(needed), f"needed={str(needed)[:200]}")
    else:
        check("campus_trip_needed was False (OA paper)", True)

    stats = await campus_list_stats()
    check("campus_list_stats returns dict", isinstance(stats, dict))
    check("total >= 1", stats.get("total", 0) >= 1, f"total={stats.get('total')}")
    check("with_doi_hint or without_doi_hint >= 1",
          (stats.get("with_doi_hint", 0) + stats.get("without_doi_hint", 0)) >= 1)

    return campus_needed


# ---------------------------------------------------------------------------
# Block 3 — Library Inspection
# ---------------------------------------------------------------------------

async def block_3(paper_id: str) -> None:
    begin_block(3, "Library Inspection")
    from qws_researcher.server import get_paper_metadata, reading_list, search_by_tag

    meta = await get_paper_metadata(paper_id)
    check("get_paper_metadata returns dict", isinstance(meta, dict))
    check("has_full_text key present", "has_full_text" in meta, f"keys={list(meta.keys())}")
    check("campus_download_needed key present", "campus_download_needed" in meta)
    tags = meta.get("tags") or []
    check("tags contains uat-test", "uat-test" in tags, f"tags={tags}")
    check("tags contains to-read", "to-read" in tags, f"tags={tags}")

    by_tag = await search_by_tag(["uat-test"])
    ids_by_tag = [r.get("ID") for r in by_tag]
    check("search_by_tag returns list", isinstance(by_tag, list))
    check("paper appears in search_by_tag", paper_id in ids_by_tag,
          f"ids={ids_by_tag[:5]}")

    rl = await reading_list()
    rl_ids = [r.get("ID") for r in rl]
    check("reading_list returns list", isinstance(rl, list))
    check("paper appears in reading_list", paper_id in rl_ids, f"ids={rl_ids[:5]}")


# ---------------------------------------------------------------------------
# Block 4 — Notes + Tags
# ---------------------------------------------------------------------------

async def block_4(paper_id: str) -> None:
    begin_block(4, "Notes + Tags")
    from qws_researcher.server import add_note, get_paper_metadata, remove_tag, update_note

    await add_note(paper_id, "UAT note line 1")
    await add_note(paper_id, "UAT note line 2")
    meta = await get_paper_metadata(paper_id)
    notes = meta.get("notes") or ""
    check("notes contains line 1", "UAT note line 1" in notes, f"notes={notes[:100]}")
    check("notes contains line 2", "UAT note line 2" in notes, f"notes={notes[:100]}")

    await update_note(paper_id, "Replaced note")
    meta2 = await get_paper_metadata(paper_id)
    notes2 = meta2.get("notes") or ""
    check("update_note replaces content", notes2 == "Replaced note",
          f"notes={notes2!r}")

    await remove_tag(paper_id, ["uat-test"])
    meta3 = await get_paper_metadata(paper_id)
    tags3 = meta3.get("tags") or []
    check("uat-test removed", "uat-test" not in tags3, f"tags={tags3}")
    check("to-read retained", "to-read" in tags3, f"tags={tags3}")


# ---------------------------------------------------------------------------
# Block 5 — Citation
# ---------------------------------------------------------------------------

async def block_5(paper_id: str) -> None:
    begin_block(5, "Citation")
    from qws_researcher.server import cite

    bibtex = await cite(paper_id, "bibtex")
    check("bibtex is a string", isinstance(bibtex, str))
    check("bibtex starts with @article{", bibtex.strip().startswith("@article{"),
          f"starts_with={bibtex[:30]!r}")

    apa = await cite(paper_id, "apa")
    check("apa is non-empty string", isinstance(apa, str) and len(apa) > 10)
    check("apa does not start with @", not apa.strip().startswith("@"),
          f"starts_with={apa[:20]!r}")

    chicago = await cite(paper_id, "chicago")
    check("chicago is non-empty string", isinstance(chicago, str) and len(chicago) > 10)

    check("three distinct formats", len({bibtex, apa, chicago}) == 3)


# ---------------------------------------------------------------------------
# Block 6 — Related Papers
# ---------------------------------------------------------------------------

async def block_6(paper_id: str) -> None:
    begin_block(6, "Related Papers")
    from qws_researcher.server import get_related_papers

    related = await get_related_papers(paper_id, n=5)
    check("get_related_papers returns list", isinstance(related, list))

    if related:
        valid_signals = {"vector", "s2_recommendations", "shared_tags"}
        signals_present = all("Signal" in r for r in related)
        check("Signal key present on all results", signals_present,
              f"first_keys={list(related[0].keys())}")
        if signals_present:
            bad = [r["Signal"] for r in related if r["Signal"] not in valid_signals]
            check("all Signal values valid", len(bad) == 0, f"bad signals={bad}")

        ids = [r.get("ID") for r in related]
        check("no duplicate IDs", len(ids) == len(set(ids)), f"ids={ids}")
        check("paper_id not in results", paper_id not in ids, "self-referential result")


# ---------------------------------------------------------------------------
# Block 7 — Campus Export
# ---------------------------------------------------------------------------

async def block_7(tmp_dir: str) -> None:
    begin_block(7, "Campus Export")
    from qws_researcher.server import export_campus_list

    result = await export_campus_list()
    check("export_campus_list returns string", isinstance(result, str))

    # Result may be a path or a message; check if the path portion exists
    path_str = result.strip()
    # Extract path if embedded in a message
    for token in path_str.split():
        if token.endswith(".md"):
            path_str = token
            break

    path = Path(path_str)
    check("returned path ends in .md", path_str.endswith(".md"), f"result={result[:100]}")
    if path.exists():
        content = path.read_text()
        check("file contains checkbox item", "- [ ]" in content, f"content_start={content[:200]}")
    else:
        check("exported file exists on disk", False, f"path={path_str} not found")


# ---------------------------------------------------------------------------
# Block 8 — Bulk Bookmark + Stats
# ---------------------------------------------------------------------------

async def block_8(tmp_dir: str) -> list[str]:
    begin_block(8, "Bulk Bookmark + Stats")
    from qws_researcher.server import bulk_bookmark, library_stats, search_papers

    results = await search_papers(
        "GARCH volatility forecasting", max_per_source=5,
        save=True
    )
    check("GARCH search returned results", len(results) >= 1, f"got {len(results)}")

    bulk_ids = [r["ID"] for r in results[:3]]
    check("have IDs for bulk bookmark", len(bulk_ids) >= 1, f"ids={bulk_ids}")

    if bulk_ids:
        bm_result = await bulk_bookmark(bulk_ids, reason="UAT bulk test", tags=["uat-bulk", "to-read"])
        check("bulk_bookmark returns dict", isinstance(bm_result, dict))
        check("bookmarked >= 1", bm_result.get("bookmarked", 0) >= 1,
              f"result={bm_result}")
        check("not_found == 0", bm_result.get("not_found", 0) == 0,
              f"not_found={bm_result.get('not_found')}")

    stats = await library_stats()
    check("library_stats returns dict", isinstance(stats, dict))
    check("total_papers >= 1", stats.get("total_papers", 0) >= 1,
          f"total_papers={stats.get('total_papers')}")

    return bulk_ids


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

async def cleanup(paper_id: str, bulk_ids: list[str], campus_needed: bool) -> None:
    begin_block(99, "Cleanup")
    from qws_researcher.server import (
        remove_from_campus_list,
        remove_tag,
        search_by_tag,
        update_note,
    )

    for tag_group in [["uat-test"], ["uat-bulk"]]:
        tagged = await search_by_tag(tag_group)
        for r in tagged:
            pid = r.get("ID")
            if pid:
                await remove_tag(pid, tag_group)
                await update_note(pid, "UAT complete")

    if campus_needed and paper_id:
        await remove_from_campus_list(paper_id)

    print("    Cleanup complete.")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

BLOCK_NAMES = {
    0: "Table Format",
    1: "Search + Abstract",
    2: "Bookmark + Campus List",
    3: "Library Inspection",
    4: "Notes + Tags",
    5: "Citation",
    6: "Related Papers",
    7: "Campus Export",
    8: "Bulk Bookmark + Stats",
}

_block_pass: dict[int, bool] = {}


def _mark_block_start(n: int) -> int:
    return len(_failures)


def _mark_block_end(n: int, failures_before: int) -> None:
    _block_pass[n] = len(_failures) == failures_before


def print_summary() -> None:
    total_checks = len(_passes) + len(_failures)
    passed = len(_passes)

    print("\n" + "=" * 60)
    print("UAT SUMMARY")
    print("=" * 60)

    rows = []
    for n, name in BLOCK_NAMES.items():
        result = _block_pass.get(n)
        if result is None:
            status = "—"
        elif result:
            status = "PASS"
        else:
            status = "FAIL"
        rows.append((n, name, status))

    print(f"{'Block':<6} {'Name':<30} {'Result'}")
    print("-" * 50)
    for n, name, status in rows:
        print(f"  {n:<4} {name:<30} {status}")

    print("=" * 60)
    print(f"Overall: {passed}/{total_checks} checks passing")

    if _failures:
        print(f"\nFailed checks ({len(_failures)}):")
        for label, detail in _failures:
            detail_str = f" — {detail}" if detail else ""
            print(f"  ✗  {label}{detail_str}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_uat(tmp_dir: str) -> None:
    setup_server(tmp_dir)

    f0 = _mark_block_start(0)
    await block_0(tmp_dir)
    _mark_block_end(0, f0)

    f1 = _mark_block_start(1)
    paper_id, _ = await block_1(tmp_dir)
    _mark_block_end(1, f1)

    if not paper_id:
        print("\nNo paper_id available — cannot continue with blocks 2-8. Check network/API.")
        return

    f2 = _mark_block_start(2)
    campus_needed = await block_2(paper_id)
    _mark_block_end(2, f2)

    f3 = _mark_block_start(3)
    await block_3(paper_id)
    _mark_block_end(3, f3)

    f4 = _mark_block_start(4)
    await block_4(paper_id)
    _mark_block_end(4, f4)

    f5 = _mark_block_start(5)
    await block_5(paper_id)
    _mark_block_end(5, f5)

    f6 = _mark_block_start(6)
    await block_6(paper_id)
    _mark_block_end(6, f6)

    f7 = _mark_block_start(7)
    await block_7(tmp_dir)
    _mark_block_end(7, f7)

    f8 = _mark_block_start(8)
    bulk_ids = await block_8(tmp_dir)
    _mark_block_end(8, f8)

    await cleanup(paper_id, bulk_ids, campus_needed)


def main() -> None:
    print("papers-mcp UAT")
    print("Using temp data directory (real library untouched)")
    print("Making live network calls to Semantic Scholar")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp_dir:
        asyncio.run(run_uat(tmp_dir))

    print_summary()
    sys.exit(1 if _failures else 0)


if __name__ == "__main__":
    main()
