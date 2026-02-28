from __future__ import annotations

from datetime import datetime
from typing import Optional

from pm.export.clean_export import CorruptionConfig, ExportParams, export_dataset


def export(
    *,
    dsn: str,
    market_id: Optional[int],
    token_id: Optional[str],
    start_ts: Optional[datetime],
    end_ts: Optional[datetime],
    expected_seconds: Optional[float],
    tolerance_seconds: float,
    top_n_flatten: int,
    out_clean: str,
    out_corrupted: str,
) -> tuple[int, int]:
    params = ExportParams(
        dsn=dsn,
        market_id=market_id,
        token_id=token_id,
        start_ts=start_ts,
        end_ts=end_ts,
        top_n_flatten=top_n_flatten,
        corruption=CorruptionConfig(expected_seconds=expected_seconds, tolerance_seconds=tolerance_seconds),
        out_clean=out_clean,
        out_corrupted=out_corrupted,
    )
    return export_dataset(params)