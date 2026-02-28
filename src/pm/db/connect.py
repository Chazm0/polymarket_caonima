from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


@dataclass
class DB:
    """
    Small DB wrapper around a psycopg connection pool.
    """
    dsn: str
    statement_timeout_ms: int = 60000
    pool: Optional[ConnectionPool] = None

    def open(self) -> "DB":
        if self.pool is not None:
            return self

        # Note: keep pool size modest; Neon can throttle
        self.pool = ConnectionPool(
            conninfo=self.dsn,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
        )

        # Session defaults
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TIME ZONE 'UTC'")
                if self.statement_timeout_ms > 0:
                    # SET doesn't reliably accept bind params; embed validated int
                    timeout = int(self.statement_timeout_ms)
                    cur.execute(f"SET statement_timeout = {timeout}")
            conn.commit()

        return self

    def close(self) -> None:
        if self.pool:
            self.pool.close()
            self.pool = None

    def connection(self):
        if not self.pool:
            raise RuntimeError("DB pool not opened. Call db.open() first.")
        return self.pool.connection()


def _split_sql_statements(sql: str) -> list[str]:
    # Sufficient for typical migration DDL (no complex function bodies).
    parts = []
    buf = []
    in_sq = False
    in_dq = False
    in_lc = False
    in_bc = False
    i = 0
    n = len(sql)

    def flush():
        s = "".join(buf).strip()
        if s:
            parts.append(s)
        buf.clear()

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if in_lc:
            buf.append(ch)
            if ch == "\n":
                in_lc = False
            i += 1
            continue

        if in_bc:
            buf.append(ch)
            if ch == "*" and nxt == "/":
                buf.append(nxt)
                in_bc = False
                i += 2
            else:
                i += 1
            continue

        if in_sq:
            buf.append(ch)
            if ch == "'" and nxt == "'":
                buf.append(nxt)
                i += 2
            elif ch == "'":
                in_sq = False
                i += 1
            else:
                i += 1
            continue

        if in_dq:
            buf.append(ch)
            if ch == '"' and nxt == '"':
                buf.append(nxt)
                i += 2
            elif ch == '"':
                in_dq = False
                i += 1
            else:
                i += 1
            continue

        if ch == "-" and nxt == "-":
            buf.append(ch); buf.append(nxt)
            in_lc = True
            i += 2
            continue

        if ch == "/" and nxt == "*":
            buf.append(ch); buf.append(nxt)
            in_bc = True
            i += 2
            continue

        if ch == "'":
            buf.append(ch)
            in_sq = True
            i += 1
            continue

        if ch == '"':
            buf.append(ch)
            in_dq = True
            i += 1
            continue

        if ch == ";":
            flush()
            i += 1
            continue

        buf.append(ch)
        i += 1

    flush()
    return parts


def run_migrations(db: DB, migrations_dir: str | Path) -> None:
    """
    Apply *.sql migrations in lexical order.
    Uses a migrations table to ensure each file runs once.
    """
    db.open()
    migrations_dir = Path(migrations_dir)

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  filename TEXT PRIMARY KEY,
                  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        conn.commit()

    files = sorted(glob.glob(str(migrations_dir / "*.sql")))
    for fp in files:
        name = os.path.basename(fp)
        sql = Path(fp).read_text(encoding="utf-8")

        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM schema_migrations WHERE filename=%s", (name,))
                if cur.fetchone():
                    continue

                for stmt in _split_sql_statements(sql):
                    cur.execute(stmt)

                cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (name,))
            conn.commit()