from pathlib import Path

import pandas as pd

from risk_service import RiskService
from settings import AppConfig


def make_config() -> AppConfig:
    return AppConfig(
        root_dir=Path("."),
        data_dir=Path("."),
        output_dir=Path("."),
        imports_dir=Path("."),
        attendance_import_dir=Path("."),
        cleaned_dir=Path("."),
        reports_dir=Path("."),
        database_dir=Path("."),
        templates_dir=Path("."),
        logs_dir=Path("."),
        sqlite_path=Path("test.sqlite"),
        settings_path=Path("settings.json"),
    )


def test_risk_threshold_defaults_are_available() -> None:
    config = make_config()

    assert config.risk_review_distance_m == 1000.0
    assert config.risk_high_distance_m == 1500.0
    assert config.risk_customer_override_gap_m == 500.0
    assert config.risk_home_radius_m == 500.0


def test_far_existing_client_override_requires_review() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "near clinic", "beeline_meter": 772.0, "is_existing_client": 0, "is_selected": 0, "selection_type": "candidate"},
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 16, "hospital_id": "c1", "hospital_label": "existing client", "beeline_meter": 1800.0, "is_existing_client": 1, "is_selected": 1, "selection_type": "existing"},
        ]
    )
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:08:04"}])

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame())
    row = result.iloc[0]

    assert row["risk_level"] == "需覆核"
    assert "far_customer_override" in row["risk_reason_codes"]
    assert row["risk_score"] >= 8


def test_score_at_least_10_takes_high_risk_precedence() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "near clinic", "beeline_meter": 772.0, "is_existing_client": 0, "is_selected": 0, "selection_type": "candidate"},
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 16, "hospital_id": "c1", "hospital_label": "existing client", "beeline_meter": 2434.0, "is_existing_client": 1, "is_selected": 1, "selection_type": "existing"},
        ]
    )
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:08:04"}])

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame())
    row = result.iloc[0]

    assert row["risk_level"] == "高風險需覆核"
    assert row["risk_score"] >= 10
    assert "far_customer_override" in row["risk_reason_codes"]
    assert "selected_not_top5" in row["risk_reason_codes"]
    assert "selected_distance_too_far" in row["risk_reason_codes"]


def test_distant_only_candidate_without_selection_is_not_reasonable() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "far clinic", "beeline_meter": 2500.0},
        ]
    )
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:08:04"}])

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame())
    row = result.iloc[0]

    assert row["risk_level"] == "低信心"
    assert "no_reasonable_candidate" in row["risk_reason_codes"]
    assert row["risk_score"] > 0


def test_non_gps_events_are_not_scored_as_visit_risk() -> None:
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:08:04", "gps_lat": 24.7, "gps_lon": 121.7},
            {"event_uid": "e2", "attendance_uid": "a1", "actual_time": "2026-05-08 18:08:04", "gps_lat": pd.NA, "gps_lon": pd.NA},
        ]
    )
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "near clinic", "beeline_meter": 300.0, "is_selected": 1},
        ]
    )

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame())

    assert result["event_uid"].tolist() == ["e1"]
    assert "e2" not in set(result["event_uid"])


def test_nearby_candidate_conflict_is_low_confidence() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "A診所", "beeline_meter": 120.0, "is_existing_client": 0, "is_selected": 1, "selection_type": "潛在院所"},
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 2, "hospital_id": "h2", "hospital_label": "B診所", "beeline_meter": 180.0, "is_existing_client": 0, "is_selected": 0, "selection_type": "潛在院所"},
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 3, "hospital_id": "h3", "hospital_label": "C診所", "beeline_meter": 220.0, "is_existing_client": 0, "is_selected": 0, "selection_type": "潛在院所"},
        ]
    )
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:00:00"}])

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame())

    assert result.iloc[0]["risk_level"] == "低信心"
    assert "nearby_candidate_conflict" in result.iloc[0]["risk_reason_codes"]


def test_impossible_travel_time_is_high_risk() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "A診所", "beeline_meter": 50.0, "is_existing_client": 0, "is_selected": 1, "selection_type": "潛在院所"},
            {"event_uid": "e2", "attendance_uid": "a1", "seq_no": 2, "candidate_rank": 1, "hospital_id": "h2", "hospital_label": "B診所", "beeline_meter": 60.0, "is_existing_client": 0, "is_selected": 1, "selection_type": "潛在院所"},
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:00:00", "source_row_no": 1},
            {"event_uid": "e2", "attendance_uid": "a1", "actual_time": "2026-05-08 08:10:00", "source_row_no": 2},
        ]
    )
    route_segments = pd.DataFrame(
        [
            {"attendance_uid": "a1", "segment_no": 1, "segment_type": "between_points", "duration_seconds": 3600, "distance_meters": 20000, "status": "OK"}
        ]
    )

    result = RiskService(make_config()).build_event_risk(raw_events, matches, route_segments, pd.DataFrame())

    assert "impossible_travel_time" in result.loc[result["event_uid"] == "e2", "risk_reason_codes"].iloc[0]
    assert result.loc[result["event_uid"] == "e2", "risk_level"].iloc[0] == "高風險需覆核"


