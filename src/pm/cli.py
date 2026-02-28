from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pm.config import load_settings
from pm.db import DB, run_migrations
from pm.gamma.client import GammaClient
from pm.clob.client import ClobClient

from pm.jobs.ingest_markets import ingest_markets
from pm.jobs.track_markets import track_markets, refresh_ended_flags, auto_track_markets, AutoTrackPolicy
from pm.jobs.collect_orderbooks import collect_orderbooks_loop
from pm.jobs.export_dataset import export as export_job


def _parse_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pm", description="Polymarket Postgres-first pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("migrate", help="Apply SQL migrations")
    m.add_argument("--dir", default=str(Path(__file__).parent / "db" / "migrations"))

    ing = sub.add_parser("ingest-markets", help="Ingest markets from Gamma into Postgres")
    ing.add_argument("--event-id", type=int, default=None)
    ing.add_argument("--limit", type=int, default=1000)
    ing.add_argument("--pages", type=int, default=1)

    tr = sub.add_parser("track-markets", help="Add markets to tracked_markets (by id list)")
    tr.add_argument("--session", required=True)
    tr.add_argument("--market-ids", required=True, help="Comma-separated list of market ids, e.g. 123,456")

    rf = sub.add_parser("refresh-ended", help="Update tracked_markets.ended based on markets table")
    # no args

    col = sub.add_parser("collect-orderbooks", help="Collect orderbooks for tracked markets and build features inline")
    col.add_argument("--batch", type=int, default=None)
    col.add_argument("--top-n", type=int, default=None)
    col.add_argument("--loop-seconds", type=float, default=None)
    col.add_argument("--per-batch-sleep", type=float, default=0.1)
    col.add_argument("--iterations", type=int, default=0)

    ex = sub.add_parser("export", help="Export clean dataset + corrupted rows")
    ex.add_argument("--market-id", type=int, default=None)
    ex.add_argument("--token-id", type=str, default=None)
    ex.add_argument("--start", type=str, default=None)
    ex.add_argument("--end", type=str, default=None)
    ex.add_argument("--expected-seconds", type=float, default=None)
    ex.add_argument("--tolerance-seconds", type=float, default=0.5)
    ex.add_argument("--top-n-flatten", type=int, default=10)
    ex.add_argument("--out-clean", type=str, default="clean_orderbook_dataset.csv")
    ex.add_argument("--out-corrupted", type=str, default="flagged_corrupted_rows.csv")

    at = sub.add_parser("auto-track", help="Auto-select markets from markets table and add to tracked_markets")
    at.add_argument("--session", required=True, help="Tag to store in tracked_markets.sessions[]")
    at.add_argument("--top", type=int, default=200)
    at.add_argument("--min-liquidity", type=float, default=None)
    at.add_argument("--min-volume", type=float, default=None)
    at.add_argument("--ends-within-hours", type=float, default=None)
    at.add_argument("--category", type=str, default=None)
    at.add_argument("--include-closed", action="store_true")
    at.add_argument("--include-already-tracked", action="store_true")
    at.add_argument("--allow-missing-token-keys", action="store_true")
    at.add_argument("--dry-run", action="store_true")

    return p


def main() -> None:
    settings = load_settings()
    args = build_parser().parse_args()

    db = DB(settings.database_dsn, statement_timeout_ms=settings.statement_timeout_ms).open()

    try:
        if args.cmd == "migrate":
            run_migrations(db, args.dir)
            print("[migrate] done")
            return
        
        if args.cmd == "auto-track":
            policy = AutoTrackPolicy(
                session=args.session,
                top_n=args.top,
                min_liquidity=args.min_liquidity,
                min_volume=args.min_volume,
                ends_within_hours=args.ends_within_hours,
                category=args.category,
                include_closed=bool(args.include_closed),
                include_already_tracked=bool(args.include_already_tracked),
                require_token_keys=not bool(args.allow_missing_token_keys),
            )

            n, mids = auto_track_markets(db=db, policy=policy, dry_run=bool(args.dry_run))

            if args.dry_run:
                print(f"[auto-track:dry-run] would_track={len(mids)} session={policy.session}")
            else:
                print(f"[auto-track] tracked={n} session={policy.session}")

            print("sample_market_ids:", ",".join(str(x) for x in mids[:25]))
            return

        # Ensure migrations applied for normal operation
        migrations_dir = Path(__file__).parent / "db" / "migrations"
        run_migrations(db, migrations_dir)

        gamma = GammaClient(settings.gamma_base, user_agent=settings.user_agent)
        clob = ClobClient(settings.clob_base, user_agent=settings.user_agent)

        if args.cmd == "ingest-markets":
            n = ingest_markets(db=db, gamma=gamma, event_id=args.event_id, limit=args.limit, pages=args.pages)
            print(f"[ingest-markets] upserted={n}")
            return

        if args.cmd == "track-markets":
            market_ids = [int(x.strip()) for x in args.market_ids.split(",") if x.strip()]
            n = track_markets(db=db, market_ids=market_ids, session=args.session)
            print(f"[track-markets] tracked={n}")
            return

        if args.cmd == "refresh-ended":
            n = refresh_ended_flags(db)
            print(f"[refresh-ended] updated={n}")
            return

        if args.cmd == "collect-orderbooks":
            batch = args.batch if args.batch is not None else settings.default_batch_size
            top_n = args.top_n if args.top_n is not None else settings.default_top_n
            loop_seconds = args.loop_seconds if args.loop_seconds is not None else settings.default_loop_seconds

            collect_orderbooks_loop(
                db=db,
                clob=clob,
                batch_size=batch,
                top_n=top_n,
                loop_seconds=loop_seconds,
                per_batch_sleep=args.per_batch_sleep,
                iterations=args.iterations,
            )
            return

        if args.cmd == "export":
            start_ts = _parse_ts(args.start)
            end_ts = _parse_ts(args.end)

            clean_n, bad_n = export_job(
                dsn=settings.database_dsn,
                market_id=args.market_id,
                token_id=args.token_id,
                start_ts=start_ts,
                end_ts=end_ts,
                expected_seconds=args.expected_seconds,
                tolerance_seconds=args.tolerance_seconds,
                top_n_flatten=args.top_n_flatten,
                out_clean=args.out_clean,
                out_corrupted=args.out_corrupted,
            )
            print(f"[export] clean_rows={clean_n} corrupted_rows={bad_n}")
            return

        raise SystemExit(f"Unknown command: {args.cmd}")

    finally:
        db.close()