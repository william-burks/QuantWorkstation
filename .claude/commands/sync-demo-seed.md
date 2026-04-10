Sync demo seed nodes in cypher.py for QuantWorkstation story: $ARGUMENTS

Invoke skill: caveman

## Step 1 — Locate story
Find story file in `qws_graph/epics/` containing ID `$ARGUMENTS`. Read full file.
Note every node type and property modified or introduced by this story.

## Step 2 — Read demo seed
Read `qws_graph/research/graph/cypher.py` — focus on `DEMO_SEED_CYPHER` and `DEMO_TEARDOWN_CYPHER`.

## Step 3 — Sync MERGE blocks
For every node type modified or extended by this story:
1. Find matching MERGE block(s) in `DEMO_SEED_CYPHER`
2. Check every new property is present in the `SET` block
3. If missing — add with realistic demo value consistent with node's role
   (demo-strategy-alpha = "active institutional" case — values should reflect that)
4. If story introduced new node type — add new MERGE block following existing pattern
   (`is_demo=true`, deterministic IDs like `'demo-...'`, realistic values)
5. If story removed or renamed a property — remove/rename in every affected MERGE block

Apply same audit to `DEMO_TEARDOWN_CYPHER` — ensure any new nodes have corresponding DELETE.

## Step 4 — Verify syntax
Read back edited `cypher.py`. Check for mismatched brackets, missing commas, unclosed strings.

## Step 5 — Stage
```
git add qws_graph/research/graph/cypher.py
```

## Step 6 — Report
```
## $ARGUMENTS — Demo Seed Sync Report

### MERGE blocks touched
- <node type> (<block id>): <properties added/changed/removed>

### New MERGE blocks added
- <node type>: <what it seeds>

### TEARDOWN changes
- <node type>: <what changed>

### No changes needed
- <node types checked with no issues>
```
