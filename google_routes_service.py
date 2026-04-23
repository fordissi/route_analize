from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests


NOW_FMT = "%Y-%m-%d %H:%M:%S"
COMPUTE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FREE_CAP_ESSENTIALS = 10_000
CACHE_COORD_PRECISION = 4


def normalize_coord_precision(coord_precision: int | None) -> int:
    if coord_precision is None:
        return CACHE_COORD_PRECISION
    return max(2, min(int(coord_precision), 6))


def _now_text() -> str:
    return datetime.now().strftime(NOW_FMT)


def parse_duration_seconds(value: str | None) -> float:
    if not value:
        return 0.0
    text = str(value).strip()
    if text.endswith("s"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return 0.0


def build_cache_key(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
    travel_mode: str,
    routing_preference: str,
    coord_precision: int | None = None,
) -> str:
    precision = normalize_coord_precision(coord_precision)
    raw = "|".join(
        [
            f"{origin_lat:.{precision}f}",
            f"{origin_lon:.{precision}f}",
            f"{destination_lat:.{precision}f}",
            f"{destination_lon:.{precision}f}",
            travel_mode,
            routing_preference,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class RouteSegment:
    attendance_uid: str
    segment_no: int
    segment_type: str
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    travel_mode: str = "DRIVE"
    routing_preference: str = "TRAFFIC_AWARE"
    coord_precision: int = CACHE_COORD_PRECISION

    @property
    def cache_key(self) -> str:
        return build_cache_key(
            self.origin_lat,
            self.origin_lon,
            self.destination_lat,
            self.destination_lon,
            self.travel_mode,
            self.routing_preference,
            self.coord_precision,
        )

    @property
    def request_payload(self) -> dict[str, Any]:
        return {
            "origin": {"location": {"latLng": {"latitude": self.origin_lat, "longitude": self.origin_lon}}},
            "destination": {"location": {"latLng": {"latitude": self.destination_lat, "longitude": self.destination_lon}}},
            "travelMode": self.travel_mode,
            "routingPreference": self.routing_preference,
            "languageCode": "zh-TW",
            "units": "METRIC",
        }


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(Path(db_path), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout = 60000;")
    conn.execute("PRAGMA foreign_keys = OFF;")
    return conn


def build_attendance_segments(
    attendance_slice: pd.DataFrame,
    raw_events: pd.DataFrame,
    employees: pd.DataFrame,
    route_mode: str,
    coord_precision: int | None = None,
) -> list[RouteSegment]:
    employee_lookup = employees.set_index("employee_id")
    segments: list[RouteSegment] = []
    precision = normalize_coord_precision(coord_precision)
    for _, attendance_row in attendance_slice.iterrows():
        attendance_uid = attendance_row["attendance_uid"]
        event_slice = raw_events.loc[raw_events["attendance_uid"] == attendance_uid].dropna(subset=["gps_lat", "gps_lon"]).copy()
        if event_slice.empty:
            continue
        event_slice = event_slice.sort_values(["actual_time", "source_row_no"])
        points = [(float(row["gps_lat"]), float(row["gps_lon"])) for _, row in event_slice.iterrows()]
        employee = employee_lookup.loc[attendance_row["employee_id"]] if attendance_row["employee_id"] in employee_lookup.index else None
        segment_no = 1

        has_home = (
            employee is not None
            and pd.notna(employee.get("home_lat"))
            and pd.notna(employee.get("home_lon"))
            and route_mode in {"home_based", "hybrid_rule_based"}
        )
        if has_home:
            home_lat = float(employee["home_lat"])
            home_lon = float(employee["home_lon"])
            first_lat, first_lon = points[0]
            segments.append(
                RouteSegment(
                    attendance_uid=attendance_uid,
                    segment_no=segment_no,
                    segment_type="home_to_first",
                    origin_lat=home_lat,
                    origin_lon=home_lon,
                    destination_lat=first_lat,
                    destination_lon=first_lon,
                    coord_precision=precision,
                )
            )
            segment_no += 1

        for first, second in zip(points, points[1:]):
            segments.append(
                RouteSegment(
                    attendance_uid=attendance_uid,
                    segment_no=segment_no,
                    segment_type="between_points",
                    origin_lat=first[0],
                    origin_lon=first[1],
                    destination_lat=second[0],
                    destination_lon=second[1],
                    coord_precision=precision,
                )
            )
            segment_no += 1

        if has_home:
            last_lat, last_lon = points[-1]
            segments.append(
                RouteSegment(
                    attendance_uid=attendance_uid,
                    segment_no=segment_no,
                    segment_type="last_to_home",
                    origin_lat=last_lat,
                    origin_lon=last_lon,
                    destination_lat=home_lat,
                    destination_lon=home_lon,
                    coord_precision=precision,
                )
            )
    return segments


def estimate_monthly_usage(
    attendance_slice: pd.DataFrame,
    raw_events: pd.DataFrame,
    employees: pd.DataFrame,
    route_mode: str,
    coord_precision: int | None = None,
) -> dict[str, Any]:
    precision = normalize_coord_precision(coord_precision)
    segments = build_attendance_segments(attendance_slice, raw_events, employees, route_mode, precision)
    gps_points = int(
        raw_events.loc[raw_events["attendance_uid"].isin(attendance_slice["attendance_uid"]), "gps_lat"].notna().sum()
    )
    return {
        "attendance_days": int(attendance_slice["attendance_uid"].nunique()),
        "employees": int(attendance_slice["employee_id"].nunique()),
        "gps_points": gps_points,
        "route_segments": len(segments),
        "estimated_compute_routes_calls": len(segments),
        "free_cap_essentials": FREE_CAP_ESSENTIALS,
        "free_cap_remaining": max(FREE_CAP_ESSENTIALS - len(segments), 0),
        "free_cap_exceeded": len(segments) > FREE_CAP_ESSENTIALS,
        "coord_precision": precision,
    }


def fetch_cached_segments(conn: sqlite3.Connection, cache_keys: list[str]) -> dict[str, dict[str, Any]]:
    if not cache_keys:
        return {}
    placeholders = ",".join(["?"] * len(cache_keys))
    query = f"""
        SELECT cache_key, distance_meters, duration_seconds, polyline, status
        FROM google_route_cache
        WHERE cache_key IN ({placeholders}) AND status = 'ok'
    """
    rows = conn.execute(query, cache_keys).fetchall()
    return {
        row[0]: {
            "distance_meters": row[1],
            "duration_seconds": row[2],
            "polyline": row[3],
            "status": row[4],
        }
        for row in rows
    }


def fetch_cached_segments_for_segments(
    conn: sqlite3.Connection,
    segments: list[RouteSegment],
) -> dict[str, dict[str, Any]]:
    cached = fetch_cached_segments(conn, [segment.cache_key for segment in segments])
    if len(cached) == len(segments):
        return cached

    fallback_sql = """
        SELECT cache_key, distance_meters, duration_seconds, polyline, status
        FROM google_route_cache
        WHERE status = 'ok'
          AND travel_mode = ?
          AND routing_preference = ?
          AND ABS(origin_lat - ?) < 1e-9
          AND ABS(origin_lon - ?) < 1e-9
          AND ABS(destination_lat - ?) < 1e-9
          AND ABS(destination_lon - ?) < 1e-9
        ORDER BY calculated_at DESC
        LIMIT 1
    """
    for segment in segments:
        if segment.cache_key in cached:
            continue
        row = conn.execute(
            fallback_sql,
            (
                segment.travel_mode,
                segment.routing_preference,
                segment.origin_lat,
                segment.origin_lon,
                segment.destination_lat,
                segment.destination_lon,
            ),
        ).fetchone()
        if not row:
            continue
        cached[segment.cache_key] = {
            "distance_meters": row[1],
            "duration_seconds": row[2],
            "polyline": row[3],
            "status": row[4],
            "matched_by": "coordinate_fallback",
            "matched_cache_key": row[0],
        }
    return cached


def compute_route_via_google(api_key: str, segment: RouteSegment) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline",
    }
    response = requests.post(COMPUTE_ROUTES_URL, headers=headers, json=segment.request_payload, timeout=60)
    response.raise_for_status()
    payload = response.json()
    routes = payload.get("routes", [])
    if not routes:
        raise ValueError("Google Routes API 未回傳可用 routes")
    route = routes[0]
    return {
        "distance_meters": float(route.get("distanceMeters", 0)),
        "duration_seconds": parse_duration_seconds(route.get("duration")),
        "polyline": route.get("polyline", {}).get("encodedPolyline"),
        "response_payload": payload,
    }


def upsert_cache_row(conn: sqlite3.Connection, segment: RouteSegment, result: dict[str, Any]) -> None:
    sql = """
        INSERT OR REPLACE INTO google_route_cache (
            cache_key, attendance_uid, segment_no, segment_type,
            origin_lat, origin_lon, destination_lat, destination_lon,
            travel_mode, routing_preference, distance_meters, duration_seconds,
            polyline, api_provider, request_payload, response_payload,
            status, error_message, calculated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        segment.cache_key,
        segment.attendance_uid,
        segment.segment_no,
        segment.segment_type,
        segment.origin_lat,
        segment.origin_lon,
        segment.destination_lat,
        segment.destination_lon,
        segment.travel_mode,
        segment.routing_preference,
        result.get("distance_meters"),
        result.get("duration_seconds"),
        result.get("polyline"),
        "google_routes_api",
        json.dumps(segment.request_payload, ensure_ascii=False),
        json.dumps(result.get("response_payload"), ensure_ascii=False) if result.get("response_payload") is not None else None,
        result.get("status", "ok"),
        result.get("error_message"),
        _now_text(),
    )
    for attempt in range(5):
        try:
            conn.execute(sql, params)
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 4:
                raise
            time.sleep(0.5 * (attempt + 1))


def upsert_summary_rows(
    conn: sqlite3.Connection,
    attendance_slice: pd.DataFrame,
    employees: pd.DataFrame,
    segment_rows: list[dict[str, Any]],
) -> pd.DataFrame:
    if not segment_rows:
        return pd.DataFrame()
    employee_lookup = employees.set_index("employee_id")
    segment_df = pd.DataFrame(segment_rows)
    attendance_meta = attendance_slice[["attendance_uid", "employee_id"]].copy()
    merged = segment_df.merge(attendance_meta, on="attendance_uid", how="left")
    output_rows: list[dict[str, Any]] = []
    for attendance_uid, group in merged.groupby("attendance_uid"):
        employee_id = group["employee_id"].iloc[0]
        employee = employee_lookup.loc[employee_id] if employee_id in employee_lookup.index else None
        total_km = group["distance_meters"].fillna(0).sum() / 1000.0
        total_min = group["duration_seconds"].fillna(0).sum() / 60.0
        base_commute = float(employee["base_commute_km"]) if employee is not None and pd.notna(employee.get("base_commute_km")) else 0.0
        business_km = max(total_km - (base_commute * 2), 0.0)
        route_start_type = "home" if "home_to_first" in set(group["segment_type"]) else "first_last_gps_only"
        route_end_type = "home" if "last_to_home" in set(group["segment_type"]) else "first_last_gps_only"
        row = {
            "attendance_uid": attendance_uid,
            "route_mode": "google_routes_api",
            "segment_count": int(len(group)),
            "cached_segment_count": int((group["source"] == "cache").sum()),
            "api_segment_count": int((group["source"] == "api").sum()),
            "estimated_total_km": round(total_km, 2),
            "estimated_business_km": round(business_km, 2),
            "estimated_travel_min": round(total_min, 2),
            "route_start_type": route_start_type,
            "route_end_type": route_end_type,
            "route_confidence": 0.98,
            "route_notes": "google_routes_cached",
            "calculated_at": _now_text(),
        }
        output_rows.append(row)
        conn.execute(
            """
            INSERT OR REPLACE INTO google_route_summary (
                attendance_uid, route_mode, segment_count, cached_segment_count, api_segment_count,
                estimated_total_km, estimated_business_km, estimated_travel_min,
                route_start_type, route_end_type, route_confidence, route_notes, calculated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(row.values()),
        )
    return pd.DataFrame(output_rows)


def compute_and_cache_routes(
    db_path: str | Path,
    attendance_slice: pd.DataFrame,
    raw_events: pd.DataFrame,
    employees: pd.DataFrame,
    route_mode: str,
    api_key: str,
    coord_precision: int | None = None,
) -> dict[str, Any]:
    precision = normalize_coord_precision(coord_precision)
    segments = build_attendance_segments(attendance_slice, raw_events, employees, route_mode, precision)
    if not segments:
        return {"summary_rows": pd.DataFrame(), "api_calls": 0, "cache_hits": 0, "segments": 0}

    with get_connection(db_path) as conn:
        cached = fetch_cached_segments_for_segments(conn, segments)
        rows: list[dict[str, Any]] = []
        api_calls = 0
        cache_hits = 0
        for segment in segments:
            if segment.cache_key in cached:
                cache_hits += 1
                row = cached[segment.cache_key]
                rows.append(
                    {
                        "attendance_uid": segment.attendance_uid,
                        "segment_no": segment.segment_no,
                        "segment_type": segment.segment_type,
                        "distance_meters": float(row["distance_meters"] or 0),
                        "duration_seconds": float(row["duration_seconds"] or 0),
                        "source": "cache",
                    }
                )
                continue

            try:
                result = compute_route_via_google(api_key, segment)
                result["status"] = "ok"
                api_calls += 1
            except Exception as exc:  # noqa: BLE001
                result = {
                    "distance_meters": None,
                    "duration_seconds": None,
                    "polyline": None,
                    "response_payload": None,
                    "status": "error",
                    "error_message": str(exc),
                }
            upsert_cache_row(conn, segment, result)
            rows.append(
                {
                    "attendance_uid": segment.attendance_uid,
                    "segment_no": segment.segment_no,
                    "segment_type": segment.segment_type,
                    "distance_meters": float(result["distance_meters"] or 0),
                    "duration_seconds": float(result["duration_seconds"] or 0),
                    "source": "api",
                }
            )

        summary_rows = upsert_summary_rows(conn, attendance_slice, employees, rows)
        conn.commit()
    return {
        "summary_rows": summary_rows,
        "api_calls": api_calls,
        "cache_hits": cache_hits,
        "segments": len(segments),
    }


def rebuild_google_route_summary_from_cache(
    db_path: str | Path,
    attendance_slice: pd.DataFrame,
    raw_events: pd.DataFrame,
    employees: pd.DataFrame,
    route_mode: str,
    coord_precision: int | None = None,
) -> pd.DataFrame:
    precision = normalize_coord_precision(coord_precision)
    segments = build_attendance_segments(attendance_slice, raw_events, employees, route_mode, precision)
    if not segments:
        with get_connection(db_path) as conn:
            conn.execute("DELETE FROM google_route_summary")
            conn.commit()
        return pd.DataFrame()

    expected_count_by_uid: dict[str, int] = {}
    for segment in segments:
        expected_count_by_uid[segment.attendance_uid] = expected_count_by_uid.get(segment.attendance_uid, 0) + 1

    with get_connection(db_path) as conn:
        cached = fetch_cached_segments_for_segments(conn, segments)
        rows: list[dict[str, Any]] = []
        cached_count_by_uid: dict[str, int] = {}
        for segment in segments:
            row = cached.get(segment.cache_key)
            if not row:
                continue
            rows.append(
                {
                    "attendance_uid": segment.attendance_uid,
                    "segment_no": segment.segment_no,
                    "segment_type": segment.segment_type,
                    "distance_meters": float(row["distance_meters"] or 0),
                    "duration_seconds": float(row["duration_seconds"] or 0),
                    "source": "cache",
                }
            )
            cached_count_by_uid[segment.attendance_uid] = cached_count_by_uid.get(segment.attendance_uid, 0) + 1

        complete_uids = {
            attendance_uid
            for attendance_uid, expected_count in expected_count_by_uid.items()
            if cached_count_by_uid.get(attendance_uid, 0) == expected_count
        }
        complete_rows = [row for row in rows if row["attendance_uid"] in complete_uids]
        current_uids = attendance_slice["attendance_uid"].dropna().astype(str).unique().tolist()
        if current_uids:
            placeholders = ",".join(["?"] * len(current_uids))
            conn.execute(f"DELETE FROM google_route_summary WHERE attendance_uid IN ({placeholders})", current_uids)
        summary_rows = upsert_summary_rows(conn, attendance_slice, employees, complete_rows)
        conn.commit()
        return summary_rows


def load_google_route_summary(db_path: str | Path) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        try:
            return pd.read_sql_query("SELECT * FROM google_route_summary", conn)
        except Exception:  # noqa: BLE001
            return pd.DataFrame()


def load_google_route_cache(db_path: str | Path) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        try:
            return pd.read_sql_query(
                """
                SELECT attendance_uid, segment_no, segment_type, polyline, distance_meters, duration_seconds, status
                FROM google_route_cache
                WHERE status = 'ok'
                ORDER BY attendance_uid, segment_no
                """,
                conn,
            )
        except Exception:  # noqa: BLE001
            return pd.DataFrame()


def load_google_route_cache_detail(db_path: str | Path) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        try:
            return pd.read_sql_query(
                """
                SELECT attendance_uid, segment_no, segment_type, polyline, distance_meters,
                       duration_seconds, status, error_message, calculated_at
                FROM google_route_cache
                ORDER BY attendance_uid, segment_no, calculated_at DESC
                """,
                conn,
            )
        except Exception:  # noqa: BLE001
            return pd.DataFrame()
