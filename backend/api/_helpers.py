"""Shared serialization helpers for the API routers.

The data modules return pandas frames, ``Path`` objects, numpy scalars, and
``datetime``/``Timestamp`` values that are not JSON-serializable out of the box.
These helpers coerce everything to plain JSON-safe primitives.
"""
from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from typing import Any

import pandas as pd


def df_records(df: "pd.DataFrame | None") -> list[dict]:
    """JSON-safe records from a DataFrame (NaN/NaT -> null, dates -> ISO 8601).

    Routes through ``DataFrame.to_json`` which already handles NaN, numpy types
    and timestamps, then back through ``json.loads`` to native Python objects.
    """
    if df is None or getattr(df, "empty", True):
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def clean(value: Any) -> Any:
    """Coerce a single scalar to a JSON-safe primitive (None for NaN/NaT)."""
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, Path):
        return str(value)
    try:
        # pd.isna raises on array-likes; scalars only here.
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    # Normalize numpy numeric scalars to Python floats/ints.
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except Exception:  # noqa: BLE001
            return value
    return value


def clean_dict(d: dict) -> dict:
    """Apply :func:`clean` to every value of a dict."""
    return {k: clean(v) for k, v in d.items()}
