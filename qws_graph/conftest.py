"""Root conftest.py for qws_graph test suite.

Stubs out ``pandas`` before neo4j's optional-deps module imports it.
The conda environment has a numpy/pandas binary incompatibility that causes
``ValueError: numpy.dtype size changed`` when pandas is imported normally.
neo4j 5.x tries to import pandas as an optional dependency; this stub
prevents that import from failing collection of all tests that transitively
import neo4j.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

if "pandas" not in sys.modules:
    sys.modules["pandas"] = MagicMock()
