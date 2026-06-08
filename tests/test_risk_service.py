from pathlib import Path

import pandas as pd

from risk_service import HIGH_RISK_LABEL, LOW_CONFIDENCE_LABEL, REVIEW_LABEL, RiskService
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
    assert config.hospital_priority_distance_m == 1000.0
    assert config.existing_client_priority_distance_m == 1000.0
    assert config.risk_customer_override_gap_m == 500.0
    assert config.risk_home_radius_m == 500.0
    assert config.risk_min_checkin_count == 2
    assert config.risk_min_attendance_span_hours == 6.0
    assert config.risk_max_attendance_span_hours == 14.0
    assert config.risk_home_core_event_score == 0
    assert config.risk_home_edge_event_score == 0


def test_v3_home_core_short_circuits_existing_client_match() -> None:
    raw_events = pd.DataFrame(
        [{"event_uid": "e1", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.7000, "gps_lon": 121.7700}]
    )
    employees = pd.DataFrame([{"employee_id": "A", "home_lat": 24.7001, "home_lon": 121.7701}])
    matches = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "candidate_rank": 1,
                "hospital_label": "近家既有客戶",
                "beeline_meter": 50.0,
                "is_existing_client": 1,
                "is_hospital_facility": 0,
            }
        ]
    )

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame(), employees=employees)
    row = result.iloc[0]

    assert row["location_class"] == "home_core"
    assert row["selected_visit_type"] == "極近居家點"
    assert row["selected_visit_name"] == "極近居家點"
    assert row["risk_score"] == 0
    assert row["review_score"] == 0


def test_v3_existing_client_visit_binds_nearest_client_within_1000m() -> None:
    raw_events = pd.DataFrame(
        [{"event_uid": "e1", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.7200, "gps_lon": 121.7900}]
    )
    employees = pd.DataFrame([{"employee_id": "A", "home_lat": 24.7000, "home_lon": 121.7700}])
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 1, "hospital_label": "潛在院所", "beeline_meter": 90.0, "is_existing_client": 0, "is_hospital_facility": 1},
            {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 2, "hospital_label": "既有A", "beeline_meter": 800.0, "is_existing_client": 1, "is_hospital_facility": 0},
            {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 3, "hospital_label": "既有B", "beeline_meter": 950.0, "is_existing_client": 1, "is_hospital_facility": 0},
        ]
    )

    row = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame(), employees=employees).iloc[0]

    assert row["location_class"] == "existing_client_visit"
    assert row["selected_visit_name"] == "既有A"
    assert row["selected_visit_type"] == "既有客戶拜訪點"
    assert row["selected_visit_distance_m"] == 800.0
    assert row["risk_score"] == 0
    assert row["review_score"] == 0
    assert "既有A 800公尺" in row["existing_client_candidates_top3"]


def test_v3_home_edge_applies_after_no_existing_client_within_1000m() -> None:
    raw_events = pd.DataFrame(
        [{"event_uid": "e1", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.7040, "gps_lon": 121.7700}]
    )
    employees = pd.DataFrame([{"employee_id": "A", "home_lat": 24.7000, "home_lon": 121.7700}])
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 1, "hospital_label": "遠既有", "beeline_meter": 1300.0, "is_existing_client": 1, "is_hospital_facility": 0},
        ]
    )

    row = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame(), employees=employees).iloc[0]

    assert row["location_class"] == "home_edge"
    assert row["selected_visit_type"] == "邊緣居家點"
    assert row["risk_score"] == 0
    assert row["review_score"] == 0


def test_v3_unknown_field_does_not_hard_select_customer_and_suggests_prospects() -> None:
    raw_events = pd.DataFrame(
        [{"event_uid": "e1", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.9000, "gps_lon": 121.2000}]
    )
    employees = pd.DataFrame([{"employee_id": "A", "home_lat": 24.7000, "home_lon": 121.7700}])
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 1, "hospital_label": "潛在A", "beeline_meter": 120.0, "is_existing_client": 0, "is_hospital_facility": 1},
            {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 2, "hospital_label": "潛在B", "beeline_meter": 260.0, "is_existing_client": 0, "is_hospital_facility": 1},
            {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 3, "hospital_label": "遠既有", "beeline_meter": 1600.0, "is_existing_client": 1, "is_hospital_facility": 0},
        ]
    )

    row = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame(), employees=employees).iloc[0]

    assert row["location_class"] == "unknown_field"
    assert row["selected_visit_name"] == "未知出勤點"
    assert row["selected_visit_type"] == "未知出勤點"
    assert row["risk_score"] == 0
    assert row["review_score"] == 4
    assert "潛在A 120公尺" in row["suggested_prospects_top3"]
    assert row["nearest_existing_client_name"] == "遠既有"


