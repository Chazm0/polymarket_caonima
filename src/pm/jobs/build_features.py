from __future__ import annotations

# In this architecture, features are built inline during collection (insert_snapshot_and_features).
# This file exists for future backfills, recomputation, or additional feature sets.

def build_features_backfill(*args, **kwargs) -> None:
    raise NotImplementedError("Backfill job not implemented yet (features are built inline).")