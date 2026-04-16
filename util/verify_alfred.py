"""Verify ALFRED release dates look correct."""
from data.store import get_store

store = get_store()
df = store.read_series("macro", "CPIAUCSL_release_1D")
print("CPIAUCSL — first 6 rows (index=release_date, obs_date=period covered)")
print(df.head(6).to_string())
print()
print("PAYEMS — first 6 rows")
df2 = store.read_series("macro", "PAYEMS_release_1D")
print(df2.head(6).to_string())
