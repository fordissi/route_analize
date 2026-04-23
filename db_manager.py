from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS employee_master (
    employee_id TEXT PRIMARY KEY,
    employee_name TEXT,
    home_lon REAL,
    home_lat REAL,
    office_lon REAL,
    office_lat REAL,
    base_commute_km REAL,
    base_commute_rule TEXT,
    fuel_rate_override REAL,
    maintenance_rate_override REAL,
    job_grade TEXT,
    department_default TEXT,
    is_active INTEGER,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS hospital_master_raw (
    hospital_id TEXT,
    hospital_name TEXT,
    phone TEXT,
    city_district TEXT,
    address TEXT,
    specialty TEXT,
    response_address TEXT,
    lon REAL,
    lat REAL,
    source_status TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS hospital_master_clean (
    hospital_id TEXT PRIMARY KEY,
    hospital_name TEXT,
    address TEXT,
    normalized_address TEXT,
    specialty TEXT,
    lon REAL,
    lat REAL,
    city_district TEXT,
    source_status TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS client_master (
    hospital_id TEXT PRIMARY KEY,
    client_name TEXT,
    client_status TEXT,
    source_status TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS raw_check_events (
    event_uid TEXT PRIMARY KEY,
    import_batch_id TEXT,
    source_sheet TEXT,
    source_row_no INTEGER,
    group_no TEXT,
    employee_id TEXT,
    employee_name TEXT,
    department TEXT,
    work_date TEXT,
    scheduled_time TEXT,
    actual_time TEXT,
    card_type TEXT,
    gps_raw TEXT,
    gps_lat REAL,
    gps_lon REAL,
    compare_result TEXT,
    exception_action TEXT,
    source_type TEXT,
    note TEXT,
    overtime_flag TEXT,
    overtime_reason TEXT,
    overtime_comment TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS attendance_day_group (
    attendance_uid TEXT PRIMARY KEY,
    import_batch_id TEXT,
    group_no TEXT,
    employee_id TEXT,
    work_date TEXT,
    department TEXT,
    event_count INTEGER,
    gps_event_count INTEGER,
    first_actual_time TEXT,
    last_actual_time TEXT,
    first_card_time TEXT,
    last_card_time TEXT,
    compare_result_summary TEXT,
    source_quality_status TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS route_stop_match (
    stop_match_uid TEXT PRIMARY KEY,
    event_uid TEXT,
    attendance_uid TEXT,
    seq_no INTEGER,
    candidate_rank INTEGER,
    hospital_id TEXT,
    beeline_meter REAL,
    match_score REAL,
    is_existing_client INTEGER,
    is_selected INTEGER,
    selected_by TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS daily_route_summary (
    attendance_uid TEXT PRIMARY KEY,
    route_mode TEXT,
    route_start_type TEXT,
    route_end_type TEXT,
    total_stop_count INTEGER,
    matched_stop_count INTEGER,
    estimated_total_km REAL,
    estimated_business_km REAL,
    estimated_travel_min REAL,
    route_confidence REAL,
    route_notes TEXT,
    rule_version TEXT,
    calculated_at TEXT
);

CREATE TABLE IF NOT EXISTS finance_audit_result (
    attendance_uid TEXT PRIMARY KEY,
    employee_claim_km REAL,
    base_commute_deduction_km REAL,
    approved_business_km REAL,
    km_variance_pct REAL,
    audit_light TEXT,
    fuel_rate REAL,
    fuel_subsidy REAL,
    maintenance_base REAL,
    maintenance_rate REAL,
    maintenance_subsidy REAL,
    per_diem_amount REAL,
    audit_status TEXT,
    reviewer_note TEXT,
    rule_version TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS manual_override_log (
    override_id TEXT PRIMARY KEY,
    target_table TEXT,
    target_id TEXT,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    override_reason TEXT,
    override_by TEXT,
    override_at TEXT
);

CREATE TABLE IF NOT EXISTS google_route_cache (
    cache_key TEXT PRIMARY KEY,
    attendance_uid TEXT,
    attendance_key TEXT,
    segment_no INTEGER,
    segment_type TEXT,
    origin_lat REAL,
    origin_lon REAL,
    destination_lat REAL,
    destination_lon REAL,
    travel_mode TEXT,
    routing_preference TEXT,
    distance_meters REAL,
    duration_seconds REAL,
    polyline TEXT,
    api_provider TEXT,
    request_payload TEXT,
    response_payload TEXT,
    status TEXT,
    error_message TEXT,
    calculated_at TEXT
);

CREATE TABLE IF NOT EXISTS google_route_summary (
    attendance_uid TEXT PRIMARY KEY,
    attendance_key TEXT,
    route_mode TEXT,
    segment_count INTEGER,
    cached_segment_count INTEGER,
    api_segment_count INTEGER,
    estimated_total_km REAL,
    estimated_business_km REAL,
    estimated_travel_min REAL,
    route_start_type TEXT,
    route_end_type TEXT,
    route_confidence REAL,
    route_notes TEXT,
    calculated_at TEXT
);
"""


class DatabaseManager:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=60)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout = 60000;")
        conn.execute("PRAGMA foreign_keys = OFF;")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate_route_tables(conn)

    def replace_table(self, conn: sqlite3.Connection, table_name: str, dataframe) -> None:
        dataframe.to_sql(table_name, conn, if_exists="replace", index=False)

    def execute(self, conn: sqlite3.Connection, sql: str, params: tuple = ()) -> None:
        conn.execute(sql, params)

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
        if column_name not in existing:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")

    def _derive_attendance_key(self, attendance_uid: str | None) -> str | None:
        if not attendance_uid:
            return None
        parts = str(attendance_uid).split("_")
        if len(parts) < 3:
            return None
        return "_".join(parts[:3])

    def _migrate_route_tables(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(conn, "google_route_cache", "attendance_key", "TEXT")
        self._ensure_column(conn, "google_route_summary", "attendance_key", "TEXT")

        cache_rows = conn.execute(
            "SELECT cache_key, attendance_uid, attendance_key FROM google_route_cache"
        ).fetchall()
        for cache_key, attendance_uid, attendance_key in cache_rows:
            derived = attendance_key or self._derive_attendance_key(attendance_uid)
            if derived and derived != attendance_key:
                conn.execute(
                    "UPDATE google_route_cache SET attendance_key = ? WHERE cache_key = ?",
                    (derived, cache_key),
                )

        summary_rows = conn.execute(
            "SELECT attendance_uid, attendance_key FROM google_route_summary"
        ).fetchall()
        for attendance_uid, attendance_key in summary_rows:
            derived = attendance_key or self._derive_attendance_key(attendance_uid)
            if derived and derived != attendance_key:
                conn.execute(
                    "UPDATE google_route_summary SET attendance_key = ? WHERE attendance_uid = ?",
                    (derived, attendance_uid),
                )
