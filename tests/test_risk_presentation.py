from __future__ import annotations

import pandas as pd

from risk_presentation import (
    add_daily_risk_drilldown_columns,
    add_event_risk_drilldown_columns,
    add_overview_risk_drilldown_columns,
    build_company_monthly_risk_trend,
    build_employee_monthly_warming,
    build_monthly_risk_trend,
    summarize_place_risk_visits,
    summarize_top_risk_day,
    translate_risk_reason_codes,
)


def test_daily_drilldown_columns_prioritize_home_and_high_risk():
    daily = pd.DataFrame(
        [
            {
                "work_date": pd.Timestamp("2026-05-01"),
                "risk_score": 5,
                "high_risk_event_count": 0,
                "review_event_count": 1,
                "home_area_only_trace": 1,
                "home_start_end_without_field_trace": 0,
                "insufficient_route_evidence": 0,
                "risk_reason_summary": "住家附近",
            },
            {
                "work_date": pd.Timestamp("2026-05-02"),
                "risk_score": 12,
                "high_risk_event_count": 2,
                "review_event_count": 2,
                "home_area_only_trace": 0,
                "home_start_end_without_field_trace": 1,
                "insufficient_route_evidence": 0,
                "risk_reason_summary": "距離過遠",
            },
        ]
    )

    result = add_daily_risk_drilldown_columns(daily)

    assert result.loc[0, "primary_risk_reason"] == "僅居家附近軌跡"
    assert result.loc[1, "primary_risk_reason"] == "住家起訖但缺外勤軌跡"
    assert result.loc[1, "risk_drilldown_hint"] == "優先查看 2026-05-02"
    assert result.loc[1, "risk_priority"] > result.loc[0, "risk_priority"]


def test_overview_drilldown_columns_surface_most_risky_employee():
    overview = pd.DataFrame(
        [
            {"employee_label": "A 業務", "風險分數": 4, "高風險點數": 0, "需覆核點數": 2, "僅居家附近軌跡天數": 0, "住家起訖但缺外勤軌跡天數": 0},
            {"employee_label": "B 業務", "風險分數": 8, "高風險點數": 1, "需覆核點數": 1, "僅居家附近軌跡天數": 2, "住家起訖但缺外勤軌跡天數": 0},
        ]
    )

    result = add_overview_risk_drilldown_columns(overview)

    assert list(result.sort_values("risk_priority", ascending=False)["employee_label"])[0] == "B 業務"
    assert result.loc[1, "主要風險原因"] == "僅居家附近軌跡"
    assert result.loc[1, "追查提示"] == "優先查看 B 業務的個人報表"


def test_event_drilldown_columns_explain_distance_and_rank_issues():
    events = pd.DataFrame(
        [
            {
                "event_time": "10:00",
                "risk_score": 4,
                "selected_distance_m": 1800,
                "nearest_distance_m": 200,
                "distance_gap_m": 1600,
                "selected_rank": 7,
                "risk_reason_text": "選取候選排名第 7，超出前 5 名",
            }
        ]
    )

    result = add_event_risk_drilldown_columns(events)

    assert result.loc[0, "event_risk_focus"] == "選定院所距離過遠"
    assert "選定距離 1800m" in result.loc[0, "event_evidence_summary"]
    assert "最近候選 200m" in result.loc[0, "event_evidence_summary"]
    assert "排名 7" in result.loc[0, "event_evidence_summary"]


def test_event_drilldown_prioritizes_near_home_checkin():
    events = pd.DataFrame(
        [
            {
                "risk_score": 10,
                "risk_reason_codes": "near_home_checkin,far_customer_override",
                "risk_reason_text": "打卡點距住家 39m，可能在住家附近打卡",
                "selected_distance_m": 1227,
                "nearest_distance_m": 541,
                "distance_gap_m": 686,
                "selected_rank": 37,
                "distance_from_home_m": 39,
            }
        ]
    )

    result = add_event_risk_drilldown_columns(events)

    assert result.loc[0, "event_risk_focus"] == "可能在家附近打卡"
    assert "距住家 39m" in result.loc[0, "event_evidence_summary"]


