#!/usr/bin/env python3
"""
Trace replay simulator for lead-engineer audit runs.

Parses a JSONL agent trace (format: {"tool":"Read","target":"<path>","id":"..."})
and simulates guard hook responses to predict how many calls would be blocked.

Usage:
    python .claude/scripts/trace-replay.py <trace.jsonl> [--verbose]
"""
import json
import os
import re
import sys
from collections import defaultdict

VERBOSE = "--verbose" in sys.argv
TRACE_FILE = next((a for a in sys.argv[1:] if not a.startswith("--")), None)

if not TRACE_FILE:
    print("Usage: python trace-replay.py <trace.jsonl> [--verbose]")
    sys.exit(1)

if not os.path.exists(TRACE_FILE):
    print(f"ERROR: trace file not found: {TRACE_FILE}")
    sys.exit(1)

# --- Guard simulation state ---
read_tracker: dict[str, int] = {}
READ_CAP = 2  # block 3rd+ read

discovery_count = 0
DISCOVERY_CAP = 10

EXCLUDED_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".cfg", ".txt"}
EXCLUDED_PREFIXES = ("test_", "conftest")

def is_tracked_file(path: str) -> bool:
    if not path:
        return False
    basename = os.path.basename(path)
    ext = os.path.splitext(basename)[1].lower()
    if ext in EXCLUDED_EXTENSIONS:
        return False
    # Track story_*.md files (re-read guard)
    if basename.endswith(".md") and not basename.startswith("story_"):
        return False
    if any(basename.startswith(p) for p in EXCLUDED_PREFIXES):
        return False
    return True

def sim_read(target: str) -> tuple[bool, str]:
    if not is_tracked_file(target):
        return False, "excluded"
    name = os.path.basename(target)
    count = read_tracker.get(name, 0) + 1
    read_tracker[name] = count
    if count > READ_CAP:
        return True, f"{name} read #{count} (cap={READ_CAP})"
    return False, f"{name} read {count}/{READ_CAP}"

catn_tracker: dict[str, int] = {}

def sim_bash(command: str) -> tuple[bool, str]:
    """Simulate agent-bash-grep-guard.sh checks."""
    # 1. Block ALL bare mypy (file, directory, or piped) — no .py requirement
    if re.search(r'(^|\s|&&\s*|;\s*)mypy\s', command):
        return True, "bare mypy (use make typecheck)"

    # 2. sed/awk/nl on ANY .py/.yaml/.yml/.md file — unconditional block
    if re.search(r'(^|\|)[^|]*(sed|awk|nl)\s', command):
        for segment in command.split("|"):
            if re.search(r'(^|\s)(sed|awk|nl)\s', segment):
                for token in segment.split():
                    if re.search(r'\.(py|yaml|yml|md)$', token):
                        name = os.path.basename(token)
                        return True, f"sed/awk/nl on {name} (unconditional — use Read+offset)"

    # 2a. python3/python inline script — heredoc stdin or /tmp script bypass
    # Catches: python3 - << 'PYEOF', python3 << 'PYEOF', python3 /tmp/script.py, python -
    if re.search(r'python3?\s+(-[^a-zA-Z0-9_]|/tmp/\S+\.py|<<)', command):
        return True, "python3 inline script bypass (use Read/Edit tools directly)"

    # 2b. cp of source files to /tmp/ — unconditional block (snapshot bypass)
    if re.search(r'(^|\s|&&\s*|;\s*)cp\s', command):
        if re.search(r'\.(py|yaml|yml|md)\s.*/tmp/', command):
            return True, "cp source to /tmp/ (snapshot bypass — use Read+offset)"

    # 3. cat -n on .py files — tracked, block 3rd+ access
    if re.search(r'(^|\s)cat\s+-n\s', command):
        for segment in command.split("|"):
            if re.search(r'(^|\s)cat\s+-n\s', segment):
                for token in segment.split():
                    if token.endswith(".py"):
                        name = os.path.basename(token)
                        count = catn_tracker.get(name, 0) + 1
                        catn_tracker[name] = count
                        if count > 2:
                            return True, f"cat -n on {name} (access #{count}, cap=2)"

    # 4. grep/rg/head/tail on tracked .py/.yaml/.yml/.md files
    if re.search(r'(^|\s)(grep|rg|head|tail)\s', command):
        for segment in command.split("|"):
            if re.search(r'(^|\s)(grep|rg|head|tail)\s', segment):
                for token in segment.split():
                    if re.search(r'\.(py|yaml|yml|md)$', token):
                        name = os.path.basename(token)
                        if name in read_tracker:
                            if re.search(r'(^|\s)(grep|rg)\s', segment):
                                return True, f"grep on {name} (already Read)"
                            else:
                                return True, f"head/tail on {name} (already Read)"
    # Fix 10: Block Bash read access to reference-only files
    REFERENCE_FILES = ("data_dictionary.yaml", "graph_v1_contract.md")
    for ref in REFERENCE_FILES:
        if ref in command:
            if re.search(r'(^|\s|\|)(cat|grep|rg|wc|head|tail|less)\s', command):
                return True, f"{ref} Bash read (use Read tool)"
    return False, ""

