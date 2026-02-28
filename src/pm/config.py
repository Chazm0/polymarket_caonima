from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_dsn: str
    gamma_base: str
    clob_base: str

    default_batch_size: int
    default_top_n: int
    default_loop_seconds: float
    statement_timeout_ms: int

    user_agent: str


def load_settings() -> Settings:
    # Load .env if present (safe even if missing)
    load_dotenv()

    dsn = os.getenv("DATABASE_DSN_PG", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_DSN_PG is required (set in .env or environment).")

    gamma_base = os.getenv("GAMMA_BASE", "https://gamma-api.polymarket.com").strip()
    clob_base = os.getenv("CLOB_BASE", "https://clob.polymarket.com").strip()

    def _int(name: str, default: int) -> int:
        v = os.getenv(name, str(default)).strip()
        try:
            return int(v)
        except Exception:
            return default

    def _float(name: str, default: float) -> float:
        v = os.getenv(name, str(default)).strip()
        try:
            return float(v)
        except Exception:
            return default

    return Settings(
        database_dsn=dsn,
        gamma_base=gamma_base,
        clob_base=clob_base,
        default_batch_size=max(1, _int("DEFAULT_BATCH_SIZE", 50)),
        default_top_n=max(0, _int("DEFAULT_TOP_N", 10)),
        default_loop_seconds=max(0.0, _float("DEFAULT_LOOP_SECONDS", 2.0)),
        statement_timeout_ms=max(0, _int("DEFAULT_STATEMENT_TIMEOUT_MS", 60000)),
        user_agent=os.getenv("PM_USER_AGENT", "polymarket-pipeline/0.1.0").strip(),
    )