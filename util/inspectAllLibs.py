from data.store import get_store

store = get_store()
for lib in ["crypto", "futures", "futures_meta", "macro", "cot", "bdti", "calendar", "signals"]:
    syms = list(store._get_lib(lib).list_symbols())
    if not syms:
        print(f"{lib}: (empty)")
        continue
    print(f"\n{lib}: {len(syms)} symbols")
    for sym in sorted(syms):
        try:
            df = store.read_series(lib, sym)
            print(f"  {sym}: {len(df)} rows | {df.index.min().date()} → {df.index.max().date()}")
        except Exception:
            try:
                df = store.read_bars(lib, sym)
                print(f"  {sym}: {len(df)} bars | {df.index.min()} → {df.index.max()}")
            except Exception as e:
                print(f"  {sym}: error reading ({e})")
