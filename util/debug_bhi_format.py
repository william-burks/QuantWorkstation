"""Debug BHI Excel format — print top rows to verify cell positions."""

from io import BytesIO

import pandas as pd
import requests

NA_URL = "https://rigcount.bakerhughes.com/static-files/16a70c3d-0e8c-4ec1-afa4-f7ebd11c3120"
headers = {"User-Agent": "Mozilla/5.0 (compatible; QuantWorkstation/1.0)"}

r = requests.get(NA_URL, headers=headers, timeout=60)
r.raise_for_status()
print(f"Downloaded {len(r.content)} bytes")

df = pd.read_excel(BytesIO(r.content), sheet_name="NAM Summary", engine="openpyxl", header=None)
print(f"Shape: {df.shape}")
print("\n--- Top 8 rows, cols 0-6 ---")
print(df.iloc[:8, :7].to_string())
