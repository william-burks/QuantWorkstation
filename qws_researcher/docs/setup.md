# Setup

## papers-mcp

### Install

```bash
cd ~/ClaudeProjects/QuantResearcher/mcp/papers-mcp
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### Environment Variables

| Variable | Required | Value |
|----------|----------|-------|
| `UNPAYWALL_EMAIL` | Yes (for Unpaywall) | `burks.113@buckeyemail.osu.edu` |
| `SEMANTIC_SCHOLAR_API_KEY` | No (higher rate limits) | Get from semanticscholar.org |
| `RESEARCH_DATA_DIR` | No (defaults to `~/ClaudeProjects/QuantResearcher/core/data`) | Shared data path used by papers, experiment, and search MCPs. `PAPERS_DATA_DIR` is kept as a legacy fallback alias only. |

### MCP Config (Claude Code)

Add via:
```bash
claude mcp add papers --command /path/to/.venv/bin/papers-server \
  --env UNPAYWALL_EMAIL=burks.113@buckeyemail.osu.edu
```

Or manually in `~/.claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "papers": {
      "command": "/Users/will/ClaudeProjects/QuantResearcher/mcp/papers-mcp/.venv/bin/papers-server",
      "env": {
        "UNPAYWALL_EMAIL": "burks.113@buckeyemail.osu.edu"
      }
    }
  }
}
```

## quant-sandbox-mcp

### Build Docker Image

```bash
cd ~/ClaudeProjects/QuantResearcher/mcp/quant-sandbox-mcp
docker build -t quant-sandbox:latest .
```

### Data Volume

Parquet data exported by QuantWorkstation ArcticDB pipeline lives at `~/quant-research/data/`.
Mounted read-only at `/workspace/data/` inside the sandbox.

### MCP Config

```bash
claude mcp add quant-sandbox --command /path/to/.venv/bin/quant-sandbox-server
```

## experiment-mcp

### Install

```bash
cd ~/ClaudeProjects/QuantResearcher/mcp/experiment-mcp
uv sync
```

### Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| `RESEARCH_DATA_DIR` | No | `~/ClaudeProjects/QuantResearcher/core/data` |

### MCP Config (Claude Code)

```bash
claude mcp add experiment -- uv run --directory ~/ClaudeProjects/QuantResearcher/mcp/experiment-mcp experiment-server
```

Shares the same SQLite + ChromaDB store as papers-mcp via `RESEARCH_DATA_DIR`.

## search-mcp

### Install

```bash
cd ~/ClaudeProjects/QuantResearcher/mcp/search-mcp
uv sync
```

### MCP Config (Claude Code)

```bash
claude mcp add search -- uv run --directory ~/ClaudeProjects/QuantResearcher/mcp/search-mcp search-server stdio
```

Shares the same SQLite + ChromaDB store as papers-mcp and experiment-mcp.

## Jobs

### nougat Weekly Upgrade

Install the launchd agent (runs every Sunday at 2:00 AM):

```bash
cp ~/ClaudeProjects/QuantResearcher/jobs/com.quantresearcher.nougat.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.quantresearcher.nougat.plist
```

See `jobs/README.md` for manual triggering and unload instructions.
