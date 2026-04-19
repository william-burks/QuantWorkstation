"""One-shot: extend BHI state rig count series from NAM Weekly sheet (2024→2026)."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from util.seed_bhi_history import seed_state_from_nam_weekly  # noqa: E402

xlsx = Path.home() / "Downloads" / "04-10-2026 North_America Rig_Count Report (2).xlsx"
seed_state_from_nam_weekly(xlsx)
