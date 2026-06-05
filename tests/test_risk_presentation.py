import pandas as pd

from risk_presentation import add_event_risk_drilldown_columns


def test_event_risk_drilldown_handles_pd_na_v3_fields() -> None:
    events = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "location_class": pd.NA,
                "home_distance_bucket": pd.NA,
                "selected_visit_name": pd.NA,
                "selected_visit_type": pd.NA,
                "existing_client_candidates_top3": pd.NA,
                "suggested_prospects_top3": pd.NA,
                "nearest_existing_client_name": pd.NA,
                "nearest_hospital_name": pd.NA,
                "risk_reason_codes": pd.NA,
                "risk_reason_text": pd.NA,
            }
        ]
    )

    result = add_event_risk_drilldown_columns(events)

    assert result.loc[0, "event_risk_focus"] == "未見明顯風險"
    assert result.loc[0, "event_evidence_summary"] == "無額外風險證據"
