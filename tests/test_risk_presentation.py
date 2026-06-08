import pandas as pd

from risk_presentation import (
    add_event_risk_drilldown_columns,
    build_employee_risk_source_breakdown,
    build_company_monthly_risk_trend,
    build_monthly_risk_trend,
    prepare_risk_review_quadrant,
)


def test_monthly_risk_trend_includes_daily_level_risk_sources() -> None:
    daily_risk = pd.DataFrame(
        [
            {
                "employee_id": "E01",
                "employee_label": "E01 Alice",
                "department": "Sales",
                "work_date": "2026-05-01",
                "risk_priority_score": 27,
                "review_event_count": 0,
                "high_risk_event_count": 0,
                "low_confidence_event_count": 0,
                "home_area_only_trace": 0,
                "insufficient_checkin_count": 1,
                "short_attendance_span": 0,
                "long_attendance_span": 0,
                "gps_event_count": 1,
            },
            {
                "employee_id": "E01",
                "employee_label": "E01 Alice",
                "department": "Sales",
                "work_date": "2026-05-02",
                "risk_priority_score": 17,
                "review_event_count": 0,
                "high_risk_event_count": 0,
                "low_confidence_event_count": 0,
                "home_area_only_trace": 0,
                "insufficient_checkin_count": 0,
                "short_attendance_span": 1,
                "long_attendance_span": 0,
                "gps_event_count": 2,
            },
            {
                "employee_id": "E02",
                "employee_label": "E02 Bob",
                "department": "Sales",
                "work_date": "2026-05-02",
                "risk_priority_score": 5,
                "review_event_count": 0,
                "high_risk_event_count": 0,
                "low_confidence_event_count": 0,
                "home_area_only_trace": 0,
                "insufficient_checkin_count": 0,
                "short_attendance_span": 0,
                "long_attendance_span": 1,
                "gps_event_count": 2,
            },
        ]
    )

    monthly = build_monthly_risk_trend(daily_risk)
    alice = monthly.loc[monthly["employee_id"].eq("E01")].iloc[0]

    assert alice["insufficient_checkin_days"] == 1
    assert alice["short_attendance_span_days"] == 1
    assert alice["long_attendance_span_days"] == 0

    company = build_company_monthly_risk_trend(monthly)
    may = company.loc[company["year_month"].eq("2026-05")].iloc[0]

    assert may["insufficient_checkin_days"] == 1
    assert may["short_attendance_span_days"] == 1
    assert may["long_attendance_span_days"] == 1


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


def test_employee_risk_source_breakdown_uses_v3_score_units() -> None:
    summary = pd.DataFrame(
        [
            {
                "employee_id": "E01",
                "employee_label": "E01 Alice",
                "department": "Sales",
                "異常風險分": 40,
                "僅居家附近軌跡天數": 2,
                "打卡不足天數": 1,
                "出勤時數過短天數": 2,
            },
            {
                "employee_id": "E02",
                "employee_label": "E02 Bob",
                "department": "Sales",
                "異常風險分": 0,
                "僅居家附近軌跡天數": 0,
                "打卡不足天數": 0,
                "出勤時數過短天數": 0,
            },
        ]
    )

    result = build_employee_risk_source_breakdown(summary)
    alice = result.loc[result["employee_id"].eq("E01")]

    assert set(alice["source"]) == {"全日居家", "打卡不足", "工時過短", "其他異常"}
    scores = dict(zip(alice["source"], alice["score"]))
    assert scores["全日居家"] == 16
    assert scores["打卡不足"] == 5
    assert scores["工時過短"] == 8
    assert scores["其他異常"] == 11
    assert "E02" not in set(result["employee_id"])


def test_prepare_risk_review_quadrant_uses_risk_and_review_scores() -> None:
    summary = pd.DataFrame(
        [
            {
                "employee_id": "E01",
                "employee_label": "E01 Alice",
                "department": "Sales",
                "異常風險分": 2,
                "開發/覆核分": 4,
                "綜合優先分": 10,
            },
            {
                "employee_id": "E02",
                "employee_label": "E02 Bob",
                "department": "Sales",
                "異常風險分": 10,
                "開發/覆核分": 8,
                "綜合優先分": 38,
            },
        ]
    )

    result, avg_review, avg_risk = prepare_risk_review_quadrant(summary)

    assert result[["開發/覆核分", "異常風險分"]].to_dict("records") == [
        {"開發/覆核分": 4, "異常風險分": 2},
        {"開發/覆核分": 8, "異常風險分": 10},
    ]
    assert avg_review == 6
    assert avg_risk == 6
    assert result["marker_size"].tolist() == [10, 38]
