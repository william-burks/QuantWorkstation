from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    graph_enabled: bool
    graph_scheme: str
    graph_host: str
    graph_port: int
    graph_user: str
    graph_password: str
    graph_timeout_seconds: int

    @property
    def graph_uri(self) -> str:
        return f"{self.graph_scheme}://{self.graph_host}:{self.graph_port}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        graph_enabled=_as_bool(os.getenv("QW_GRAPH_ENABLED"), True),
        graph_scheme=os.getenv("QW_GRAPH_SCHEME", "bolt"),
        graph_host=os.getenv("QW_GRAPH_HOST", "127.0.0.1"),
        graph_port=_as_int(os.getenv("QW_GRAPH_PORT"), 7687),
        graph_user=os.getenv("QW_GRAPH_USER", "neo4j"),
        graph_password=os.getenv("QW_GRAPH_PASSWORD", "password"),
        graph_timeout_seconds=_as_int(os.getenv("QW_GRAPH_TIMEOUT_SECONDS"), 3),
    )


def load_settings() -> Settings:
    # Alias kept to align with common "load_*" config call sites.
    return get_settings()

