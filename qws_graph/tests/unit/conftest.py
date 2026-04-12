"""conftest.py for qws_graph unit tests.

Inserts QWS_GRAPH_ROOT onto sys.path so that ``research.graph.*`` imports
resolve without sys.path manipulation in individual test files.
"""

from __future__ import annotations

import sys
from pathlib import Path

_QWS_GRAPH_ROOT = str(Path(__file__).resolve().parents[2])
if _QWS_GRAPH_ROOT not in sys.path:
    sys.path.insert(0, _QWS_GRAPH_ROOT)
