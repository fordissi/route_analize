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

    clock_reasons = result.loc[result["event_uid"] == "clock", "risk_reason_codes"].iloc[0]
    e2_reasons = result.loc[result["event_uid"] == "e2", "risk_reason_codes"].iloc[0]
    assert "impossible_travel_time" not in clock_reasons
    assert "impossible_travel_time" in e2_reasons
