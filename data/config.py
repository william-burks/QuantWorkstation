from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Alpaca
    alpaca_api_key: str
    alpaca_api_secret: str
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # IBKR
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 4002  # 4002=paper, 4001=live
    ibkr_client_id: int = 1

    # arcticdb — override with ARCTIC_URI env var; store.py sets a local default if unset
    arctic_uri: str = ""

    # UNUSED — reserved for execution state layer (signals relay, position cache)
    redis_url: str = "redis://redis:6379/0"

    # Crypto symbols to collect
    crypto_symbols: list[str] = ["BTC/USD"]

    # Futures root symbols to collect
    futures_symbols: list[str] = [
        "MES",
        "MNQ",
        "MGC",
        "CL",
        "ES",
        "NQ",
        "GC",
        "RTY",
        "M2K",
        "ZN",
        "ZB",
        "6E",
        "6J",
        "6B",
        "NG",
        "SI",
        "ZC",
        "ZS",
        "MBT",
        "DX",
        "VX",
        "NKD",
        "FDAX",
        "Z",
    ]

    # Cash index symbols to collect (secType=IND, daily/weekly/monthly only)
    index_symbols: list[str] = ["VIX", "VIX9D", "VIX3M", "VIX6M", "SKEW"]

    # COT symbols to collect (must be keys in CFTC_SYMBOL_MAP in data/collectors/cot.py)
    cot_symbols: list[str] = ["GC", "MGC", "CL", "ES", "NQ", "ZN", "ZB", "6E"]

    # FRED macro series to collect (see data/collectors/fred.py)
    fred_api_key: str = ""
    fred_series: list[str] = [
        # Yield curve
        "DGS2",
        "DGS10",
        "T10Y2Y",
        # Vol / credit
        "VIXCLS",
        "BAMLH0A0HYM2",
        # Inflation expectations
        "T5YIE",       # 5-year breakeven inflation
        "T10YIE",      # 10-year breakeven inflation
        "DFII10",      # 10-year TIPS real yield
        "PCEPILFE",    # Core PCE (Fed's preferred inflation measure)
        # Labor / activity
        "ICSA",        # Initial jobless claims (weekly)
        "RSAFS",       # Retail sales (monthly)
        # Financial stress
        "STLFSI4",     # St. Louis Fed Financial Stress Index
    ]

    # EIA petroleum stock series to collect (see data/collectors/eia.py)
    # API key loaded from EIA_API_KEY env var (free at https://www.eia.gov/opendata/)
    eia_api_key: str = ""
    eia_series: list[str] = [
        "WCRSTUS1",
        "WCSSTUS1",
        "WGTSTUS1",
        "WDISTUS1",
    ]

    eia_mer_series: list[str] = [
        "ZWHDPUS",  # US Heating Degree Days (monthly, population-weighted, 1973-present)
        "ZWCDPUS",  # US Cooling Degree Days (monthly, population-weighted, 1973-present)
    ]

    # Financial Modeling Prep API key — free at https://financialmodelingprep.com/developer/docs
    # Loaded from FMP_API_KEY env var
    fmp_api_key: str = ""

    # USDA NASS Quick Stats API key — free from https://quickstats.nass.usda.gov/api
    # Loaded from USDA_API_KEY env var; stored as export in ~/.zshrc per security rules
    usda_api_key: str = ""

    # Google Trends search terms to collect (see data/collectors/google_trends.py)
    gtrends_terms: list[str] = [
        "buy gold",
        "gold inflation hedge",
        "recession",
        "inflation",
    ]

    # Risk / evaluation
    eval_profit_target: float = 3000.0  # evaluation profit goal (USD)
    risk_per_trade_pct: float = 0.01  # 1% of balance per trade (range: 0.005–0.01)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
