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

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Crypto symbols to collect
    crypto_symbols: list[str] = ["BTC/USD"]

    # Futures root symbols to collect
    futures_symbols: list[str] = ["MES", "MNQ", "CL"]

    # Risk / evaluation
    eval_profit_target: float = 3000.0   # evaluation profit goal (USD)
    risk_per_trade_pct: float = 0.01     # 1% of balance per trade (range: 0.005–0.01)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