def test_v3_unknown_field_uses_nearest_non_client_candidates_as_suggested_prospects() -> None:
    raw_events = pd.DataFrame(
        [{"event_uid": "e1", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 23.9600, "gps_lon": 121.5900}]
    )
    employees = pd.DataFrame([{"employee_id": "A", "home_lat": 24.7000, "home_lon": 121.7700}])
    matches = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "candidate_rank": 1,
                "hospital_label": "亨寧藥局",
                "beeline_meter": 30.0,
                "is_existing_client": 0,
                "is_hospital_facility": 0,
            },
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "candidate_rank": 2,
                "hospital_label": "何裕鈞骨外科診所",
                "beeline_meter": 84.0,
                "is_existing_client": 0,
                "is_hospital_facility": 0,
            },
        ]
    )

    row = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame(), employees=employees).iloc[0]

    assert row["location_class"] == "unknown_field"
    assert "亨寧藥局 30公尺" in row["suggested_prospects_top3"]
    assert "何裕鈞骨外科診所 84公尺" in row["suggested_prospects_top3"]


def test_far_existing_client_override_becomes_unknown_field_review() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "near clinic", "beeline_meter": 772.0, "is_existing_client": 0, "is_selected": 0, "selection_type": "candidate"},
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 16, "hospital_id": "c1", "hospital_label": "existing client", "beeline_meter": 1800.0, "is_existing_client": 1, "is_selected": 1, "selection_type": "existing"},
        ]
    )
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:08:04"}])

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame())
    row = result.iloc[0]

    assert row["risk_level"] == REVIEW_LABEL
    assert row["location_class"] == "unknown_field"
    assert "unknown_field" in row["risk_reason_codes"]
    assert row["risk_score"] == 0
    assert row["review_score"] == 4
    assert row["selected_visit_name"] == "未知出勤點"
    assert row["nearest_existing_client_name"] == "existing client"


def test_selected_distance_too_far_becomes_unknown_field_without_hard_selection() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "near clinic", "beeline_meter": 772.0, "is_existing_client": 0, "is_selected": 0, "selection_type": "candidate"},
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 16, "hospital_id": "c1", "hospital_label": "existing client", "beeline_meter": 2434.0, "is_existing_client": 1, "is_selected": 1, "selection_type": "existing"},
        ]
    )
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:08:04"}])

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame())
    row = result.iloc[0]

    assert row["risk_level"] == REVIEW_LABEL
    assert row["location_class"] == "unknown_field"
    assert row["risk_score"] == 0
    assert row["review_score"] == 4
    assert "unknown_field" in row["risk_reason_codes"]
    assert row["nearest_existing_client_name"] == "existing client"


def test_distant_only_candidate_without_selection_is_not_reasonable() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "far clinic", "beeline_meter": 2500.0},
        ]
    )
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:08:04"}])

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame())
    row = result.iloc[0]

    assert row["risk_level"] == REVIEW_LABEL
    assert row["location_class"] == "unknown_field"
    assert "unknown_field" in row["risk_reason_codes"]
    assert row["risk_score"] == 0
    assert row["review_score"] == 4


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

    assert result.iloc[0]["risk_level"] == REVIEW_LABEL
    assert result.iloc[0]["location_class"] == "unknown_field"
    assert "unknown_field" in result.iloc[0]["risk_reason_codes"]
    assert result.iloc[0]["risk_score"] == 0
    assert result.iloc[0]["review_score"] == 4