def sim_search_code() -> tuple[bool, str]:
    global discovery_count
    discovery_count += 1
    if discovery_count > DISCOVERY_CAP:
        return True, f"search_code call #{discovery_count} (cap={DISCOVERY_CAP})"
    return False, f"search_code #{discovery_count}/{DISCOVERY_CAP}"

# --- Parse trace ---
calls: list[tuple[str, str]] = []  # (tool, target)
with open(TRACE_FILE) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        tool = entry.get("tool", "")
        target = entry.get("target", "")
        if tool:
            calls.append((tool, target))

if not calls:
    print(f"ERROR: no tool calls found in {TRACE_FILE}")
    sys.exit(1)

# --- Simulate ---
blocked_reads: list[tuple[int, str, str]] = []
blocked_bash: list[tuple[int, str, str]] = []
blocked_searches: list[tuple[int, str, str]] = []

read_tracker.clear()
catn_tracker.clear()
discovery_count = 0

for i, (tool, target) in enumerate(calls, 1):
    if tool == "Read":
        blocked, reason = sim_read(target)
        if blocked:
            blocked_reads.append((i, target, reason))
            if VERBOSE:
                print(f"  [READ BLOCK]   #{i:3d} Read {os.path.basename(target)} — {reason}")

    elif tool == "Bash":
        blocked, reason = sim_bash(target)
        if blocked:
            blocked_bash.append((i, target[:80], reason))
            if VERBOSE:
                print(f"  [BASH BLOCK]   #{i:3d} Bash — {reason}")

    elif tool == "mcp__codebase-memory-mcp__search_code":
        blocked, reason = sim_search_code()
        if blocked:
            blocked_searches.append((i, target, reason))
            if VERBOSE:
                print(f"  [SRCH BLOCK]   #{i:3d} search_code '{target[:40]}' — {reason}")

# --- Breakdown by sub-category ---
bash_grep   = [(i, t, r) for i, t, r in blocked_bash if "grep" in r or "head/tail" in r]
bash_sed    = [(i, t, r) for i, t, r in blocked_bash if any(x in r for x in ("sed/awk", "awk", " nl "))]
bash_catn   = [(i, t, r) for i, t, r in blocked_bash if "cat -n" in r]
bash_mypy   = [(i, t, r) for i, t, r in blocked_bash if "mypy" in r]
bash_cp     = [(i, t, r) for i, t, r in blocked_bash if "cp source" in r or "snapshot bypass" in r]
bash_py3tmp = [(i, t, r) for i, t, r in blocked_bash if "python3 /tmp" in r or "script bypass" in r]
bash_reffile = [(i, t, r) for i, t, r in blocked_bash if "Bash read (use Read tool)" in r]

# --- Summary ---
total = len(calls)
total_blocked = len(blocked_reads) + len(blocked_bash) + len(blocked_searches)
projected = total - total_blocked

print()
print(f"=== Trace Replay: {os.path.basename(TRACE_FILE)} ===")
print(f"Total tool calls in trace:  {total}")
print()
print("Calls guards would BLOCK:")
print(f"  Read re-reads (3rd+):     {len(blocked_reads):3d}  [agent-read-guard]")
print(f"  Bash grep on Read files:  {len(bash_grep):3d}  [agent-bash-grep-guard — grep/rg/head/tail]")
print(f"  Bash sed/awk/nl (any):    {len(bash_sed):3d}  [agent-bash-grep-guard — unconditional]")
print(f"  Bash cat -n (3rd+):       {len(bash_catn):3d}  [agent-bash-grep-guard — cat-n cap]")
print(f"  Bash bare mypy (any):     {len(bash_mypy):3d}  [agent-bash-grep-guard — mypy block]")
print(f"  Bash cp to /tmp/ (any):   {len(bash_cp):3d}  [agent-bash-grep-guard — snapshot bypass]")
print(f"  Bash python3 /tmp (any):  {len(bash_py3tmp):3d}  [agent-bash-grep-guard — script bypass]")
print(f"  Bash ref-file reads (any):{len(bash_reffile):3d}  [agent-bash-grep-guard — reference file block]")
print(f"  search_code over-cap:     {len(blocked_searches):3d}  [agent-discovery-guard]")
print(f"  Total would-be blocked:   {total_blocked:3d}")
print()
print(f"Projected effective calls:  {projected}  (if agent doesn't compensate)")
waste_pct = round(100 * total_blocked / total) if total else 0
print(f"Projected waste reduction:  {waste_pct}% of calls blocked by guards")

if VERBOSE:
    if blocked_reads:
        print()
        print("Read blocks by file:")
        by_file: dict[str, list[int]] = defaultdict(list)
        for i, path, _ in blocked_reads:
            by_file[os.path.basename(path)].append(i)
        for fname, indices in sorted(by_file.items(), key=lambda x: -len(x[1])):
            print(f"  {fname}: {len(indices)} blocked (calls {indices})")

    if bash_sed:
        print()
        print("Sed/chunk blocks (NEW — file-chunking bypass closed):")
        for i, cmd, reason in bash_sed:
            print(f"  #{i:3d}: {reason}")

    if bash_mypy:
        print()
        print("Individual mypy blocks (NEW — mypy storm closed):")
        for i, cmd, reason in bash_mypy:
            print(f"  #{i:3d}: {reason}")
