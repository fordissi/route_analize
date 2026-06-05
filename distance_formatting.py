from __future__ import annotations

from typing import Any

import pandas as pd


def format_distance(value: Any, *, unknown: str = "未知距離") -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return unknown
    distance_m = float(numeric)
    if abs(distance_m) < 1000:
        return f"{distance_m:.0f}公尺"
    distance_km = distance_m / 1000
    text = f"{distance_km:.1f}".rstrip("0").rstrip(".")
    return f"{text}公里"
