from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class CorruptionConfig:
    expected_seconds: Optional[float] = None
    tolerance_seconds: float = 0.5


def cadence_flags(aligned: pd.DataFrame, cfg: CorruptionConfig) -> pd.DataFrame:
    if aligned.empty:
        return pd.DataFrame(columns=["token_id", "ts_utc", "reason"])

    df = aligned[["token_id", "ts_utc"]].copy()
    df = df.sort_values(["token_id", "ts_utc"])
    df["prev_ts"] = df.groupby("token_id")["ts_utc"].shift(1)
    df["delta_s"] = (df["ts_utc"] - df["prev_ts"]).dt.total_seconds()

    bad = []
    m0 = df["delta_s"].notna() & (df["delta_s"] <= 0)
    for _, r in df[m0].iterrows():
        bad.append({"token_id": r["token_id"], "ts_utc": r["ts_utc"], "reason": "non_positive_delta"})

    if cfg.expected_seconds and cfg.expected_seconds > 0:
        m1 = df["delta_s"].notna() & (df["delta_s"] > 0) & ((df["delta_s"] - cfg.expected_seconds).abs() > cfg.tolerance_seconds)
        for _, r in df[m1].iterrows():
            bad.append({"token_id": r["token_id"], "ts_utc": r["ts_utc"], "reason": f"off_grid_delta:{r['delta_s']:.3f}s"})

    return pd.DataFrame(bad, columns=["token_id", "ts_utc", "reason"])