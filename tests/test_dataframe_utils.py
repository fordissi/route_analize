import pandas as pd

from dataframe_utils import ensure_columns, rename_columns_for_unique_selection


def test_rename_columns_for_unique_selection_prevents_series_scalar_lookup() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "nearest_hospital_name": "legacy nearest",
                "nearest_hospital_distance_m": 123.0,
            }
        ]
    )

    result = rename_columns_for_unique_selection(
        dataframe,
        {
            "nearest_hospital_name": "v3_nearest_hospital_name",
            "nearest_hospital_distance_m": "v3_nearest_hospital_distance_m",
        },
    )
    selected = result[["event_uid", "nearest_hospital_name", "v3_nearest_hospital_name"]]
    row = selected.iloc[0]

    assert selected.columns.tolist() == ["event_uid", "nearest_hospital_name", "v3_nearest_hospital_name"]
    assert row["nearest_hospital_name"] == "legacy nearest"
    assert row["v3_nearest_hospital_name"] == "legacy nearest"


def test_ensure_columns_adds_missing_columns_with_defaults() -> None:
    dataframe = pd.DataFrame([{"event_uid": "e1", "risk_score": 3}])

    result = ensure_columns(
        dataframe,
        {
            "event_uid": "",
            "location_class": pd.NA,
            "review_score": 0,
        },
    )

    assert result.columns.tolist() == ["event_uid", "risk_score", "location_class", "review_score"]
    assert pd.isna(result.loc[0, "location_class"])
    assert result.loc[0, "review_score"] == 0