def test_low_confidence_reasons_do_not_raise_daily_risk_score() -> None:
    event_risk = pd.DataFrame(
        [
            {
                "event_uid": f"a1e{index}",
                "attendance_uid": "a1",
                "risk_level": LOW_CONFIDENCE_LABEL,
                "risk_score": 0,
                "confidence_score": 2,
                "risk_reason_codes": "nearby_candidate_conflict",
            }
            for index in range(10)
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "業務A",
                "department": "北區",
                "work_date": "2026-05-08",
                "gps_event_count": 10,
            }
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(event_risk, attendance)
    row = daily.iloc[0]

    assert row["low_confidence_event_count"] == 10
    assert row["risk_score"] == 0
    assert row["risk_priority_score"] == 0
    assert row["confidence_score"] == 20
    assert row["risk_level"] == LOW_CONFIDENCE_LABEL


def test_insufficient_checkin_count_raises_daily_risk_priority() -> None:
    event_risk = pd.DataFrame(
        [{"event_uid": "e1", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""}]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "業務A",
                "department": "北區",
                "work_date": "2026-05-08",
                "event_count": 1,
                "gps_event_count": 1,
                "first_actual_time": "2026-05-08 09:00:00",
                "last_actual_time": "2026-05-08 09:00:00",
            }
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(event_risk, attendance)
    row = daily.iloc[0]

    assert row["insufficient_checkin_count"] == 1
    assert row["risk_score"] >= 5
    assert row["risk_priority_score"] >= 12
    assert "insufficient_checkin_count" in row["risk_reason_summary"]
    assert row["review_score"] == 12
    assert row["risk_level"] == HIGH_RISK_LABEL


def test_short_attendance_span_raises_daily_risk_priority() -> None:
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
                "employee_name": "業務A",
                "department": "北區",
                "work_date": "2026-05-08",
                "event_count": 2,
                "gps_event_count": 2,
                "first_actual_time": "2026-05-08 09:00:00",
                "last_actual_time": "2026-05-08 14:30:00",
            }
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(event_risk, attendance)
    row = daily.iloc[0]

    assert row["attendance_span_minutes"] == 330
    assert row["short_attendance_span"] == 1
    assert row["risk_score"] == 4
    assert row["risk_priority_score"] == 17
    assert row["review_score"] == 5
    assert "short_attendance_span" in row["risk_reason_summary"]
    assert row["risk_level"] == REVIEW_LABEL


def test_long_attendance_span_is_confidence_not_behavior_risk() -> None:
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
                "employee_name": "業務A",
                "department": "北區",
                "work_date": "2026-05-08",
                "event_count": 2,
                "gps_event_count": 2,
                "first_actual_time": "2026-05-08 07:00:00",
                "last_actual_time": "2026-05-08 22:30:00",
            }
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(event_risk, attendance)
    row = daily.iloc[0]

    assert row["attendance_span_minutes"] == 930
    assert row["long_attendance_span"] == 1
    assert row["risk_score"] == 0
    assert row["risk_priority_score"] == 5
    assert row["review_score"] == 5
    assert row["confidence_score"] == 3
    assert "long_attendance_span" in row["risk_reason_summary"]
    assert row["risk_level"] == REVIEW_LABEL


def test_near_home_checkin_is_scored_at_event_level() -> None:
    raw_events = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "employee_id": "A",
                "gps_lat": 24.70000,
                "gps_lon": 121.77000,
                "actual_time": "2026-05-08 08:00:00",
            }
        ]
    )
    employees = pd.DataFrame(
        [{"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010}]
    )
    matches = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "candidate_rank": 37,
                "hospital_id": "c1",
                "hospital_label": "existing client",
                "beeline_meter": 1227.0,
                "is_existing_client": 1,
                "is_selected": 1,
                "selection_type": "existing",
            },
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "candidate_rank": 1,
                "hospital_id": "h1",
                "hospital_label": "near clinic",
                "beeline_meter": 541.0,
                "is_existing_client": 0,
                "is_selected": 0,
                "selection_type": "candidate",
            },
        ]
    )

    result = RiskService(make_config()).build_event_risk(
        raw_events,
        matches,
        pd.DataFrame(),
        pd.DataFrame(),
        employees=employees,
    )
    row = result.iloc[0]

    assert "near_home_checkin" in row["risk_reason_codes"]
    assert row["location_class"] == "home_core"
    assert row["risk_score"] <= 3
    assert row["distance_from_home_m"] <= make_config().risk_home_radius_m
    assert "住家" in row["risk_reason_text"]


def test_near_home_checkin_defaults_to_zero_event_risk() -> None:
    service = RiskService(make_config())
    candidates = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "candidate_rank": 1,
                "hospital_id": "h1",
                "hospital_label": "near clinic",
                "beeline_meter": 120.0,
                "is_selected": 1,
            }
        ]
    )

    scores = [
        service._score_event(pd.Series({"event_uid": "e1", "attendance_uid": "a1", "distance_from_home_m": distance}), candidates)[
            "risk_score"
        ]
        for distance in [50, 400, 800, 1200]
    ]

    assert scores == [0, 0, 0, 0]


