#!/bin/bash
set -e
cd "$(dirname "$0")/../mcp/papers-mcp"
.venv/bin/python ~/ClaudeProjects/QuantResearcher/library/ingest.py
