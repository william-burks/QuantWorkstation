"""
Seed BDTI historical data from Investing.com CSV export.

Download from investing.com → "Baltic Dirty Tanker Index" → Historical Data → Daily.
Set date range to max before downloading.

Run once:
  python util/seed_bdti_history.py

File expected in ~/Downloads/:
  Baltic Dirty Tanker Historical Data Daily.csv
"""

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.store import get_store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DOWNLOADS = Path.home() / "Downloads"
CSV_PATH = DOWNLOADS / "Baltic Dirty Tanker Historical Data Daily.csv"
ARC_KEY = "BDTI_1D"


def seed_bdti(path: Path) -> None:
    log.info("Reading %s", path.name)
    df = pd.read_csv(path, thousands=",")
    df["date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", utc=True)
    df = df.set_index("date")[["Price"]].rename(columns={"Price": "value"})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).sort_index()
    log.info("Parsed %d rows: %s → %s", len(df), df.index.min().date(), df.index.max().date())

    store = get_store()
    store.write_series("macro", ARC_KEY, df)
    log.info("Wrote %d rows to macro/%s", len(df), ARC_KEY)


if __name__ == "__main__":
    if not CSV_PATH.exists():
        log.error("File not found: %s", CSV_PATH)
        sys.exit(1)
    seed_bdti(CSV_PATH)
    log.info("BDTI seeding complete")