def test_summarize_top_risk_day_returns_actionable_hint():
    daily = pd.DataFrame(
        [
            {"work_date": pd.Timestamp("2026-05-01"), "risk_score": 1, "high_risk_event_count": 0, "review_event_count": 1},
            {"work_date": pd.Timestamp("2026-05-03"), "risk_score": 9, "high_risk_event_count": 1, "review_event_count": 2},
        ]
    )

    top = summarize_top_risk_day(daily)

    assert top["date"] == "2026-05-03"
    assert top["hint"] == "優先查看 2026-05-03 日報表"


def test_summarize_place_risk_visits_surfaces_risky_frequent_place():
    events = pd.DataFrame(
        [
            {
                "selected_hospital_name": "德風藥局",
                "selected_client_tag": "既有客戶",
                "risk_level": "高風險",
                "risk_score": 6,
                "selected_distance_m": 1800,
                "nearest_distance_m": 120,
                "distance_gap_m": 1680,
            }
            for _ in range(14)
        ]
        + [
            {
                "selected_hospital_name": "衛生福利部嘉義醫院",
                "selected_client_tag": "既有客戶",
                "risk_level": "正常",
                "risk_score": 0,
                "selected_distance_m": 80,
                "nearest_distance_m": 80,
                "distance_gap_m": 0,
            }
            for _ in range(12)
        ]
    )

    result = summarize_place_risk_visits(events)

    assert result.loc[0, "地點名稱"] == "德風藥局"
    assert result.loc[0, "拜訪次數"] == 14
    assert result.loc[0, "高風險"] == 14
    assert result.loc[0, "風險拜訪次數"] == 14
    assert result.loc[0, "主要風險等級"] == "高風險"
    assert result.loc[0, "主要風險原因"] == "選定院所距離過遠"
    assert "高風險 14" in result.loc[0, "地點風險摘要"]
    assert result.loc[1, "地點名稱"] == "衛生福利部嘉義醫院"
    assert result.loc[1, "正常"] == 12


def test_summarize_place_risk_visits_accepts_match_table_columns():
    matches = pd.DataFrame(
        [
            {"hospital_label": "A 院所", "client_tag": "潛在院所", "risk_level": "需覆核", "risk_score": 2},
            {"hospital_label": "A 院所", "client_tag": "潛在院所", "risk_level": "正常", "risk_score": 0},
            {"hospital_label": "B 院所", "client_tag": "既有客戶", "risk_level": "低信心", "risk_score": 1},
        ]
    )

    result = summarize_place_risk_visits(matches, name_col="hospital_label", tag_col="client_tag")

    row = result.loc[result["地點名稱"] == "A 院所"].iloc[0]
    assert row["拜訪次數"] == 2
    assert row["需覆核"] == 1
    assert row["正常"] == 1
    assert row["風險拜訪次數"] == 1


def test_translate_risk_reason_codes_to_chinese_descriptions():
    text = translate_risk_reason_codes("far_customer_override,selected_distance_too_far,selected_not_top5")

    assert "系統選到較遠的既有客戶" in text
    assert "距離過遠" in text
    assert "前 5 名候選" in text
    assert "far_customer_override" not in text


def test_translate_risk_reason_codes_keeps_unknown_codes_visible():
    text = translate_risk_reason_codes("unknown_reason,nearby_candidate_conflict")

    assert "unknown_reason" in text
    assert "附近候選院所過於密集" in text


def test_build_monthly_risk_trend_normalizes_by_attendance_days():
    daily = pd.DataFrame(
        [
            {
                "employee_id": "A",
                "employee_label": "A 業務",
                "department": "北區",
                "work_date": "2026-03-01",
                "risk_priority_score": 10,
                "review_event_count": 1,
                "high_risk_event_count": 0,
                "low_confidence_event_count": 2,
                "home_area_only_trace": 0,
                "gps_event_count": 5,
            },
            {
                "employee_id": "A",
                "employee_label": "A 業務",
                "department": "北區",
                "work_date": "2026-03-02",
                "risk_priority_score": 20,
                "review_event_count": 0,
                "high_risk_event_count": 1,
                "low_confidence_event_count": 0,
                "home_area_only_trace": 1,
                "gps_event_count": 5,
            },
            {
                "employee_id": "B",
                "employee_label": "B 業務",
                "department": "中區",
                "work_date": "2026-04-01",
                "risk_priority_score": 18,
                "review_event_count": 2,
                "high_risk_event_count": 1,
                "low_confidence_event_count": 1,
                "home_area_only_trace": 0,
                "gps_event_count": 3,
            },
        ]
    )
    claims = pd.DataFrame(
        [
            {"employee_id": "A", "year_month": "2026-03", "difference_rate": 0.2},
            {"employee_id": "B", "year_month": "2026-04", "difference_rate": -0.5},
        ]
    )

    trend = build_monthly_risk_trend(daily, claims)

    march = trend.loc[trend["year_month"] == "2026-03"].iloc[0]
    assert march["attendance_days"] == 2
    assert march["risk_priority_score"] == 30
    assert march["risk_priority_per_day"] == 15
    assert march["high_risk_event_count"] == 1
    assert march["claim_diff_abs_rate"] == 0.2
    april = trend.loc[trend["year_month"] == "2026-04"].iloc[0]
    assert april["claim_diff_abs_rate"] == 0.5