def test_impossible_travel_pairs_skip_non_gps_events() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "A診所", "beeline_meter": 50.0, "is_existing_client": 0, "is_selected": 1, "selection_type": "潛在院所"},
            {"event_uid": "clock", "attendance_uid": "a1", "seq_no": 2, "candidate_rank": 1, "hospital_id": "h2", "hospital_label": "B診所", "beeline_meter": 60.0, "is_existing_client": 0, "is_selected": 1, "selection_type": "潛在院所"},
            {"event_uid": "e2", "attendance_uid": "a1", "seq_no": 3, "candidate_rank": 1, "hospital_id": "h3", "hospital_label": "C診所", "beeline_meter": 70.0, "is_existing_client": 0, "is_selected": 1, "selection_type": "潛在院所"},
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:00:00", "source_row_no": 1, "gps_lat": 25.01, "gps_lon": 121.01},
            {"event_uid": "clock", "attendance_uid": "a1", "actual_time": "2026-05-08 08:05:00", "source_row_no": 2, "gps_lat": None, "gps_lon": None},
            {"event_uid": "e2", "attendance_uid": "a1", "actual_time": "2026-05-08 09:00:00", "source_row_no": 3, "gps_lat": 25.02, "gps_lon": 121.02},
        ]
    )
    route_segments = pd.DataFrame(
        [
            {"attendance_uid": "a1", "segment_no": 1, "segment_type": "between_points", "duration_seconds": 7200, "distance_meters": 20000, "status": "OK"}
        ]
    )

    result = RiskService(make_config()).build_event_risk(raw_events, matches, route_segments, pd.DataFrame())

    e2_reasons = result.loc[result["event_uid"] == "e2", "risk_reason_codes"].iloc[0]
    assert "clock" not in set(result["event_uid"])
    assert "impossible_travel_time" in e2_reasons


def test_home_area_only_trace_requires_review() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e2", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "員工A",
                "department": "業務",
                "work_date": "2026-05-08",
                "gps_event_count": 2,
            }
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "gps_lat": 24.70000, "gps_lon": 121.77000, "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "e2", "attendance_uid": "a1", "gps_lat": 24.70050, "gps_lon": 121.77050, "actual_time": "2026-05-08 18:00:00"},
        ]
    )
    employees = pd.DataFrame(
        [{"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010}]
    )

    service = RiskService(make_config())
    daily = service.build_daily_risk_summary(event_risk, attendance, raw_events=raw_events, employees=employees, matches=pd.DataFrame())
    row = daily.iloc[0]

    assert row["risk_level"] == "需覆核"
    assert row["home_area_only_trace"] == 1
    assert "home_area_only_trace" in row["risk_reason_summary"]
    assert row["risk_score"] >= 6


def test_home_area_only_trace_accepts_raw_events_with_employee_id() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "risk_level": "甇?虜", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e2", "attendance_uid": "a1", "risk_level": "甇?虜", "risk_score": 0, "risk_reason_codes": ""},
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "?∪極A",
                "department": "璆剖?",
                "work_date": "2026-05-08",
                "gps_event_count": 2,
            }
        ]
    )
    raw_events = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "employee_id": "A",
                "gps_lat": 24.70000,
                "gps_lon": 121.77000,
                "actual_time": "2026-05-08 08:00:00",
            },
            {
                "event_uid": "e2",
                "attendance_uid": "a1",
                "employee_id": "A",
                "gps_lat": 24.70050,
                "gps_lon": 121.77050,
                "actual_time": "2026-05-08 18:00:00",
            },
        ]
    )
    employees = pd.DataFrame(
        [{"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010}]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(
        event_risk,
        attendance,
        raw_events=raw_events,
        employees=employees,
        matches=pd.DataFrame(),
    )

    assert daily.iloc[0]["home_area_only_trace"] == 1


def test_home_start_end_with_field_visit_is_not_penalized() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e2", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e3", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "員工A",
                "department": "業務",
                "work_date": "2026-05-08",
                "gps_event_count": 3,
            }
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "gps_lat": 24.70000, "gps_lon": 121.77000, "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "e2", "attendance_uid": "a1", "gps_lat": 24.73000, "gps_lon": 121.80000, "actual_time": "2026-05-08 10:00:00"},
            {"event_uid": "e3", "attendance_uid": "a1", "gps_lat": 24.70040, "gps_lon": 121.77040, "actual_time": "2026-05-08 18:00:00"},
        ]
    )
    employees = pd.DataFrame(
        [{"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010}]
    )
    matches = pd.DataFrame(
        [
            {"event_uid": "e2", "attendance_uid": "a1", "is_selected": 1, "beeline_meter": 120.0, "selection_type": "既有客戶"}
        ]
    )

    service = RiskService(make_config())
    daily = service.build_daily_risk_summary(event_risk, attendance, raw_events=raw_events, employees=employees, matches=matches)

    assert daily.iloc[0]["home_area_only_trace"] == 0
    assert "home_area_only_trace" not in daily.iloc[0]["risk_reason_summary"]


def test_employee_summary_normalizes_by_gps_count() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "a1e1", "attendance_uid": "a1", "risk_level": "需覆核", "risk_score": 8, "risk_reason_codes": "far_customer_override"},
            {"event_uid": "a1e2", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "b1e1", "attendance_uid": "b1", "risk_level": "需覆核", "risk_score": 8, "risk_reason_codes": "far_customer_override"},
        ]
    )
    attendance = pd.DataFrame(
        [
            {"attendance_uid": "a1", "employee_id": "A", "employee_name": "員工A", "department": "業務", "work_date": "2026-05-08", "gps_event_count": 10},
            {"attendance_uid": "b1", "employee_id": "B", "employee_name": "員工B", "department": "業務", "work_date": "2026-05-08", "gps_event_count": 2},
        ]
    )

    service = RiskService(make_config())
    daily = service.build_daily_risk_summary(event_risk, attendance)
    employee = service.build_employee_risk_summary(daily)

    assert set(daily["attendance_uid"]) == {"a1", "b1"}
    assert employee.sort_values("risk_rate", ascending=False).iloc[0]["employee_id"] == "B"


