"""Quick inventory of futures library — 1H bars per symbol."""
from data.store import get_store

SYMBOLS = ["ES", "CL", "GC", "ZN", "NQ", "RTY", "6E", "NG", "ZB", "SI", "HG", "6J", "6B"]

store = get_store()
print(f"{'Symbol':<8} {'Bars':>7}  {'Start':<12}  {'End':<12}  Source")
print("-" * 60)
for sym in SYMBOLS:
    key = f"{sym}_1H"
    try:
        df = store.read_bars("futures", key)
        src = df["source"].unique().tolist() if "source" in df.columns else ["?"]
        print(f"{sym:<8} {len(df):>7}  {str(df.index.min().date()):<12}  {str(df.index.max().date()):<12}  {src}")
    except Exception as e:
        print(f"{sym:<8}  ERROR: {e}")
