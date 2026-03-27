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

    # arcticdb
    arctic_uri: str = "lmdb:///data/arctic"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Crypto symbols to collect
    crypto_symbols: list[str] = ["BTC/USD", "ETH/USD", "SOL/USD"]

    # Futures root symbols to collect
    futures_symbols: list[str] = ["ES", "NQ", "CL", "GC"]


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
