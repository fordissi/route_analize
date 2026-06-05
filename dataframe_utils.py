from __future__ import annotations

import pandas as pd


def rename_columns_for_unique_selection(dataframe: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    result = dataframe.copy()
    for source, alias in aliases.items():
        if source in result.columns and alias not in result.columns:
            result[alias] = result[source]
    return result


def ensure_columns(dataframe: pd.DataFrame, defaults: dict[str, object]) -> pd.DataFrame:
    result = dataframe.copy()
    for column, default in defaults.items():
        if column not in result.columns:
            result[column] = default
    return result