def test_near_home_checkin_scores_can_be_enabled_from_settings() -> None:
    config = make_config()
    config.risk_home_core_event_score = 3
    config.risk_home_edge_event_score = 1
    service = RiskService(config)
    candidates = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "candidate_rank": 1,
                "hospital_id": "h1",
                "hospital_label": "near clinic",
                "beeline_meter": 120.0,
                "is_selected": 1,
            }
        ]
    )

    scores = [
        service._score_event(pd.Series({"event_uid": "e1", "attendance_uid": "a1", "distance_from_home_m": distance}), candidates)[
            "risk_score"
        ]
        for distance in [50, 400, 800, 1200]
    ]

    assert scores == [3, 1, 1, 0]


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


def test_impossible_travel_pairs_dedupe_route_segments_by_segment_no() -> None:
    matches = pd.DataFrame(
        [
            {
                "event_uid": event_uid,
                "attendance_uid": "a1",
                "seq_no": index,
                "candidate_rank": 1,
                "hospital_id": f"h{index}",
                "hospital_label": "衛生福利部八里療養院",
                "beeline_meter": 120.0,
                "is_existing_client": 1,
                "is_selected": 1,
                "selection_type": "既有客戶",
            }
            for index, event_uid in enumerate(["e1", "e2", "e3", "e4"], start=1)
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-26 08:00:00", "source_row_no": 1, "gps_lat": 25.1000, "gps_lon": 121.4000},
            {"event_uid": "e2", "attendance_uid": "a1", "actual_time": "2026-05-26 09:00:00", "source_row_no": 2, "gps_lat": 25.1200, "gps_lon": 121.4050},
            {"event_uid": "e3", "attendance_uid": "a1", "actual_time": "2026-05-26 12:33:18", "source_row_no": 3, "gps_lat": 25.145159, "gps_lon": 121.412829},
            {"event_uid": "e4", "attendance_uid": "a1", "actual_time": "2026-05-26 12:34:20", "source_row_no": 4, "gps_lat": 25.145592, "gps_lon": 121.412920},
        ]
    )
    route_segments = pd.DataFrame(
        [
            {"attendance_uid": "a1", "segment_no": 1, "segment_type": "home_to_first", "duration_seconds": 600, "distance_meters": 2000, "status": "ok", "calculated_at": "2026-05-26 13:00:00"},
            {"attendance_uid": "a1", "segment_no": 2, "segment_type": "between_points", "duration_seconds": 300, "distance_meters": 2000, "status": "ok", "calculated_at": "2026-05-26 13:00:00"},
            {"attendance_uid": "a1", "segment_no": 3, "segment_type": "between_points", "duration_seconds": 600, "distance_meters": 3000, "status": "ok", "calculated_at": "2026-05-26 13:00:00"},
            {"attendance_uid": "a1", "segment_no": 3, "segment_type": "between_points", "duration_seconds": 9999, "distance_meters": 3000, "status": "ok", "calculated_at": "2026-05-26 12:00:00"},
            {"attendance_uid": "a1", "segment_no": 4, "segment_type": "between_points", "duration_seconds": 40, "distance_meters": 40, "status": "ok", "calculated_at": "2026-05-26 13:00:00"},
        ]
    )

    result = RiskService(make_config()).build_event_risk(raw_events, matches, route_segments, pd.DataFrame())

    e4_reasons = result.loc[result["event_uid"] == "e4", "risk_reason_codes"].iloc[0]
    assert "impossible_travel_time" not in e4_reasons


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

    assert row["risk_level"] == HIGH_RISK_LABEL
    assert row["home_area_only_trace"] == 1
    assert "home_area_only_trace" in row["risk_reason_summary"]
    assert row["risk_priority_score"] >= 20


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


