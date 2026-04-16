# UAT Script — papers-mcp

End-to-end verification of all major tools. Run in a live Claude Code session with the papers MCP active.
Replace `{paper_id}` with actual IDs as you go.

---

## Block 0 — Standard Table Format

```
search_papers("volatility", max_per_source=3)
```

**Expect:** Table has exactly 9 columns in this order: `#`, `Title`, `Authors`, `Year`, `Citations`, `Source`, `Abstract`, `Full Text`, `ID`

**Fail if:** any column is missing, URL appears in Title column, or `#` column is absent.

---

## Block 1 — Search + Abstract

```
search_papers("realized volatility HAR model", max_per_source=5)
```

**Expect:** Up to 5 papers. Each row has all 9 columns. Note one `paper_id` for subsequent blocks.

```
read_abstract("{paper_id}")
```

**Expect:** `**Title**\nAuthors (Year)\n\n{abstract text}` — abstract only, no PDF download triggered.

---

## Block 2 — Bookmark + Campus List

```
bookmark_paper("{paper_id}", reason="UAT test bookmark", tags=["uat-test", "to-read"])
```

**Expect:** `campus_trip_needed: true/false`. arXiv papers may be false (OA PDF available). S2 paywalled papers will be true.

```
list_needed()
```

**Expect:** Bookmarked paper appears if `campus_trip_needed` was true.

```
campus_list_stats()
```

**Expect:** `total >= 1`, `with_doi_hint` or `without_doi_hint` incremented depending on whether DOI is known.

> After UAT, clean up with `remove_from_campus_list("{paper_id}")` (see Cleanup block).

---

## Block 3 — Library Inspection

```
get_paper_metadata("{paper_id}")
```

**Expect:** Full metadata dict including `has_full_text`, `campus_download_needed`, `doi_filename` (if DOI known), and `tags: ["uat-test", "to-read"]`.

```
search_by_tag(["uat-test"])
```

**Expect:** The bookmarked paper appears. Only papers with that exact tag — no others.

```
reading_list()
```

**Expect:** Papers tagged `to-read` sorted by citations descending. Bookmarked paper should appear.

---

## Block 4 — Notes + Tags

```
add_note("{paper_id}", "UAT note line 1")
add_note("{paper_id}", "UAT note line 2")
get_paper_metadata("{paper_id}")
```

**Expect:** `notes` contains both lines separated by `\n\n`.

```
update_note("{paper_id}", "UAT complete")
get_paper_metadata("{paper_id}")
```

**Expect:** `notes` is exactly `"UAT complete"` — prior content gone.

```
remove_tag("{paper_id}", ["uat-test"])
get_paper_metadata("{paper_id}")
```

**Expect:** `tags` no longer contains `"uat-test"`, still has `"to-read"`.

---

## Block 5 — Citation

```
cite("{paper_id}", "bibtex")
cite("{paper_id}", "apa")
cite("{paper_id}", "chicago")
```

**Expect:** Three distinct formatted strings.
- BibTeX: `@article{id_safe_key, ...}` with paper ID as cite key; DOI field present if known; missing fields noted with `% NOTE:`.
- APA: `Authors (Year). Title. URL`
- Chicago: `Authors. "Title." Year. URL`

---

## Block 6 — Related Papers

```
get_related_papers("{paper_id}", n=5)
```

**Expect:** Up to 5 results. Each row has all 9 standard columns plus a `Signal` column with value `"vector"`, `"s2_recommendations"`, or `"shared_tags"`. No duplicate IDs.

---

## Block 7 — Campus Export

```
export_campus_list()
```

**Expect:** Returns a file path like `.../research/notes/campus-trip-2026-03-28.md`. Open the file — should have a checkbox list organized into "DOI known" (exact inbox filename shown) and "needs manual search" sections.

---

## Block 8 — Bulk Bookmark + Stats

```
search_papers("GARCH volatility forecasting", max_per_source=5, save=False)
```

Note 3 paper IDs from the results, then:

```
bulk_bookmark(["{id1}", "{id2}", "{id3}"], reason="UAT bulk test", tags=["uat-bulk", "to-read"])
```

**Expect:** `bookmarked: 3, not_found: 0`.

```
library_stats()
```

**Expect:** Total paper count reflects all additions this session.

---

## Cleanup

```
search_by_tag(["uat-test"])
```

For each returned paper:
```
remove_tag("{paper_id}", ["uat-test"])
update_note("{paper_id}", "")
```

```
search_by_tag(["uat-bulk"])
```

For each returned paper:
```
remove_tag("{paper_id}", ["uat-bulk"])
update_note("{paper_id}", "")
```

> Note: `search_by_tag` uses AND logic — run the two cleanup queries separately, not as `["uat-test", "uat-bulk"]`.

```
remove_from_campus_list("{paper_id from Block 2}")
```
