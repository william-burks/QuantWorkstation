"""Check NAM Weekly sheet in the current Apr 2026 file."""

from pathlib import Path

import pandas as pd

CURRENT = Path.home() / "Downloads" / "04-10-2026 North_America Rig_Count Report (1).xlsx"

df = pd.read_excel(CURRENT, sheet_name="NAM Weekly", engine="openpyxl", header=10)
print("Total rows:", len(df))
print("Date range:", df["US_PublishDate"].min(), "→", df["US_PublishDate"].max())
print("Country values:", df["Country"].unique())