def test_daily_summary_counts_high_risk_event_label() -> None:
    event_risk = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "risk_level": "高風險需覆核",
                "risk_score": 10,
                "risk_reason_codes": "impossible_travel_time",
            }
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "員工A",
                "department": "業務",
                "work_date": "2026-05-08",
                "gps_event_count": 1,
            }
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(event_risk, attendance)
    row = daily.iloc[0]

    assert row["high_risk_event_count"] == 1
    assert row["review_event_count"] == 1
    assert row["risk_level"] == "高風險需覆核"


def test_employee_summary_preserves_high_risk_daily_label() -> None:
    daily_risk = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "員工A",
                "department": "業務",
                "gps_event_count": 1,
                "risk_score": 10,
                "review_event_count": 1,
                "high_risk_event_count": 1,
                "home_area_only_trace": 0,
                "home_start_end_without_field_trace": 0,
                "insufficient_route_evidence": 0,
            }
        ]
    )

    employee = RiskService(make_config()).build_employee_risk_summary(daily_risk)

    assert employee.iloc[0]["risk_level"] == "高風險需覆核"


def test_rank_one_field_candidate_counts_as_field_visit_evidence() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e2", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e3", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "員工A",
                "department": "業務",
                "work_date": "2026-05-08",
                "gps_event_count": 3,
            }
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "gps_lat": 24.70000, "gps_lon": 121.77000, "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "e2", "attendance_uid": "a1", "gps_lat": 24.73000, "gps_lon": 121.80000, "actual_time": "2026-05-08 10:00:00"},
            {"event_uid": "e3", "attendance_uid": "a1", "gps_lat": 24.70040, "gps_lon": 121.77040, "actual_time": "2026-05-08 18:00:00"},
        ]
    )
    employees = pd.DataFrame(
        [{"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010}]
    )
    matches = pd.DataFrame(
        [
            {"event_uid": "e2", "attendance_uid": "a1", "candidate_rank": 1, "is_selected": 0, "beeline_meter": 120.0}
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(
        event_risk,
        attendance,
        raw_events=raw_events,
        employees=employees,
        matches=matches,
    )
    row = daily.iloc[0]

    assert row["home_start_end_without_field_trace"] == 0
    assert row["field_visit_count"] == 1


def test_selected_match_near_home_does_not_suppress_home_area_only_trace() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e2", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "員工A",
                "department": "業務",
                "work_date": "2026-05-08",
                "gps_event_count": 2,
            }
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "gps_lat": 24.70000, "gps_lon": 121.77000, "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "e2", "attendance_uid": "a1", "gps_lat": 24.70050, "gps_lon": 121.77050, "actual_time": "2026-05-08 18:00:00"},
        ]
    )
    employees = pd.DataFrame(
        [{"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010}]
    )
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 4, "is_selected": 1, "beeline_meter": 80.0}
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(
        event_risk,
        attendance,
        raw_events=raw_events,
        employees=employees,
        matches=matches,
    )
    row = daily.iloc[0]

    assert row["home_area_only_trace"] == 1
    assert row["field_visit_count"] == 0


def test_duplicate_employee_home_rows_do_not_inflate_home_event_counts() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e2", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "員工A",
                "department": "業務",
                "work_date": "2026-05-08",
                "gps_event_count": 2,
            }
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "gps_lat": 24.70000, "gps_lon": 121.77000, "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "e2", "attendance_uid": "a1", "gps_lat": 24.70050, "gps_lon": 121.77050, "actual_time": "2026-05-08 18:00:00"},
        ]
    )
    employees = pd.DataFrame(
        [
            {"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010},
            {"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010},
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(
        event_risk,
        attendance,
        raw_events=raw_events,
        employees=employees,
        matches=pd.DataFrame(),
    )

    assert daily.iloc[0]["home_near_event_count"] == 2
