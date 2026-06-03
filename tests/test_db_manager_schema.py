import sqlite3

import pandas as pd

from db_manager import DatabaseManager


def table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")]


def test_initialize_creates_risk_review_tables(tmp_path):
    db_path = tmp_path / "risk.sqlite"

    DatabaseManager(db_path).initialize()

    with sqlite3.connect(db_path) as conn:
        assert table_columns(conn, "event_risk_review") == [
            "event_uid",
            "attendance_uid",
            "risk_level",
            "risk_score",
            "risk_reason_codes",
            "risk_reason_text",
            "selected_distance_m",
            "nearest_distance_m",
            "distance_gap_m",
            "selected_rank",
            "distance_from_home_m",
        ]
        assert table_columns(conn, "daily_risk_summary") == [
            "attendance_uid",
            "employee_id",
            "employee_name",
            "department",
            "work_date",
            "gps_event_count",
            "risk_score",
            "risk_priority_score",
            "risk_priority_rate",
            "risk_rate",
            "review_event_count",
            "high_risk_event_count",
            "low_confidence_event_count",
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
            "home_near_event_count",
            "max_distance_from_home_m",
            "field_visit_count",
            "risk_level",
            "risk_reason_summary",
        ]
        assert table_columns(conn, "employee_risk_summary") == [
            "employee_id",
            "employee_name",
            "department",
            "attendance_days",
            "gps_event_count",
            "risk_score",
            "risk_priority_score",
            "risk_priority_rate",
            "risk_rate",
            "review_rate",
            "review_event_count",
            "high_risk_event_count",
            "low_confidence_event_count",
            "home_area_only_days",
            "home_start_end_without_field_days",
            "insufficient_route_evidence_days",
            "risk_level",
        ]


def test_replace_table_preserves_risk_table_primary_key(tmp_path):
    db_path = tmp_path / "risk.sqlite"
    db = DatabaseManager(db_path)
    db.initialize()

    daily_risk = pd.DataFrame(
        [
            {
                "attendance_uid": "E001_2026-04-15_1_batch",
                "employee_id": "E001",
                "employee_name": "User",
                "department": "Sales",
                "work_date": "2026-04-15",
                "gps_event_count": 1,
                "risk_score": 0.0,
                "risk_rate": 0.0,
                "review_event_count": 0,
                "high_risk_event_count": 0,
                "home_area_only_trace": 0,
                "home_start_end_without_field_trace": 0,
                "insufficient_route_evidence": 0,
                "home_near_event_count": 0,
                "max_distance_from_home_m": 0.0,
                "field_visit_count": 0,
                "risk_level": "normal",
                "risk_reason_summary": "",
            }
        ]
    )

    with db.connect() as conn:
        db.replace_table(conn, "daily_risk_summary", daily_risk)
        table_info = conn.execute("PRAGMA table_info(daily_risk_summary)").fetchall()
        rows = conn.execute("SELECT attendance_uid, risk_level FROM daily_risk_summary").fetchall()

    pk_by_column = {row[1]: row[5] for row in table_info}
    assert pk_by_column["attendance_uid"] == 1
    assert rows == [("E001_2026-04-15_1_batch", "normal")]
