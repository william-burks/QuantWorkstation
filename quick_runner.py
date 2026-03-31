from data.collectors.alpaca_crypto import collect, collect_all
from data.collectors.ibkr_futures import collect_all_timeframes
from data.store import get_store


# All configured symbols (ETH/USD)
# collect("ETH/USD","1T")
# collect("ETH/USD","5T")
# collect("ETH/USD","15T")
# collect("ETH/USD","1H")
# collect("ETH/USD","4H")
# collect("ETH/USD","1D")
# collect("ETH/USD","1W")

# collect_all_timeframes()

store = get_store()
for sym in store.list_symbols("futures"):
    df = store.read_bars("futures", sym)
    print(f"{sym}: {len(df)} bars | {df.index.min()} → {df.index.max()}")

