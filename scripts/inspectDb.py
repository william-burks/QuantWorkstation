from data.store import get_store

store = get_store()
for sym in store.list_symbols("crypto"):
    df = store.read_bars("crypto", sym)
    print(f"{sym}: {len(df)} bars | {df.index.min()} → {df.index.max()}")
