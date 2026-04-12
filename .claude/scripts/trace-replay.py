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

EXCLUDED_EXTENSIONS = {".md", ".yaml", ".yml", ".json", ".toml", ".cfg", ".txt"}
EXCLUDED_PREFIXES = ("test_", "conftest")

def is_tracked_file(path: str) -> bool:
    if not path:
        return False
    basename = os.path.basename(path)
    ext = os.path.splitext(basename)[1].lower()
    if ext in EXCLUDED_EXTENSIONS:
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

def sim_bash_grep(command: str) -> tuple[bool, str]:
    """Detect grep commands targeting already-Read .py files."""
    # Match: grep <flags> <pattern> <file>  OR  grep <flags> <file>
    # Heuristic: find .py filename in command that's in read_tracker
    tokens = command.split()
    for token in tokens:
        if token.endswith(".py"):
            name = os.path.basename(token)
            if name in read_tracker:
                return True, f"grep on {name} (already Read)"
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
blocked_bash_greps: list[tuple[int, str, str]] = []
blocked_searches: list[tuple[int, str, str]] = []

read_tracker.clear()
discovery_count = 0

for i, (tool, target) in enumerate(calls, 1):
    if tool == "Read":
        blocked, reason = sim_read(target)
        if blocked:
            blocked_reads.append((i, target, reason))
            if VERBOSE:
                print(f"  [READ BLOCK]   #{i:3d} Read {os.path.basename(target)} — {reason}")

    elif tool == "Bash":
        # Only check if it looks like a grep targeting a .py file already read
        blocked, reason = sim_bash_grep(target)
        if blocked:
            blocked_bash_greps.append((i, target[:80], reason))
            if VERBOSE:
                print(f"  [GREP BLOCK]   #{i:3d} Bash grep — {reason}")

    elif tool == "mcp__codebase-memory-mcp__search_code":
        blocked, reason = sim_search_code()
        if blocked:
            blocked_searches.append((i, target, reason))
            if VERBOSE:
                print(f"  [SRCH BLOCK]   #{i:3d} search_code '{target[:40]}' — {reason}")

# --- Summary ---
total = len(calls)
total_blocked = len(blocked_reads) + len(blocked_bash_greps) + len(blocked_searches)
projected = total - total_blocked

print()
print(f"=== Trace Replay: {os.path.basename(TRACE_FILE)} ===")
print(f"Total tool calls in trace:  {total}")
print()
print(f"Calls guards would BLOCK:")
print(f"  Read re-reads (3rd+):     {len(blocked_reads):3d}  [agent-read-guard, now in settings.json]")
print(f"  Bash grep on Read files:  {len(blocked_bash_greps):3d}  [NOT YET STRUCTURALLY BLOCKED — prose only]")
print(f"  search_code over-cap:     {len(blocked_searches):3d}  [agent-discovery-guard, now in settings.json]")
print(f"  Total would-be blocked:   {total_blocked:3d}")
print()
print(f"Projected effective calls:  {projected}  (if agent doesn't compensate)")

if VERBOSE:
    if blocked_reads:
        print()
        print("Read blocks by file:")
        by_file: dict[str, list[int]] = defaultdict(list)
        for i, path, _ in blocked_reads:
            by_file[os.path.basename(path)].append(i)
        for fname, indices in sorted(by_file.items(), key=lambda x: -len(x[1])):
            print(f"  {fname}: {len(indices)} blocked (calls {indices})")

    if blocked_bash_greps:
        print()
        print("Bash grep blocks (structural gap — needs Bash hook extension):")
        for i, cmd, reason in blocked_bash_greps:
            print(f"  #{i:3d}: {reason}")

print()
print("NOTE: Bash grep on already-read files is NOT blocked structurally.")
print("      To close this gap: extend agent-guard.sh to detect grep on tracked files.")