def test_build_employee_monthly_warming_compares_latest_month_to_history():
    trend = pd.DataFrame(
        [
            {"year_month": "2026-03", "employee_id": "A", "employee_label": "A 業務", "department": "北區", "risk_priority_per_day": 2.0, "risk_priority_score": 20, "high_risk_event_count": 0, "home_area_only_days": 0},
            {"year_month": "2026-04", "employee_id": "A", "employee_label": "A 業務", "department": "北區", "risk_priority_per_day": 4.0, "risk_priority_score": 40, "high_risk_event_count": 1, "home_area_only_days": 0},
            {"year_month": "2026-05", "employee_id": "A", "employee_label": "A 業務", "department": "北區", "risk_priority_per_day": 12.0, "risk_priority_score": 120, "high_risk_event_count": 3, "home_area_only_days": 1},
            {"year_month": "2026-04", "employee_id": "B", "employee_label": "B 業務", "department": "中區", "risk_priority_per_day": 8.0, "risk_priority_score": 80, "high_risk_event_count": 2, "home_area_only_days": 0},
            {"year_month": "2026-05", "employee_id": "B", "employee_label": "B 業務", "department": "中區", "risk_priority_per_day": 7.0, "risk_priority_score": 70, "high_risk_event_count": 1, "home_area_only_days": 0},
        ]
    )

    warming = build_employee_monthly_warming(trend, latest_month="2026-05")

    assert warming.iloc[0]["employee_id"] == "A"
    assert warming.iloc[0]["baseline_risk_priority_per_day"] == 3.0
    assert warming.iloc[0]["warming_delta"] == 9.0
    assert warming.iloc[0]["warming_ratio"] == 4.0


def test_build_company_monthly_risk_trend_counts_people_and_risky_share():
    trend = pd.DataFrame(
        [
            {"year_month": "2026-05", "employee_id": "A", "risk_priority_score": 30, "attendance_days": 3, "high_risk_event_count": 1, "review_event_count": 2, "low_confidence_event_count": 0, "home_area_only_days": 0, "claim_diff_abs_rate": 0.1},
            {"year_month": "2026-05", "employee_id": "B", "risk_priority_score": 1, "attendance_days": 2, "high_risk_event_count": 0, "review_event_count": 0, "low_confidence_event_count": 1, "home_area_only_days": 0, "claim_diff_abs_rate": 0.2},
            {"year_month": "2026-05", "employee_id": "C", "risk_priority_score": 18, "attendance_days": 1, "high_risk_event_count": 0, "review_event_count": 1, "low_confidence_event_count": 0, "home_area_only_days": 1, "claim_diff_abs_rate": 0.3},
            {"year_month": "2026-06", "employee_id": "A", "risk_priority_score": 12, "attendance_days": 2, "high_risk_event_count": 0, "review_event_count": 1, "low_confidence_event_count": 0, "home_area_only_days": 0, "claim_diff_abs_rate": 0.4},
        ]
    )

    company = build_company_monthly_risk_trend(trend)

    may = company.loc[company["year_month"] == "2026-05"].iloc[0]
    assert may["employee_count"] == 3
    assert may["risky_employee_count"] == 2
    assert may["risky_employee_rate"] == 2 / 3
    assert may["risk_priority_per_day"] == 49 / 6
    assert may["risk_priority_per_employee"] == 49 / 3
    assert round(may["claim_diff_abs_rate"], 6) == 0.2
