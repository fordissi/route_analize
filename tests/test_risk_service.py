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