def test_home_start_end_without_field_trace_is_lower_priority_than_home_only() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "start", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "middle", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "end", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "home1", "attendance_uid": "b1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "home2", "attendance_uid": "b1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
        ]
    )
    attendance = pd.DataFrame(
        [
            {"attendance_uid": "a1", "employee_id": "A", "employee_name": "業務A", "department": "北區", "work_date": "2026-05-08", "gps_event_count": 3},
            {"attendance_uid": "b1", "employee_id": "B", "employee_name": "業務B", "department": "北區", "work_date": "2026-05-08", "gps_event_count": 2},
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "start", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.70000, "gps_lon": 121.77000, "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "middle", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.73000, "gps_lon": 121.80000, "actual_time": "2026-05-08 12:00:00"},
            {"event_uid": "end", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.70040, "gps_lon": 121.77040, "actual_time": "2026-05-08 18:00:00"},
            {"event_uid": "home1", "attendance_uid": "b1", "employee_id": "B", "gps_lat": 24.70000, "gps_lon": 121.77000, "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "home2", "attendance_uid": "b1", "employee_id": "B", "gps_lat": 24.70050, "gps_lon": 121.77050, "actual_time": "2026-05-08 18:00:00"},
        ]
    )
    employees = pd.DataFrame(
        [
            {"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010},
            {"employee_id": "B", "home_lat": 24.70010, "home_lon": 121.77010},
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(
        event_risk,
        attendance,
        raw_events=raw_events,
        employees=employees,
        matches=pd.DataFrame(),
    )
    start_end = daily.loc[daily["attendance_uid"] == "a1"].iloc[0]
    home_only = daily.loc[daily["attendance_uid"] == "b1"].iloc[0]

    assert start_end["home_start_end_without_field_trace"] == 1
    assert start_end["risk_level"] == REVIEW_LABEL
    assert home_only["home_area_only_trace"] == 1
    assert home_only["risk_level"] == HIGH_RISK_LABEL
    assert start_end["risk_priority_score"] < home_only["risk_priority_score"]


def test_two_home_near_points_are_home_only_not_start_end_missing_field() -> None:
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
                "employee_name": "業務A",
                "department": "北區",
                "work_date": "2026-05-08",
                "gps_event_count": 2,
            }
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.70000, "gps_lon": 121.77000, "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "e2", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.70050, "gps_lon": 121.77050, "actual_time": "2026-05-08 18:00:00"},
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
    row = daily.iloc[0]

    assert row["home_area_only_trace"] == 1
    assert row["home_start_end_without_field_trace"] == 0


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


def test_priority_score_caps_repeated_low_confidence_noise_below_home_trace() -> None:
    event_risk = pd.DataFrame(
        [
            {
                "event_uid": f"a1e{index}",
                "attendance_uid": "a1",
                "risk_level": "低信心",
                "risk_score": 0,
                "confidence_score": 2,
                "risk_reason_codes": "nearby_candidate_conflict",
            }
            for index in range(10)
        ]
        + [
            {"event_uid": "b1e1", "attendance_uid": "b1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "b1e2", "attendance_uid": "b1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
        ]
    )
    attendance = pd.DataFrame(
        [
            {"attendance_uid": "a1", "employee_id": "A", "employee_name": "員工A", "department": "業務", "work_date": "2026-05-08", "gps_event_count": 10},
            {"attendance_uid": "b1", "employee_id": "B", "employee_name": "員工B", "department": "業務", "work_date": "2026-05-08", "gps_event_count": 2},
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": f"a1e{index}", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.90, "gps_lon": 121.20}
            for index in range(10)
        ]
        + [
            {"event_uid": "b1e1", "attendance_uid": "b1", "employee_id": "B", "gps_lat": 24.70010, "gps_lon": 121.77010},
            {"event_uid": "b1e2", "attendance_uid": "b1", "employee_id": "B", "gps_lat": 24.70020, "gps_lon": 121.77020},
        ]
    )
    employees = pd.DataFrame(
        [
            {"employee_id": "A", "home_lat": 24.00, "home_lon": 121.00},
            {"employee_id": "B", "home_lat": 24.70010, "home_lon": 121.77010},
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(
        event_risk,
        attendance,
        raw_events=raw_events,
        employees=employees,
        matches=pd.DataFrame(),
    )
    noisy = daily.loc[daily["attendance_uid"] == "a1"].iloc[0]
    home_only = daily.loc[daily["attendance_uid"] == "b1"].iloc[0]

    assert noisy["risk_score"] < home_only["risk_score"]
    assert noisy["low_confidence_event_count"] == 10
    assert noisy["risk_priority_score"] < home_only["risk_priority_score"]
    assert home_only["home_area_only_trace"] == 1


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


def test_daily_summary_counts_unknown_field_as_unmatched_event() -> None:
    event_risk = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "risk_level": "需覆核",
                "risk_score": 0,
                "review_score": 4,
                "location_class": "unknown_field",
                "risk_reason_codes": "unknown_field",
            },
            {
                "event_uid": "e2",
                "attendance_uid": "a1",
                "risk_level": "正常",
                "risk_score": 0,
                "review_score": 0,
                "location_class": "existing_client_visit",
                "risk_reason_codes": "",
            },
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "User A",
                "department": "Sales",
                "work_date": "2026-05-08",
                "gps_event_count": 2,
            }
        ]
    )

    daily = RiskService(make_config()).build_daily_risk_summary(event_risk, attendance)
    employee = RiskService(make_config()).build_employee_risk_summary(daily)

    assert daily.iloc[0]["unmatched_event_count"] == 1
    assert employee.iloc[0]["unmatched_event_count"] == 1


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
