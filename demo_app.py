from __future__ import annotations

import json
from io import StringIO
from math import cos, log, radians
import os
import shutil
import subprocess

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from pathlib import Path

from pipeline import run_pipeline
from settings import build_config, config_to_editable_dict, save_user_settings
from google_routes_service import (
    build_attendance_segments,
    compute_and_cache_routes,
    estimate_monthly_usage,
    load_google_route_cache,
    load_google_route_cache_detail,
    load_google_route_summary,
)


st.set_page_config(page_title="Function Route Report", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(12,74,110,0.10), transparent 26%),
            linear-gradient(180deg, #f8fafc 0%, #eef4f7 100%);
        color: #0f172a;
    }
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.98);
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 16px;
        padding: 0.8rem 1rem;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
    }
    div[data-testid="stMetric"] label, div[data-testid="stMetric"] div {
        color: #0f172a !important;
    }
    div[data-testid="stDataFrame"] {
        background: rgba(255, 255, 255, 0.96);
        border-radius: 16px;
        padding: 0.35rem;
    }
    label, [data-testid="stWidgetLabel"], .stMarkdown, .stCaption, .stText {
        color: #0f172a !important;
    }
    [data-testid="stWidgetLabel"] p, label p {
        color: #0f172a !important;
        font-weight: 600 !important;
    }
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"],
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextInput"] input,
    div[data-testid="stDateInput"] input,
    textarea {
        background: rgba(255,255,255,0.97) !important;
        color: #0f172a !important;
    }
    label, .stMarkdown, .stCaption, .stText, .stSelectbox label, .stNumberInput label, .stTextInput label, .stCheckbox label {
        color: #0f172a !important;
    }
    div[data-baseweb="select"] *, div[data-testid="stNumberInput"] *, div[data-testid="stTextInput"] * {
        color: #0f172a;
    }
    div[data-baseweb="input"], div[data-baseweb="select"] > div {
        background: rgba(255,255,255,0.96) !important;
    }
    .hero-card {
        background: linear-gradient(135deg, #0f3d5e 0%, #1d4d73 52%, #0f766e 100%);
        color: white;
        padding: 1.2rem 1.35rem;
        border-radius: 20px;
        margin-bottom: 1rem;
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.18);
    }
    .hero-title {
        font-size: 1.45rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    .hero-subtitle {
        font-size: 0.96rem;
        opacity: 0.92;
    }
    .candidate-card {
        background: rgba(255,255,255,0.98);
        border: 1px solid rgba(15,23,42,0.08);
        border-left: 6px solid #0f766e;
        border-radius: 16px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 10px 26px rgba(15,23,42,0.05);
    }
    .candidate-title {
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.35rem;
    }
    .candidate-sub {
        color: #475569;
        font-size: 0.92rem;
        margin-bottom: 0.45rem;
    }
    .candidate-list {
        margin: 0.35rem 0 0 0;
        padding-left: 1rem;
        color: #0f172a;
    }
    .candidate-list li {
        margin-bottom: 0.22rem;
    }
    .candidate-panel-header {
        background: rgba(255,255,255,0.96);
        border: 1px solid rgba(15,23,42,0.08);
        border-radius: 16px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 10px 24px rgba(15,23,42,0.05);
    }
    .section-card {
        background: rgba(255,255,255,0.96);
        border: 1px solid rgba(15,23,42,0.08);
        border-radius: 18px;
        padding: 0.6rem 0.75rem 0.75rem 0.75rem;
        box-shadow: 0 10px 24px rgba(15,23,42,0.05);
    }
    .daily-map-card {
        background: rgba(255,255,255,0.96);
        border: 1px solid rgba(15,23,42,0.08);
        border-radius: 18px;
        padding: 0.45rem;
        box-shadow: 0 10px 24px rgba(15,23,42,0.05);
    }
    .tag-client {
        display: inline-block;
        background: #fee2e2;
        color: #b91c1c;
        border-radius: 999px;
        padding: 0.12rem 0.5rem;
        font-size: 0.82rem;
        font-weight: 700;
        margin-left: 0.35rem;
    }
    .tag-potential {
        display: inline-block;
        background: #fef3c7;
        color: #92400e;
        border-radius: 999px;
        padding: 0.12rem 0.5rem;
        font-size: 0.82rem;
        font-weight: 700;
        margin-left: 0.35rem;
    }
    .tag-hospital {
        display: inline-block;
        background: #dbeafe;
        color: #1d4ed8;
        border-radius: 999px;
        padding: 0.12rem 0.5rem;
        font-size: 0.82rem;
        font-weight: 700;
        margin-left: 0.35rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.3rem;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(255,255,255,0.7);
        border-radius: 12px 12px 0 0;
        color: #334155;
        padding-left: 0.9rem;
        padding-right: 0.9rem;
    }
    .stTabs [aria-selected="true"] {
        color: #0f3d5e !important;
        font-weight: 700;
    }
    .stButton > button {
        background: linear-gradient(135deg, #f8fbff 0%, #e8f0f7 100%);
        color: #0f3d5e !important;
        border: 1px solid rgba(15, 61, 94, 0.18);
        border-radius: 14px;
        font-weight: 700;
        min-height: 48px;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #eaf4ff 0%, #dbeaf7 100%);
        border-color: rgba(15, 61, 94, 0.28);
        color: #0b2f49 !important;
    }
    .stButton > button:focus {
        color: #0b2f49 !important;
        border-color: rgba(15, 61, 94, 0.35);
        box-shadow: 0 0 0 0.1rem rgba(37, 99, 235, 0.12);
    }
    div[data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #f8fbff 0%, #e8f0f7 100%) !important;
        color: #0f3d5e !important;
        border: 1px solid rgba(15, 61, 94, 0.18) !important;
        border-radius: 14px !important;
        font-weight: 700 !important;
        min-height: 48px !important;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05) !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background: linear-gradient(135deg, #eaf4ff 0%, #dbeaf7 100%) !important;
        border-color: rgba(15, 61, 94, 0.28) !important;
        color: #0b2f49 !important;
    }
    div[data-testid="stDownloadButton"] > button:focus {
        color: #0b2f49 !important;
        border-color: rgba(15, 61, 94, 0.35) !important;
        box-shadow: 0 0 0 0.1rem rgba(37, 99, 235, 0.12) !important;
    }
    div[data-testid="stNumberInput"] button,
    div[data-baseweb="input"] button {
        background: linear-gradient(135deg, #f8fbff 0%, #e8f0f7 100%) !important;
        color: #0f3d5e !important;
        border-left: 1px solid rgba(15, 61, 94, 0.18) !important;
        box-shadow: none !important;
    }
    div[data-testid="stNumberInput"] button:hover,
    div[data-baseweb="input"] button:hover {
        background: linear-gradient(135deg, #eaf4ff 0%, #dbeaf7 100%) !important;
        color: #0b2f49 !important;
    }
    div[data-testid="stNumberInput"] button svg,
    div[data-baseweb="input"] button svg {
        fill: #0f3d5e !important;
        color: #0f3d5e !important;
    }
    @media print {
        @page {
            size: A4 portrait;
            margin: 12mm;
        }
        .hero-card,
        .candidate-card,
        .candidate-panel-header,
        .section-card,
        .daily-map-card,
        div[data-testid="stMetric"],
        div[data-testid="stDataFrame"] {
            break-inside: avoid;
            page-break-inside: avoid;
            box-shadow: none !important;
        }
        .block-container {
            max-width: none;
            padding-top: 0;
            padding-bottom: 0;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    buffer = StringIO()
    dataframe.to_csv(buffer, index=False, encoding="utf-8-sig")
    return buffer.getvalue().encode("utf-8-sig")


def compute_zoom(latitudes: list[float], longitudes: list[float]) -> float:
    if not latitudes or not longitudes:
        return 6.0
    lat_span = max(latitudes) - min(latitudes)
    lon_span = max(longitudes) - min(longitudes)
    center_lat = sum(latitudes) / len(latitudes)
    lon_span_adjusted = lon_span * max(abs(cos(radians(center_lat))), 0.2)
    max_span = max(lat_span, lon_span_adjusted)
    if max_span <= 0.001:
        return 14.2
    if max_span <= 0.005:
        return 13.0
    if max_span <= 0.01:
        return 12.0
    if max_span <= 0.03:
        return 10.8
    if max_span <= 0.08:
        return 9.8
    if max_span <= 0.2:
        return 8.6
    if max_span <= 0.5:
        return 7.4
    zoom = 7.2 - log(max(max_span, 1e-6) * 70, 2)
    return float(min(max(zoom, 3.2), 14.2))


def make_employee_label(employee_id: str, employee_name: str) -> str:
    return f"{employee_id} {employee_name}".strip()


def is_hospital_name(
    name: object,
    hospital_keywords: tuple[str, ...] | list[str] | None = None,
    exclude_keywords: tuple[str, ...] | list[str] | None = None,
) -> bool:
    text = str(name or "").strip()
    if not text:
        return False
    include = tuple(hospital_keywords or ("醫院", "衛生所", "療養院"))
    exclude = tuple(exclude_keywords or ("診所", "藥局"))
    return any(keyword in text for keyword in include) and not any(keyword in text for keyword in exclude)

def chunked(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def build_attendance_event_flags(raw_events: pd.DataFrame) -> pd.DataFrame:
    if raw_events.empty:
        return pd.DataFrame(
            columns=[
                "attendance_uid",
                "missing_punch_count",
                "missing_punch_unprocessed_count",
                "missing_punch_processed_count",
                "forget_punch_application_count",
                "missing_punch_unprocessed_flag",
                "overtime_flag_bool",
                "actual_overtime_flag",
                "personal_overtime_flag",
            ]
        )

    work = raw_events.copy()
    work["compare_result"] = work["compare_result"].fillna("").astype(str).str.strip()
    work["exception_action"] = work["exception_action"].fillna("").astype(str).str.strip()
    work["source_type"] = work["source_type"].fillna("").astype(str).str.strip()
    work["overtime_flag"] = work["overtime_flag"].fillna("").astype(str).str.strip()
    work["overtime_reason"] = work["overtime_reason"].fillna("").astype(str).str.strip()

    work["missing_punch_flag"] = work["compare_result"].eq("未打卡")
    work["missing_punch_unprocessed_flag"] = work["missing_punch_flag"] & work["exception_action"].eq("待處理")
    work["missing_punch_processed_flag"] = work["missing_punch_flag"] & work["exception_action"].eq("已處理")
    work["forget_punch_application_flag"] = work["source_type"].eq("忘刷申請")
    work["overtime_event_flag"] = work["overtime_flag"].eq("*")
    work["actual_overtime_event_flag"] = work["overtime_event_flag"] & work["overtime_reason"].eq("實際加班")
    work["personal_overtime_event_flag"] = work["overtime_event_flag"] & work["overtime_reason"].eq("個人因素")

    grouped = (
        work.groupby("attendance_uid", dropna=False)
        .agg(
            missing_punch_count=("missing_punch_flag", "sum"),
            missing_punch_unprocessed_count=("missing_punch_unprocessed_flag", "sum"),
            missing_punch_processed_count=("missing_punch_processed_flag", "sum"),
            forget_punch_application_count=("forget_punch_application_flag", "sum"),
            missing_punch_unprocessed_flag=("missing_punch_unprocessed_flag", "max"),
            overtime_flag_bool=("overtime_event_flag", "max"),
            actual_overtime_flag=("actual_overtime_event_flag", "max"),
            personal_overtime_flag=("personal_overtime_event_flag", "max"),
        )
        .reset_index()
    )
    return grouped


def build_commute_estimate(
    attendance_row: pd.Series,
    day_events: pd.DataFrame,
    employee_row: pd.Series | None,
    day_google_segments: pd.DataFrame,
    config,
) -> dict[str, float]:
    result = {"commute_km": 0.0, "commute_min": 0.0}
    if employee_row is None or day_events.empty:
        return result
    home_lat = employee_row.get("home_lat")
    home_lon = employee_row.get("home_lon")
    if pd.isna(home_lat) or pd.isna(home_lon):
        return result

    attendance_key = attendance_row.get("attendance_key")
    segment_slice = day_google_segments.copy() if isinstance(day_google_segments, pd.DataFrame) else pd.DataFrame()
    if not segment_slice.empty:
        if "attendance_key" not in segment_slice.columns:
            segment_slice["attendance_key"] = segment_slice["attendance_uid"].astype("string").str.split("_").str[:3].str.join("_")
        segment_slice = segment_slice.loc[segment_slice["attendance_key"] == attendance_key].copy()
        if not segment_slice.empty and {"segment_type", "distance_meters", "duration_seconds"}.issubset(segment_slice.columns):
            commute_segments = segment_slice.loc[segment_slice["segment_type"].isin(["home_to_first", "last_to_home"])].copy()
            if not commute_segments.empty:
                result["commute_km"] = float(commute_segments["distance_meters"].fillna(0).sum()) / 1000.0
                result["commute_min"] = float(commute_segments["duration_seconds"].fillna(0).sum()) / 60.0
                return result

    gps_events = day_events.dropna(subset=["gps_lat", "gps_lon"]).sort_values(["actual_time", "source_row_no"])
    if gps_events.empty:
        return result

    first_event = gps_events.iloc[0]
    last_event = gps_events.iloc[-1]
    first_leg_m = float(haversine_m(float(home_lat), float(home_lon), np.array([first_event["gps_lat"]]), np.array([first_event["gps_lon"]]))[0])
    last_leg_m = float(haversine_m(float(last_event["gps_lat"]), float(last_event["gps_lon"]), np.array([home_lat]), np.array([home_lon]))[0])
    commute_km = ((first_leg_m + last_leg_m) / 1000.0) * float(config.detour_index)
    commute_min = (commute_km / max(float(config.average_speed_kmph), 1.0)) * 60.0
    result["commute_km"] = commute_km
    result["commute_min"] = commute_min
    return result


def build_google_routes_diagnostics(
    attendance_slice: pd.DataFrame,
    raw_events: pd.DataFrame,
    employees: pd.DataFrame,
    route_mode: str,
    coord_precision: int,
    google_route_summary: pd.DataFrame,
    google_route_cache_detail: pd.DataFrame,
) -> pd.DataFrame:
    if attendance_slice.empty:
        return pd.DataFrame()

    attendance_meta = attendance_slice[
        ["attendance_uid", "attendance_key", "employee_id", "employee_label", "work_date"]
    ].drop_duplicates().copy()
    attendance_meta["work_date"] = pd.to_datetime(attendance_meta["work_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    expected_segments = build_attendance_segments(
        attendance_slice=attendance_slice,
        raw_events=raw_events,
        employees=employees,
        route_mode=route_mode,
        coord_precision=coord_precision,
    )

    if not expected_segments:
        diagnostics = attendance_meta.copy()
        diagnostics["expected_segments"] = 0
        diagnostics["api_success_segments"] = 0
        diagnostics["cache_hit_segments"] = 0
        diagnostics["failed_segments"] = 0
        diagnostics["missing_polyline_segments"] = 0
        diagnostics["diagnosis"] = "無可計算路段"
        diagnostics["last_error_message"] = None
    else:
        expected_df = pd.DataFrame(
            [
                {
                    "attendance_uid": segment.attendance_uid,
                    "attendance_key": segment.attendance_key,
                    "segment_no": segment.segment_no,
                    "segment_type": segment.segment_type,
                }
                for segment in expected_segments
            ]
        )

        cache_detail = google_route_cache_detail.copy() if isinstance(google_route_cache_detail, pd.DataFrame) else pd.DataFrame()
        if not cache_detail.empty:
            if "attendance_key" not in cache_detail.columns:
                cache_detail["attendance_key"] = cache_detail["attendance_uid"].astype("string").str.split("_").str[:3].str.join("_")
            cache_detail = cache_detail.loc[
                cache_detail["attendance_key"].isin(expected_df["attendance_key"])
            ].copy()
            cache_detail["calculated_at"] = pd.to_datetime(cache_detail["calculated_at"], errors="coerce")
            cache_detail = cache_detail.sort_values(["attendance_key", "segment_no", "segment_type", "calculated_at"])
            cache_detail = cache_detail.drop_duplicates(
                subset=["attendance_key", "segment_no", "segment_type"],
                keep="last",
            )
        else:
            cache_detail = pd.DataFrame(
                columns=["attendance_key", "segment_no", "segment_type", "polyline", "status", "error_message", "calculated_at"]
            )

        merged = expected_df.merge(
            cache_detail[
                ["attendance_key", "segment_no", "segment_type", "polyline", "status", "error_message", "calculated_at"]
            ],
            on=["attendance_key", "segment_no", "segment_type"],
            how="left",
        )
        merged["has_polyline"] = merged["polyline"].astype("string").fillna("").str.len() > 0
        merged["status"] = merged["status"].astype("string")
        merged["is_error"] = merged["status"].eq("error")
        merged["is_ok"] = merged["status"].eq("ok")
        merged["is_missing_polyline"] = merged["is_ok"] & ~merged["has_polyline"]

        aggregated = (
            merged.groupby("attendance_key", dropna=False)
            .agg(
                expected_segments=("segment_no", "count"),
                cache_rows=("status", lambda values: int(values.notna().sum())),
                failed_segments=("is_error", lambda values: int(values.sum())),
                missing_polyline_segments=("is_missing_polyline", lambda values: int(values.sum())),
                usable_polyline_segments=("has_polyline", lambda values: int(values.sum())),
                last_error_message=("error_message", lambda values: next((value for value in values if pd.notna(value) and str(value).strip()), None)),
            )
            .reset_index()
        )

        summary_slice = google_route_summary.copy() if isinstance(google_route_summary, pd.DataFrame) else pd.DataFrame()
        if not summary_slice.empty:
            if "attendance_key" not in summary_slice.columns:
                summary_slice["attendance_key"] = summary_slice["attendance_uid"].astype("string").str.split("_").str[:3].str.join("_")
            summary_slice = summary_slice.loc[
                summary_slice["attendance_key"].isin(expected_df["attendance_key"])
            ][["attendance_key", "cached_segment_count", "api_segment_count", "segment_count"]].copy()
            summary_slice = summary_slice.sort_values(["attendance_key"]).drop_duplicates(["attendance_key"], keep="last")
        else:
            summary_slice = pd.DataFrame(columns=["attendance_key", "cached_segment_count", "api_segment_count", "segment_count"])

        diagnostics = attendance_meta.merge(aggregated, on="attendance_key", how="left").merge(summary_slice, on="attendance_key", how="left")
        for column in [
            "expected_segments",
            "failed_segments",
            "missing_polyline_segments",
            "usable_polyline_segments",
            "cached_segment_count",
            "api_segment_count",
            "segment_count",
        ]:
            diagnostics[column] = (
                pd.to_numeric(diagnostics[column].astype("string"), errors="coerce")
                .fillna(0)
                .astype(int)
            )

        diagnostics["api_success_segments"] = diagnostics["api_segment_count"]
        diagnostics["cache_hit_segments"] = np.where(
            diagnostics["cached_segment_count"] > 0,
            diagnostics["cached_segment_count"],
            diagnostics["usable_polyline_segments"],
        )

        def classify(row: pd.Series) -> str:
            if row["failed_segments"] > 0:
                return "有 API 失敗"
            if row["missing_polyline_segments"] > 0:
                return "有段缺 polyline"
            if row["api_success_segments"] > 0 and row["cache_hit_segments"] > 0 and row["usable_polyline_segments"] == row["expected_segments"]:
                return "混合：API + 快取"
            if row["api_success_segments"] > 0 and row["usable_polyline_segments"] == row["expected_segments"]:
                return "API 成功"
            if row["cache_hit_segments"] == row["expected_segments"] and row["expected_segments"] > 0:
                return "只命中快取"
            if row["expected_segments"] > 0 and row["api_success_segments"] == 0 and row["cache_hit_segments"] == 0 and row["failed_segments"] == 0:
                return "尚未執行"
            return "部分完成"

        diagnostics["diagnosis"] = diagnostics.apply(classify, axis=1)

    diagnostics = diagnostics.rename(
        columns={
            "work_date": "日期",
            "employee_id": "員工編號",
            "employee_label": "員工",
            "attendance_uid": "attendance_uid",
            "diagnosis": "診斷結果",
            "expected_segments": "預期路段數",
            "api_success_segments": "API 成功段數",
            "cache_hit_segments": "快取命中段數",
            "failed_segments": "失敗段數",
            "missing_polyline_segments": "缺 polyline 段數",
            "last_error_message": "最後錯誤訊息",
        }
    )
    return diagnostics[
        [
            "日期",
            "員工編號",
            "員工",
            "attendance_uid",
            "attendance_key",
            "診斷結果",
            "預期路段數",
            "API 成功段數",
            "快取命中段數",
            "失敗段數",
            "缺 polyline 段數",
            "最後錯誤訊息",
        ]
    ].sort_values(["日期", "員工編號", "attendance_uid"]).reset_index(drop=True)


def haversine_m(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    earth_radius = 6371000.0
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2.0) ** 2
    return 2.0 * earth_radius * np.arcsin(np.sqrt(a))


def build_nearest_hospital_lookup(raw_events: pd.DataFrame, hospitals: pd.DataFrame, config) -> pd.DataFrame:
    hospital_pool = hospitals.loc[
        hospitals["hospital_name"].apply(lambda name: is_hospital_name(name, config.hospital_keywords, config.hospital_exclude_keywords))
        & hospitals["lat"].notna()
        & hospitals["lon"].notna(),
        ["hospital_name", "lat", "lon"],
    ].copy()
    if hospital_pool.empty:
        return pd.DataFrame(columns=["event_uid", "nearest_hospital_only_name", "nearest_hospital_only_meter"])

    hospital_lats = hospital_pool["lat"].astype(float).to_numpy()
    hospital_lons = hospital_pool["lon"].astype(float).to_numpy()
    hospital_names = hospital_pool["hospital_name"].astype(str).to_numpy()

    rows = []
    for event in raw_events.loc[raw_events["gps_lat"].notna() & raw_events["gps_lon"].notna(), ["event_uid", "gps_lat", "gps_lon"]].itertuples(index=False):
        distances = haversine_m(float(event.gps_lat), float(event.gps_lon), hospital_lats, hospital_lons)
        nearest_idx = int(np.argmin(distances))
        rows.append(
            {
                "event_uid": event.event_uid,
                "nearest_hospital_only_name": hospital_names[nearest_idx],
                "nearest_hospital_only_meter": float(distances[nearest_idx]),
            }
        )
    return pd.DataFrame(rows)


def build_nearest_existing_client_lookup(raw_events: pd.DataFrame, hospitals: pd.DataFrame, clients: pd.DataFrame) -> pd.DataFrame:
    client_ids = set(clients["hospital_id"].dropna().astype(str))
    client_pool = hospitals.loc[
        hospitals["hospital_id"].astype(str).isin(client_ids)
        & hospitals["lat"].notna()
        & hospitals["lon"].notna(),
        ["hospital_id", "hospital_name", "lat", "lon"],
    ].copy()
    if client_pool.empty:
        return pd.DataFrame(columns=["event_uid", "nearest_client_name", "nearest_client_meter"])

    client_lats = client_pool["lat"].astype(float).to_numpy()
    client_lons = client_pool["lon"].astype(float).to_numpy()
    client_names = client_pool["hospital_name"].astype(str).to_numpy()
    rows: list[dict] = []
    for _, event in raw_events.dropna(subset=["gps_lat", "gps_lon"]).iterrows():
        distances = haversine_m(float(event["gps_lat"]), float(event["gps_lon"]), client_lats, client_lons)
        if len(distances) == 0:
            continue
        nearest_idx = int(np.argmin(distances))
        rows.append(
            {
                "event_uid": event["event_uid"],
                "nearest_client_name": client_names[nearest_idx],
                "nearest_client_meter": float(distances[nearest_idx]),
            }
        )
    return pd.DataFrame(rows)


def decode_polyline(polyline_str: str | None) -> list[tuple[float, float]]:
    if not polyline_str:
        return []
    index = 0
    lat = 0
    lng = 0
    coordinates: list[tuple[float, float]] = []
    while index < len(polyline_str):
        shift = 0
        result = 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat

        shift = 0
        result = 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlng = ~(result >> 1) if result & 1 else result >> 1
        lng += dlng
        coordinates.append((lat / 1e5, lng / 1e5))
    return coordinates


def save_csv(dataframe: pd.DataFrame, path: Path) -> None:
    dataframe.to_csv(path, index=False, encoding="utf-8-sig")


def render_editable_source_csv(title: str, file_name: str, key: str, help_text: str) -> None:
    path = Path(__file__).resolve().parent / file_name
    st.markdown(f"**{title}**")
    st.caption(help_text)
    source_df = pd.read_csv(path, encoding="utf-8-sig")
    edited = st.data_editor(source_df, width="stretch", num_rows="dynamic", key=key)
    action_col1, action_col2 = st.columns(2)
    if action_col1.button(f"儲存 {title}", key=f"save_{key}", width="stretch"):
        save_csv(pd.DataFrame(edited), path)
        st.success(f"{title} 已更新：{path.name}")
    action_col2.download_button(
        f"下載 {title}",
        data=to_csv_bytes(pd.DataFrame(edited)),
        file_name=path.name,
        mime="text/csv",
        width="stretch",
        key=f"download_{key}",
    )


def render_attendance_importer() -> None:
    st.markdown("**打卡資料匯入**")
    st.caption("每次上傳的 104 打卡匯出檔都會保留在本機；系統會合併所有已匯入檔案，若日期重複則以最新匯入檔案為準。")
    uploaded = st.file_uploader("選擇打卡匯出檔", type=["xlsx"], key="attendance_upload")
    if uploaded and st.button("匯入打卡資料", key="import_attendance", width="stretch"):
        config = build_config()
        config.attendance_import_dir.mkdir(parents=True, exist_ok=True)
        imported_at = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        target = config.attendance_import_dir / f"attendance_{imported_at}.xlsx"
        target.write_bytes(uploaded.getbuffer())
        manifest_path = config.reports_dir / "attendance_import_manifest.json"
        existing_manifest: dict = {}
        if manifest_path.exists():
            try:
                existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                existing_manifest = {}
        history = existing_manifest.get("imports", [])
        history.append(
            {
                "stored_file_name": target.name,
                "original_file_name": uploaded.name,
                "stored_path": str(target),
                "imported_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        manifest = {
            "active_attendance_file": str(target),
            "stored_file_name": target.name,
            "original_file_name": uploaded.name,
            "updated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "import_file_count": len(history),
            "imports": history,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        st.cache_data.clear()
        st.success(f"已完成打卡檔匯入，已保留檔案：{uploaded.name}")
        st.rerun()

def render_home_action(action: str) -> None:
    if action == "hospitals":
        render_editable_source_csv("醫療院所資料", "hospitals.csv", "edit_hospitals", "可直接編輯醫療院所主檔資料。")
    elif action == "clients":
        render_editable_source_csv("既有客戶資料", "existing_clients.csv", "edit_clients", "可直接維護既有客戶名單。")
    elif action == "employees":
        render_editable_source_csv("員工資料", "employees.csv", "edit_employees", "可直接維護員工主檔，包含住家座標與個別費率欄位。")
    elif action == "attendance":
        render_attendance_importer()
    elif action == "routes":
        st.info("請前往上方的「Google Routes 執行」頁面，先估算月度用量，再決定是否手動執行 Google Routes。")
    elif action == "finance":
        st.markdown("**日當費 / 里程核定**")
        st.caption("此區會預覽目前已產生的財務核定結果，包含里程、油資、維修補貼與日當費。")
        finance_path = Path(__file__).resolve().parent / "outputs" / "cleaned" / "finance_audit_result.csv"
        if not finance_path.exists():
            st.info("目前尚未找到 finance_audit_result.csv，請先重新整理資料或執行主流程。")
        else:
            finance_df = pd.read_csv(finance_path, encoding="utf-8-sig")
            preview_cols = [
                column
                for column in [
                    "attendance_uid",
                    "approved_business_km",
                    "fuel_subsidy",
                    "maintenance_subsidy",
                    "per_diem_amount",
                    "audit_status",
                    "audit_light",
                ]
                if column in finance_df.columns
            ]
            st.dataframe(finance_df[preview_cols], width="stretch", hide_index=True)



@st.cache_data(show_spinner=False)
def load_results():
    config = build_config(root_dir=Path(__file__).resolve().parent / 'demo_data')
    base = config.cleaned_dir
    attendance = pd.read_csv(base / "attendance_day_group.csv", encoding="utf-8-sig")
    routes = pd.read_csv(base / "daily_route_summary.csv", encoding="utf-8-sig")
    finance = pd.read_csv(base / "finance_audit_result.csv", encoding="utf-8-sig")
    daily_metrics = pd.read_csv(base / "bi_daily_metrics.csv", encoding="utf-8-sig")
    raw_events = pd.read_csv(base / "raw_check_events.csv", encoding="utf-8-sig")
    matches = pd.read_csv(base / "route_stop_match.csv", encoding="utf-8-sig", low_memory=False)
    hospitals = pd.read_csv(base / "hospital_master_clean.csv", encoding="utf-8-sig")
    clients = pd.read_csv(base / "client_master.csv", encoding="utf-8-sig")
    employees = pd.read_csv(base / "employee_master.csv", encoding="utf-8-sig")

    raw_events["work_date"] = pd.to_datetime(raw_events["work_date"], errors="coerce")
    attendance["work_date"] = pd.to_datetime(attendance["work_date"], errors="coerce")
    daily_metrics["work_date"] = pd.to_datetime(daily_metrics["work_date"], errors="coerce")
    for column in ["actual_time", "scheduled_time"]:
        raw_events[column] = pd.to_datetime(raw_events[column], errors="coerce")
    if "attendance_uid" not in raw_events.columns:
        attendance_key = attendance[["attendance_uid", "employee_id", "work_date", "group_no"]].copy()
        raw_events = raw_events.merge(attendance_key, on=["employee_id", "work_date", "group_no"], how="left")

    employee_names = (
        raw_events[["employee_id", "employee_name", "department"]]
        .dropna(subset=["employee_id"])
        .drop_duplicates(subset=["employee_id"], keep="first")
    )
    employee_names["employee_label"] = employee_names.apply(
        lambda row: make_employee_label(row["employee_id"], row["employee_name"]),
        axis=1,
    )
    employees = employees.merge(employee_names[["employee_id", "employee_name", "employee_label"]], on="employee_id", how="left")
    employees["employee_name"] = employees["employee_name_y"].fillna(employees["employee_name_x"])
    employees["employee_label"] = employees["employee_label"].fillna(
        employees.apply(lambda row: make_employee_label(row["employee_id"], row["employee_name"]), axis=1)
    )
    employees = employees.drop(columns=["employee_name_x", "employee_name_y"], errors="ignore")

    attendance = attendance.merge(employee_names[["employee_id", "employee_name", "employee_label"]], on="employee_id", how="left")
    daily_metrics = daily_metrics.merge(employee_names[["employee_id", "employee_name", "employee_label"]], on="employee_id", how="left")
    routes = routes.merge(attendance[["attendance_uid", "employee_id", "employee_name", "employee_label", "work_date"]], on="attendance_uid", how="left")
    finance = finance.merge(attendance[["attendance_uid", "employee_id", "employee_name", "employee_label", "work_date"]], on="attendance_uid", how="left")
    if "attendance_key" not in routes.columns:
        routes = routes.merge(attendance[["attendance_uid", "attendance_key"]], on="attendance_uid", how="left")
    if "attendance_key" not in finance.columns:
        finance = finance.merge(attendance[["attendance_uid", "attendance_key"]], on="attendance_uid", how="left")
    google_route_summary = load_google_route_summary(config.sqlite_path)
    google_route_cache = load_google_route_cache(config.sqlite_path)
    google_route_cache_detail = load_google_route_cache_detail(config.sqlite_path)
    if not google_route_summary.empty:
        if "attendance_key" not in google_route_summary.columns:
            google_route_summary["attendance_key"] = google_route_summary["attendance_uid"].astype("string").str.split("_").str[:3].str.join("_")
        routes = routes.merge(
            google_route_summary[
                [
                    "attendance_key",
                    "route_mode",
                    "estimated_total_km",
                    "estimated_business_km",
                    "estimated_travel_min",
                    "route_start_type",
                    "route_end_type",
                    "route_confidence",
                    "route_notes",
                ]
            ].rename(
                columns={
                    "route_mode": "google_route_mode",
                    "estimated_total_km": "google_estimated_total_km",
                    "estimated_business_km": "google_estimated_business_km",
                    "estimated_travel_min": "google_estimated_travel_min",
                    "route_start_type": "google_route_start_type",
                    "route_end_type": "google_route_end_type",
                    "route_confidence": "google_route_confidence",
                    "route_notes": "google_route_notes",
                }
            ),
            on="attendance_key",
            how="left",
        )
        for base_col, google_col in [
            ("route_mode", "google_route_mode"),
            ("estimated_total_km", "google_estimated_total_km"),
            ("estimated_business_km", "google_estimated_business_km"),
            ("estimated_travel_min", "google_estimated_travel_min"),
            ("route_start_type", "google_route_start_type"),
            ("route_end_type", "google_route_end_type"),
            ("route_confidence", "google_route_confidence"),
            ("route_notes", "google_route_notes"),
        ]:
            routes[base_col] = routes[google_col].combine_first(routes[base_col])

    hospital_lookup = hospitals[["hospital_id", "hospital_name", "address"]].copy()
    client_ids = set(clients["hospital_id"].astype(str))
    match_enriched = matches.merge(hospital_lookup, on="hospital_id", how="left")
    match_enriched["hospital_label"] = match_enriched["hospital_name"].fillna(match_enriched["hospital_id"])
    match_enriched["client_tag"] = match_enriched["hospital_id"].astype(str).isin(client_ids).map(
        {True: "既有客戶", False: "潛在院所"}
    )
    match_enriched["is_hospital_facility"] = match_enriched["hospital_name"].apply(
        lambda name: is_hospital_name(name, config.hospital_keywords, config.hospital_exclude_keywords)
    )
    if "selection_type" not in match_enriched.columns:
        match_enriched["selection_type"] = np.where(
            match_enriched["hospital_id"].astype(str).isin(client_ids),
            "既有客戶",
            np.where(match_enriched["is_hospital_facility"], "醫院", "潛在院所"),
        )

    selected_match = (
        match_enriched.loc[match_enriched["is_selected"] == 1, ["event_uid", "hospital_id", "hospital_name", "selection_type"]]
        .drop_duplicates(subset=["event_uid"])
        .rename(
            columns={
                "hospital_id": "selected_hospital_id",
                "hospital_name": "selected_hospital_name",
                "selection_type": "selected_client_tag",
            }
        )
    )
    nearest_match = (
        match_enriched.loc[match_enriched["candidate_rank"] == 1, ["event_uid", "hospital_name", "beeline_meter"]]
        .drop_duplicates(subset=["event_uid"])
        .rename(columns={"hospital_name": "nearest_hospital_name", "beeline_meter": "nearest_hospital_meter"})
    )
    nearest_client = build_nearest_existing_client_lookup(raw_events, hospitals, clients)
    nearest_hospital_only = build_nearest_hospital_lookup(raw_events, hospitals, config)
    raw_events = raw_events.merge(selected_match, on="event_uid", how="left")
    raw_events = raw_events.merge(nearest_match, on="event_uid", how="left")
    raw_events = raw_events.merge(nearest_client, on="event_uid", how="left")
    raw_events = raw_events.merge(nearest_hospital_only, on="event_uid", how="left")

    return {
        "config": config,
        "attendance": attendance,
        "routes": routes,
        "finance": finance,
        "daily_metrics": daily_metrics,
        "raw_events": raw_events,
        "matches": match_enriched,
        "employees": employees,
        "google_route_summary": google_route_summary,
        "google_route_cache": google_route_cache,
        "google_route_cache_detail": google_route_cache_detail,
    }


def build_daily_map(
    day_events: pd.DataFrame,
    employee_row: pd.Series | None = None,
    google_segments: pd.DataFrame | None = None,
) -> go.Figure:
    gps_events = day_events.dropna(subset=["gps_lat", "gps_lon"]).sort_values(["actual_time", "source_row_no"]).copy()
    fig = go.Figure()
    if gps_events.empty:
        fig.update_layout(height=760, margin=dict(l=0, r=0, t=30, b=0))
        return fig

    has_home = (
        employee_row is not None
        and pd.notna(employee_row.get("home_lat"))
        and pd.notna(employee_row.get("home_lon"))
    )
    first_point = gps_events.iloc[0]
    last_point = gps_events.iloc[-1]
    fit_latitudes = gps_events["gps_lat"].astype(float).tolist()
    fit_longitudes = gps_events["gps_lon"].astype(float).tolist()
    color_map = {
        "home_to_first": "#2563eb",
        "between_points": "#0f766e",
        "last_to_home": "#7c3aed",
    }
    label_map = {
        "home_to_first": "\u4f4f\u5bb6 \u2192 \u9996\u9ede",
        "between_points": "Google \u884c\u8eca\u8def\u5f91",
        "last_to_home": "\u672b\u9ede \u2192 \u4f4f\u5bb6",
    }
    fallback_segments: list[dict] = []
    segment_no = 1

    if has_home:
        home_lat = float(employee_row["home_lat"])
        home_lon = float(employee_row["home_lon"])
        fit_latitudes.append(home_lat)
        fit_longitudes.append(home_lon)
        fig.add_trace(
            go.Scattermap(
                lat=[home_lat],
                lon=[home_lon],
                mode="markers+text",
                text=["\u5bb6"],
                textposition="top center",
                textfont=dict(size=14, color="#1e3a8a"),
                marker=dict(size=20, color="#2563eb"),
                hovertemplate="<b>\u54e1\u5de5\u4f4f\u5bb6</b><br>%{lat:.6f}, %{lon:.6f}<extra></extra>",
                name="\u4f4f\u5bb6",
            )
        )
        fallback_segments.append(
            {
                "segment_no": segment_no,
                "segment_type": "home_to_first",
                "lat": [home_lat, float(first_point["gps_lat"])],
                "lon": [home_lon, float(first_point["gps_lon"])],
            }
        )
        segment_no += 1

    gps_points = gps_events[["gps_lat", "gps_lon"]].astype(float).to_dict("records")
    for first_coords, second_coords in zip(gps_points, gps_points[1:]):
        fallback_segments.append(
            {
                "segment_no": segment_no,
                "segment_type": "between_points",
                "lat": [first_coords["gps_lat"], second_coords["gps_lat"]],
                "lon": [first_coords["gps_lon"], second_coords["gps_lon"]],
            }
        )
        segment_no += 1

    if has_home:
        fallback_segments.append(
            {
                "segment_no": segment_no,
                "segment_type": "last_to_home",
                "lat": [float(last_point["gps_lat"]), home_lat],
                "lon": [float(last_point["gps_lon"]), home_lon],
            }
        )

    google_polyline_lookup: dict[tuple[int, str], list[tuple[float, float]]] = {}
    if google_segments is not None and not google_segments.empty:
        for _, segment in google_segments.sort_values("segment_no").iterrows():
            if "coords" in segment:
                points = segment["coords"]
            else:
                points = decode_polyline(segment.get("polyline"))
            if len(points) >= 2:
                google_polyline_lookup[(int(segment["segment_no"]), str(segment["segment_type"]))] = points

    has_any_google_polyline = bool(google_polyline_lookup)
    if not fallback_segments:
        fallback_segments.append(
            {
                "segment_no": 1,
                "segment_type": "between_points",
                "lat": gps_events["gps_lat"].astype(float).tolist(),
                "lon": gps_events["gps_lon"].astype(float).tolist(),
            }
        )

    for segment in fallback_segments:
        key = (int(segment["segment_no"]), str(segment["segment_type"]))
        google_points = google_polyline_lookup.get(key)
        if google_points:
            fit_latitudes.extend([point[0] for point in google_points])
            fit_longitudes.extend([point[1] for point in google_points])
            fig.add_trace(
                go.Scattermap(
                    lat=[point[0] for point in google_points],
                    lon=[point[1] for point in google_points],
                    mode="lines",
                    line=dict(width=4, color=color_map.get(segment["segment_type"], "#0f766e")),
                    hoverinfo="skip",
                    name=label_map.get(segment["segment_type"], "Google \u884c\u8eca\u8def\u5f91"),
                    showlegend=segment["segment_no"] == 1 or segment["segment_type"] != "between_points",
                )
            )
        else:
            fig.add_trace(
                go.Scattermap(
                    lat=segment["lat"],
                    lon=segment["lon"],
                    mode="lines",
                    line=dict(width=3, color=color_map.get(segment["segment_type"], "#0f766e")),
                    opacity=0.55 if has_any_google_polyline else 0.9,
                    hoverinfo="skip",
                    name=(
                        f"{label_map.get(segment['segment_type'], '\u6253\u5361\u9ede\u9023\u7dda')}\uff08\u76f4\u7dda\u88dc\u7dda\uff09"
                        if has_any_google_polyline
                        else label_map.get(segment["segment_type"], "\u6253\u5361\u9ede\u9023\u7dda")
                    ),
                    showlegend=segment["segment_no"] == 1 or segment["segment_type"] != "between_points",
                )
            )

    point_labels = [str(i) for i in range(1, len(gps_events) + 1)]
    point_colors = []
    point_sizes = []
    for idx in range(len(gps_events)):
        if idx == 0:
            point_colors.append("#0b7285")
            point_sizes.append(30)
        elif idx == len(gps_events) - 1:
            point_colors.append("#7c3aed")
            point_sizes.append(30)
        else:
            point_colors.append("#0f766e")
            point_sizes.append(26)

    fig.add_trace(
        go.Scattermap(
            lat=gps_events["gps_lat"],
            lon=gps_events["gps_lon"],
            mode="markers+text",
            text=point_labels,
            textposition="middle center",
            textfont=dict(size=15, color="white"),
            marker=dict(size=point_sizes, color=point_colors, opacity=0.96),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "\u9806\u5e8f\uff1a%{customdata[4]}<br>"
                "\u6642\u9593\uff1a%{customdata[1]}<br>"
                "\u5ea7\u6a19\uff1a%{lat:.6f}, %{lon:.6f}<br>"
                "\u9810\u4f30\u9662\u6240\uff1a%{customdata[2]}<br>"
                "\u985e\u578b\uff1a%{customdata[3]}<extra></extra>"
            ),
            customdata=[
                [
                    row.employee_label if pd.notna(row.employee_label) else "\u672a\u5224\u5b9a",
                    row.actual_time_display if pd.notna(row.actual_time_display) else "\u672a\u5224\u5b9a",
                    row.selected_hospital_name if pd.notna(row.selected_hospital_name) else "\u672a\u5224\u5b9a",
                    row.selected_client_tag if pd.notna(row.selected_client_tag) else "\u672a\u5224\u5b9a",
                    f"\u7b2c {index + 1} \u7ad9",
                ]
                for index, row in gps_events.reset_index(drop=True).iterrows()
            ],
            name="\u6253\u5361\u9ede\u9806\u5e8f",
        )
    )

    selected_stops = gps_events.dropna(subset=["selected_hospital_name"]).copy()
    if not selected_stops.empty:
        fig.add_trace(
            go.Scattermap(
                lat=selected_stops["gps_lat"],
                lon=selected_stops["gps_lon"],
                mode="markers",
                marker=dict(
                    size=14,
                    color=selected_stops["selected_client_tag"].map({"\u65e2\u6709\u5ba2\u6236": "#dc2626", "\u6f5b\u5728\u9662\u6240": "#f59e0b"}).fillna("#2563eb"),
                    opacity=0.55,
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "\u9662\u6240\uff1a%{customdata[1]}<br>"
                    "\u6642\u9593\uff1a%{customdata[2]}<extra></extra>"
                ),
                customdata=selected_stops[["selected_client_tag", "selected_hospital_name", "actual_time_display"]].fillna("\u672a\u5224\u5b9a"),
                name="\u9810\u4f30\u62dc\u8a2a\u9662\u6240",
            )
        )

    lat_span = max(fit_latitudes) - min(fit_latitudes)
    lon_span = max(fit_longitudes) - min(fit_longitudes)
    lat_padding = max(lat_span * 0.45, 0.008)
    lon_padding = max(lon_span * 0.45, 0.008)
    padded_lats = [min(fit_latitudes) - lat_padding, max(fit_latitudes) + lat_padding]
    padded_lons = [min(fit_longitudes) - lon_padding, max(fit_longitudes) + lon_padding]

    fig.add_trace(
        go.Scattermap(
            lat=padded_lats,
            lon=padded_lons,
            mode="markers",
            marker=dict(size=1, opacity=0),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.update_layout(
        map_style="open-street-map",
        map=dict(
            center=dict(lat=sum(padded_lats) / len(padded_lats), lon=sum(padded_lons) / len(padded_lons)),
            zoom=max(compute_zoom(padded_lats, padded_lons) - 1.25, 2.4),
            bounds=dict(
                west=min(padded_lons),
                east=max(padded_lons),
                south=min(padded_lats),
                north=max(padded_lats),
            ),
        ),
        height=780,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.01),
    )
    return fig

def build_candidate_panel(day_events: pd.DataFrame, matches: pd.DataFrame) -> list[dict]:
    gps_events = day_events.dropna(subset=["gps_lat", "gps_lon"]).copy()
    if gps_events.empty:
        return []

    candidates = matches.merge(
        gps_events[
            [
                "event_uid",
                "actual_time_display",
                "gps_lat",
                "gps_lon",
                "selected_hospital_name",
                "selected_client_tag",
                "nearest_client_name",
                "nearest_client_meter",
                "nearest_hospital_name",
                "nearest_hospital_meter",
                "nearest_hospital_only_name",
                "nearest_hospital_only_meter",
            ]
        ],
        on="event_uid",
        how="inner",
    )
    candidates = candidates.sort_values(["seq_no", "candidate_rank"]).copy()
    panels: list[dict] = []
    for _, group in candidates.groupby(["seq_no", "event_uid", "actual_time_display", "gps_lat", "gps_lon"], dropna=False):
        group = group.sort_values("candidate_rank").copy()
        first_row = group.iloc[0]
        selected_row = group.loc[group["is_selected"] == 1].head(1)
        top_candidates = group.head(5).copy()
        if not selected_row.empty and int(selected_row.iloc[0]["candidate_rank"]) not in set(top_candidates["candidate_rank"].tolist()):
            top_candidates = pd.concat([top_candidates, selected_row], ignore_index=True)
            top_candidates = top_candidates.drop_duplicates(subset=["candidate_rank"], keep="first")
        candidate_items = []
        for _, row in top_candidates.iterrows():
            candidate_items.append(
                {
                    "rank": int(row["candidate_rank"]),
                    "name": row["hospital_label"],
                    "distance": float(row["beeline_meter"]),
                    "tag": "既有客戶" if row["client_tag"] == "既有客戶" else ("醫院" if bool(row.get("is_hospital_facility", False)) else "潛在院所"),
                    "selected": int(row.get("is_selected", 0)) == 1,
                }
            )
        panels.append(
            {
                "seq_no": int(first_row["seq_no"]),
                "time": first_row["actual_time_display"],
                "lat": float(first_row["gps_lat"]),
                "lon": float(first_row["gps_lon"]),
                "nearest_hospital_name": first_row["nearest_hospital_name"],
                "nearest_hospital_meter": float(first_row["nearest_hospital_meter"]) if pd.notna(first_row["nearest_hospital_meter"]) else None,
                "nearest_hospital_only_name": first_row["nearest_hospital_only_name"],
                "nearest_hospital_only_meter": float(first_row["nearest_hospital_only_meter"]) if pd.notna(first_row["nearest_hospital_only_meter"]) else None,
                "selected_hospital_name": first_row["selected_hospital_name"],
                "selected_client_tag": first_row["selected_client_tag"],
                "nearest_client_name": first_row["nearest_client_name"],
                "nearest_client_meter": first_row["nearest_client_meter"],
                "candidates": candidate_items,
            }
        )
    return panels


def render_candidate_cards(candidate_panels: list[dict]) -> None:
    if not candidate_panels:
        st.info("這一天沒有可用 GPS 路徑資料。")
        return

    st.markdown(
        """
        <div class="candidate-panel-header">
            <div class="candidate-title">打卡點候選院所</div>
            <div class="candidate-sub">依每個 GPS 打卡點列出最近既有客戶、最近醫院、系統選定院所與前五候選名單。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for row_panels in chunked(candidate_panels, 3):
        columns = st.columns(3)
        for column, panel in zip(columns, row_panels):
            selected_tag_class = (
                "tag-client" if panel["selected_client_tag"] == "既有客戶"
                else "tag-hospital" if panel["selected_client_tag"] == "醫院"
                else "tag-potential"
            )
            selected_tag = panel["selected_client_tag"] or "未判定"
            nearest_client_text = (
                f"{panel['nearest_client_name']} · {panel['nearest_client_meter']:.0f} m"
                if panel["nearest_client_name"] and panel["nearest_client_meter"] is not None
                else "無既有客戶資料"
            )
            nearest_text = (
                f"{panel['nearest_hospital_only_name']} · {panel['nearest_hospital_only_meter']:.0f} m"
                if panel["nearest_hospital_only_name"] and panel["nearest_hospital_only_meter"] is not None
                else "醫院主檔中沒有可判定為醫院的院所"
            )
            list_items = []
            for item in panel["candidates"]:
                tag_class = (
                    "tag-client" if item["tag"] == "既有客戶"
                    else "tag-hospital" if item["tag"] == "醫院"
                    else "tag-potential"
                )
                selected_suffix = "（系統選定）" if item.get("selected") else ""
                rank_suffix = f"（候選#{item['rank']}）" if int(item["rank"]) > 5 else ""
                list_items.append(
                    f"<li>{item['name']}{selected_suffix}{rank_suffix} · {item['distance']:.0f} m "
                    f"<span class=\"{tag_class}\">{item['tag']}</span></li>"
                )
            selected_name = panel["selected_hospital_name"] or "未判定"
            html = f"""
            <div class="candidate-card">
                <div class="candidate-title">#{panel['seq_no']} {panel['time']}</div>
                <div class="candidate-sub">座標：{panel['lat']:.6f}, {panel['lon']:.6f}</div>
                <div class="candidate-sub">最近既有客戶：{nearest_client_text}</div>
                <div class="candidate-sub">最近醫院：{nearest_text}</div>
                <div class="candidate-sub">系統選定：{selected_name}<span class="{selected_tag_class}">{selected_tag}</span></div>
                <ol class="candidate-list">
                    {''.join(list_items)}
                </ol>
            </div>
            """
            column.markdown(html, unsafe_allow_html=True)


def summarize_period(
    employee_id: str,
    start_date,
    end_date,
    attendance: pd.DataFrame,
    daily_metrics: pd.DataFrame,
    routes: pd.DataFrame,
    event_flags: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    attendance_mask = attendance["work_date"].dt.date.between(start_date, end_date)
    metrics_mask = daily_metrics["work_date"].dt.date.between(start_date, end_date)
    routes_mask = routes["work_date"].dt.date.between(start_date, end_date)
    period_attendance = attendance.loc[(attendance["employee_id"] == employee_id) & attendance_mask].copy()
    period_metrics = daily_metrics.loc[(daily_metrics["employee_id"] == employee_id) & metrics_mask].copy()
    period_routes = routes.loc[(routes["employee_id"] == employee_id) & routes_mask].copy()

    if period_attendance.empty:
        return pd.DataFrame(), pd.DataFrame()

    merged = (
        period_attendance.merge(
            period_metrics[
                [
                    "attendance_uid",
                    "raw_span_minutes",
                    "effective_field_minutes",
                    "anomaly_flag",
                ]
            ],
            on="attendance_uid",
            how="left",
        )
        .merge(
            event_flags[
                [
                    "attendance_uid",
                    "missing_punch_count",
                    "missing_punch_unprocessed_count",
                    "missing_punch_processed_count",
                    "forget_punch_application_count",
                    "missing_punch_unprocessed_flag",
                    "overtime_flag_bool",
                    "actual_overtime_flag",
                    "personal_overtime_flag",
                ]
            ],
            on="attendance_uid",
            how="left",
        )
        .merge(
            period_routes[
                [
                    "attendance_uid",
                    "estimated_total_km",
                    "estimated_business_km",
                    "estimated_travel_min",
                    "matched_stop_count",
                ]
            ],
            on="attendance_uid",
            how="left",
        )
    )
    merged["employee_label"] = merged["employee_label"].fillna(
        merged.apply(lambda row: make_employee_label(row["employee_id"], row["employee_name"]), axis=1)
    )
    for column in [
        "missing_punch_count",
        "missing_punch_unprocessed_count",
        "missing_punch_processed_count",
        "forget_punch_application_count",
    ]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0).astype(int)
    for column in ["missing_punch_unprocessed_flag", "overtime_flag_bool", "actual_overtime_flag", "personal_overtime_flag"]:
        merged[column] = merged[column].fillna(False).astype(bool)

    summary = pd.DataFrame(
        [
            {
                "員工": merged["employee_label"].iloc[0],
                "部門": merged["department"].mode().iloc[0] if not merged["department"].mode().empty else "",
                "報表起日": merged["work_date"].min().date().isoformat(),
                "報表迄日": merged["work_date"].max().date().isoformat(),
                "出勤天數": int(merged["attendance_uid"].nunique()),
                "總出勤時數": round(merged["raw_span_minutes"].fillna(0).sum() / 60, 2),
                "總有效外勤時數": round(merged["effective_field_minutes"].fillna(0).sum() / 60, 2),
                "總打卡次數": int(merged["event_count"].fillna(0).sum()),
                "總GPS點數": int(merged["gps_event_count"].fillna(0).sum()),
                "總計預估里程": round(merged["estimated_total_km"].fillna(0).sum(), 2),
                "總計預估公務里程": round(merged["estimated_business_km"].fillna(0).sum(), 2),
                "平均每日里程": round(merged["estimated_total_km"].fillna(0).mean(), 2),
                "平均每日公務里程": round(merged["estimated_business_km"].fillna(0).mean(), 2),
                "未打卡未處理次數": int(merged["missing_punch_unprocessed_count"].fillna(0).sum()),
                "未打卡已處理次數": int(merged["missing_punch_processed_count"].fillna(0).sum()),
                "忘刷申請總次數": int(merged["forget_punch_application_count"].fillna(0).sum()),
                "異常率": round(float(merged["anomaly_flag"].fillna(False).mean()), 4),
                "超時出勤率": round(float(merged["overtime_flag_bool"].fillna(False).mean()), 4),
                "實際加班率": round(float(merged["actual_overtime_flag"].fillna(False).mean()), 4),
                "總匹配院所次數": int(merged["matched_stop_count"].fillna(0).sum()),
            }
        ]
    )

    detail = merged[
        [
            "work_date",
            "employee_label",
            "department",
            "event_count",
            "gps_event_count",
            "raw_span_minutes",
            "effective_field_minutes",
            "estimated_total_km",
            "estimated_business_km",
            "estimated_travel_min",
            "matched_stop_count",
            "missing_punch_unprocessed_count",
            "missing_punch_processed_count",
            "forget_punch_application_count",
            "overtime_flag_bool",
            "actual_overtime_flag",
            "personal_overtime_flag",
            "compare_result_summary",
            "source_quality_status",
        ]
    ].sort_values("work_date")
    detail = detail.rename(
        columns={
            "work_date": "日期",
            "employee_label": "員工",
            "department": "部門",
            "event_count": "打卡次數",
            "gps_event_count": "GPS點數",
            "raw_span_minutes": "總出勤分鐘",
            "effective_field_minutes": "有效外勤分鐘",
            "estimated_total_km": "預估總里程",
            "estimated_business_km": "預估公務里程",
            "estimated_travel_min": "預估移動分鐘",
            "matched_stop_count": "匹配院所數",
            "missing_punch_unprocessed_count": "未打卡未處理次數",
            "missing_punch_processed_count": "未打卡已處理次數",
            "forget_punch_application_count": "忘刷申請次數",
            "overtime_flag_bool": "超時出勤",
            "actual_overtime_flag": "實際加班",
            "personal_overtime_flag": "個人因素超時",
            "compare_result_summary": "異常摘要",
            "source_quality_status": "資料品質",
        }
    )
    return summary, detail


def build_overview_summary(
    attendance: pd.DataFrame,
    daily_metrics: pd.DataFrame,
    routes: pd.DataFrame,
    finance: pd.DataFrame,
    event_flags: pd.DataFrame,
    start_date,
    end_date,
) -> pd.DataFrame:
    attendance_mask = attendance["work_date"].dt.date.between(start_date, end_date)
    metrics_mask = daily_metrics["work_date"].dt.date.between(start_date, end_date)
    routes_mask = routes["work_date"].dt.date.between(start_date, end_date)
    finance_mask = finance["work_date"].dt.date.between(start_date, end_date)

    base = attendance.loc[attendance_mask].copy()
    metrics = daily_metrics.loc[metrics_mask, ["attendance_uid", "raw_span_minutes", "effective_field_minutes", "anomaly_flag", "gps_event_count"]]
    route_slice = routes.loc[routes_mask, ["attendance_uid", "estimated_total_km", "estimated_business_km", "estimated_travel_min", "route_confidence"]]
    finance_slice = finance.loc[finance_mask, ["attendance_uid", "audit_light", "fuel_subsidy", "maintenance_subsidy", "per_diem_amount"]]
    event_flag_slice = event_flags[
        [
            "attendance_uid",
            "missing_punch_unprocessed_count",
            "missing_punch_processed_count",
            "overtime_flag_bool",
            "actual_overtime_flag",
            "personal_overtime_flag",
        ]
    ]

    merged = base.merge(metrics, on="attendance_uid", how="left", suffixes=("", "_metric"))
    merged = merged.merge(route_slice, on="attendance_uid", how="left")
    merged = merged.merge(finance_slice, on="attendance_uid", how="left")
    merged = merged.merge(event_flag_slice, on="attendance_uid", how="left")
    for column in ["overtime_flag_bool", "actual_overtime_flag", "personal_overtime_flag"]:
        merged[column] = merged[column].fillna(False).astype(bool)

    summary = (
        merged.groupby(["employee_id", "employee_label", "department"], dropna=False)
        .agg(
            出勤天數=("attendance_uid", "nunique"),
            總出勤時數=("raw_span_minutes", lambda s: round(s.fillna(0).sum() / 60, 2)),
            總GPS點數=("gps_event_count", lambda s: int(s.fillna(0).sum())),
            總打卡次數=("event_count", lambda s: int(s.fillna(0).sum())),
            總計預估里程=("estimated_total_km", lambda s: round(s.fillna(0).sum(), 2)),
            總計預估公務里程=("estimated_business_km", lambda s: round(s.fillna(0).sum(), 2)),
            未打卡未處理次數=("missing_punch_unprocessed_count", lambda s: int(s.fillna(0).sum())),
            平均路徑信心=("route_confidence", lambda s: round(s.fillna(0).mean(), 4)),
            異常率=("anomaly_flag", lambda s: round(float(s.fillna(False).mean()), 4)),
            超時出勤率=("overtime_flag_bool", lambda s: round(float(s.fillna(False).mean()), 4)),
            實際加班率=("actual_overtime_flag", lambda s: round(float(s.fillna(False).mean()), 4)),
            油資補貼=("fuel_subsidy", lambda s: round(s.fillna(0).sum(), 2)),
            維修補貼=("maintenance_subsidy", lambda s: round(s.fillna(0).sum(), 2)),
            日當費=("per_diem_amount", lambda s: round(s.fillna(0).sum(), 2)),
        )
        .reset_index()
        .sort_values(["總計預估里程", "異常率"], ascending=[False, False])
    )
    return summary


def normalize_year_month_value(value) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    for fmt in ("%Y-%m", "%Y/%m", "%Y-%m-%d", "%Y/%m/%d", "%b-%y", "%b-%Y", "%Y%m", "%m/%Y"):
        try:
            return pd.to_datetime(text, format=fmt).strftime("%Y-%m")
        except (TypeError, ValueError):
            continue
    try:
        return pd.to_datetime(text, errors="raise").strftime("%Y-%m")
    except (TypeError, ValueError):
        return None


def months_in_range(start_date, end_date) -> list[str]:
    start_ts = pd.Timestamp(start_date).to_period("M")
    end_ts = pd.Timestamp(end_date).to_period("M")
    return [str(period) for period in pd.period_range(start_ts, end_ts, freq="M")]


def build_monthly_claim_comparison(
    routes: pd.DataFrame,
    monthly_claims: pd.DataFrame | None,
    green_threshold: float,
    yellow_threshold: float,
) -> pd.DataFrame:
    comparison_columns = [
        "employee_id",
        "employee_label",
        "department",
        "year_month",
        "claimed_km",
        "estimated_business_km",
        "difference_km",
        "difference_rate",
        "difference_rate_abs",
        "comparison_light",
    ]
    if routes.empty:
        return pd.DataFrame(columns=comparison_columns)

    route_monthly = routes.copy()
    if "employee_label" not in route_monthly.columns:
        route_monthly["employee_label"] = route_monthly.get("employee_id", "").astype("string")
    if "department" not in route_monthly.columns:
        route_monthly["department"] = ""
    route_monthly["work_date"] = pd.to_datetime(route_monthly["work_date"], errors="coerce")
    route_monthly["year_month"] = route_monthly["work_date"].dt.strftime("%Y-%m")
    route_monthly["estimated_business_km"] = pd.to_numeric(route_monthly["estimated_business_km"], errors="coerce").fillna(0.0)
    route_monthly = (
        route_monthly.dropna(subset=["employee_id", "year_month"])
        .groupby(["employee_id", "employee_label", "department", "year_month"], dropna=False, as_index=False)["estimated_business_km"]
        .sum()
    )

    if monthly_claims is None or monthly_claims.empty:
        comparison = route_monthly.copy()
        comparison["claimed_km"] = np.nan
    else:
        claims = monthly_claims.copy()
        claims["employee_id"] = claims["employee_id"].astype("string").str.strip()
        claims["year_month"] = claims["year_month"].apply(normalize_year_month_value)
        claims["claimed_km"] = pd.to_numeric(claims["claimed_km"], errors="coerce")
        claims = (
            claims.dropna(subset=["employee_id", "year_month", "claimed_km"])
            .groupby(["employee_id", "year_month"], dropna=False, as_index=False)["claimed_km"]
            .sum()
        )
        comparison = route_monthly.merge(claims, on=["employee_id", "year_month"], how="outer")
        comparison["employee_label"] = comparison["employee_label"].fillna(comparison["employee_id"])
        comparison["estimated_business_km"] = pd.to_numeric(comparison["estimated_business_km"], errors="coerce").fillna(0.0)

    comparison["claimed_km"] = pd.to_numeric(comparison["claimed_km"], errors="coerce")
    comparison["difference_km"] = comparison["claimed_km"].fillna(0.0) - comparison["estimated_business_km"].fillna(0.0)
    denominator = comparison["claimed_km"].where(comparison["claimed_km"].fillna(0) > 0)
    comparison["difference_rate"] = comparison["difference_km"] / denominator
    comparison["difference_rate_abs"] = comparison["difference_rate"].abs()

    def classify(row: pd.Series) -> str:
        if pd.isna(row["claimed_km"]):
            return "gray"
        variance = row["difference_rate_abs"]
        if pd.isna(variance):
            return "gray"
        if variance <= green_threshold:
            return "green"
        if variance <= yellow_threshold:
            return "yellow"
        return "red"

    comparison["comparison_light"] = comparison.apply(classify, axis=1)
    return comparison[comparison_columns].sort_values(["year_month", "employee_id"]).reset_index(drop=True)


def format_distance_summary(group: pd.DataFrame, name_col: str, distance_col: str, tag_col: str | None = None) -> str:
    if group.empty or name_col not in group.columns:
        return ""
    work = group.copy()
    work[name_col] = work[name_col].fillna("").astype(str).str.strip()
    work = work.loc[work[name_col] != ""].copy()
    if work.empty:
        return ""
    if distance_col in work.columns:
        work[distance_col] = pd.to_numeric(work[distance_col], errors="coerce")
        work = work.sort_values(distance_col, na_position="last")
    subset = [name_col]
    if tag_col and tag_col in work.columns:
        subset.append(tag_col)
    work = work.drop_duplicates(subset=subset, keep="first")
    items: list[str] = []
    for _, row in work.iterrows():
        label = str(row[name_col]).strip()
        if tag_col and tag_col in work.columns and pd.notna(row.get(tag_col)) and str(row.get(tag_col)).strip():
            label = f"{label}（{str(row.get(tag_col)).strip()}）"
        if distance_col in work.columns and pd.notna(row.get(distance_col)):
            label = f"{label} · {int(round(float(row[distance_col])))} m"
        items.append(label)
    return "；".join(items)


def json_safe_value(value):
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if pd.isna(value):
        return ""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def dataframe_to_sheet_rows(dataframe: pd.DataFrame) -> list[list]:
    rows = [list(dataframe.columns)]
    for row in dataframe.itertuples(index=False, name=None):
        rows.append([json_safe_value(value) for value in row])
    return rows


def reference_report_filename(start_date, end_date) -> str:
    start_text = pd.Timestamp(start_date).strftime("%Y-%m-%d")
    end_text = pd.Timestamp(end_date).strftime("%Y-%m-%d")
    if pd.Timestamp(start_date).to_period("M") == pd.Timestamp(end_date).to_period("M"):
        prefix = pd.Timestamp(start_date).strftime("%Y-%m")
    else:
        prefix = f"{start_text}_to_{end_text}"
    return f"{prefix}_業務核定參考報表.xlsx"


def find_node_executable() -> str:
    candidates = [
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    fallback = shutil.which("node")
    if fallback:
        return fallback
    raise FileNotFoundError("找不到可用的 Node.js 執行檔，無法產出 Excel 報表。")


def ensure_artifact_tool_node_modules(base_dir: Path) -> None:
    local_node_modules = base_dir / "node_modules"
    if local_node_modules.exists():
        return
    bundled_node_modules = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node_modules"
    if not bundled_node_modules.exists():
        raise FileNotFoundError("找不到 artifact-tool 所需的 node_modules。")
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(local_node_modules), str(bundled_node_modules)],
        check=True,
        cwd=base_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def build_google_sheet_reference_payload(
    attendance: pd.DataFrame,
    daily_metrics: pd.DataFrame,
    routes: pd.DataFrame,
    finance: pd.DataFrame,
    raw_events: pd.DataFrame,
    matches: pd.DataFrame,
    employees: pd.DataFrame,
    event_flags: pd.DataFrame,
    monthly_claim_comparison: pd.DataFrame,
    google_route_cache: pd.DataFrame,
    config,
    start_date,
    end_date,
) -> dict:
    attendance_slice = attendance.loc[attendance["work_date"].dt.date.between(start_date, end_date)].copy()
    if attendance_slice.empty:
        raise ValueError("所選日期區間沒有可匯出的出勤資料。")

    metrics_slice = daily_metrics.loc[
        daily_metrics["attendance_uid"].isin(attendance_slice["attendance_uid"]),
        ["attendance_uid", "raw_span_minutes", "effective_field_minutes", "anomaly_flag"],
    ].copy()
    route_slice = routes.loc[
        routes["attendance_uid"].isin(attendance_slice["attendance_uid"]),
        ["attendance_uid", "estimated_total_km", "estimated_business_km", "estimated_travel_min", "route_confidence"],
    ].copy()
    finance_slice = finance.loc[
        finance["attendance_uid"].isin(attendance_slice["attendance_uid"]),
        ["attendance_uid", "fuel_subsidy", "maintenance_subsidy", "per_diem_amount", "audit_light", "audit_status"],
    ].copy()
    flag_slice = event_flags.loc[
        event_flags["attendance_uid"].isin(attendance_slice["attendance_uid"]),
        [
            "attendance_uid",
            "missing_punch_unprocessed_count",
            "missing_punch_processed_count",
            "forget_punch_application_count",
            "overtime_flag_bool",
            "actual_overtime_flag",
            "personal_overtime_flag",
        ],
    ].copy()

    daily_export = attendance_slice.merge(metrics_slice, on="attendance_uid", how="left")
    daily_export = daily_export.merge(route_slice, on="attendance_uid", how="left")
    daily_export = daily_export.merge(finance_slice, on="attendance_uid", how="left")
    daily_export = daily_export.merge(flag_slice, on="attendance_uid", how="left")
    daily_export["year_month"] = daily_export["work_date"].dt.strftime("%Y-%m")
    daily_export["出勤時段"] = daily_export.apply(
        lambda row: (
            f"{pd.to_datetime(row['first_actual_time'], errors='coerce'):%H:%M}-{pd.to_datetime(row['last_actual_time'], errors='coerce'):%H:%M}"
            if pd.notna(pd.to_datetime(row["first_actual_time"], errors="coerce"))
            and pd.notna(pd.to_datetime(row["last_actual_time"], errors="coerce"))
            else ""
        ),
        axis=1,
    )
    daily_export["總出勤時數"] = pd.to_numeric(daily_export["raw_span_minutes"], errors="coerce").fillna(0) / 60
    daily_export["有效外勤時數"] = pd.to_numeric(daily_export["effective_field_minutes"], errors="coerce").fillna(0) / 60

    detail_events = raw_events.loc[raw_events["attendance_uid"].isin(attendance_slice["attendance_uid"])].copy()
    selected_event_detail = (
        matches.loc[matches["is_selected"] == 1, ["event_uid", "hospital_label", "beeline_meter", "selection_type"]]
        .drop_duplicates(subset=["event_uid"], keep="first")
        .rename(
            columns={
                "hospital_label": "selected_hospital_label_detail",
                "beeline_meter": "selected_hospital_meter_detail",
                "selection_type": "selected_hospital_type_detail",
            }
        )
    )
    detail_events = detail_events.merge(selected_event_detail, on="event_uid", how="left")

    selected_matches_for_summary = matches.loc[
        matches["attendance_uid"].isin(attendance_slice["attendance_uid"]) & (matches["is_selected"] == 1),
        ["attendance_uid", "seq_no", "hospital_label", "beeline_meter", "selection_type"],
    ].sort_values(["attendance_uid", "seq_no", "beeline_meter"])
    selected_summary = (
        selected_matches_for_summary.groupby("attendance_uid", dropna=False)[["hospital_label", "beeline_meter", "selection_type"]]
        .apply(lambda group: format_distance_summary(group, "hospital_label", "beeline_meter", "selection_type"))
        .reset_index(name="系統選定院所清單")
    )
    nearest_client_summary = (
        detail_events.groupby("attendance_uid", dropna=False)[["nearest_client_name", "nearest_client_meter"]]
        .apply(lambda group: format_distance_summary(group, "nearest_client_name", "nearest_client_meter"))
        .reset_index(name="最近既有客戶清單")
    )
    nearest_hospital_summary = (
        detail_events.groupby("attendance_uid", dropna=False)[["nearest_hospital_only_name", "nearest_hospital_only_meter"]]
        .apply(lambda group: format_distance_summary(group, "nearest_hospital_only_name", "nearest_hospital_only_meter"))
        .reset_index(name="最近醫院清單")
    )
    daily_export = daily_export.merge(selected_summary, on="attendance_uid", how="left")
    daily_export = daily_export.merge(nearest_client_summary, on="attendance_uid", how="left")
    daily_export = daily_export.merge(nearest_hospital_summary, on="attendance_uid", how="left")

    employee_lookup = employees.drop_duplicates(subset=["employee_id"]).set_index("employee_id")
    cache_slice = google_route_cache.loc[
        google_route_cache["attendance_key"].isin(attendance_slice["attendance_key"])
    ].copy() if isinstance(google_route_cache, pd.DataFrame) and not google_route_cache.empty else pd.DataFrame()
    commute_rows: list[dict] = []
    for row in daily_export.itertuples(index=False):
        row_dict = row._asdict()
        employee_row = employee_lookup.loc[row_dict["employee_id"]] if row_dict["employee_id"] in employee_lookup.index else None
        day_events = detail_events.loc[detail_events["attendance_uid"] == row_dict["attendance_uid"]].copy()
        day_google_segments = cache_slice.loc[cache_slice["attendance_key"] == row_dict.get("attendance_key")].copy() if not cache_slice.empty else pd.DataFrame()
        commute_estimate = build_commute_estimate(pd.Series(row_dict), day_events, employee_row, day_google_segments, config)
        commute_rows.append(
            {
                "attendance_uid": row_dict["attendance_uid"],
                "預估通勤公里": round(float(commute_estimate["commute_km"]), 2),
                "預估通勤時間(分)": round(float(commute_estimate["commute_min"]), 1),
            }
        )
    daily_export = daily_export.merge(pd.DataFrame(commute_rows), on="attendance_uid", how="left")

    month_claims = monthly_claim_comparison.loc[
        monthly_claim_comparison["year_month"].isin(daily_export["year_month"].dropna().unique().tolist())
    ][["employee_id", "year_month", "claimed_km", "difference_km", "difference_rate", "comparison_light"]].copy()
    daily_export = daily_export.merge(month_claims, on=["employee_id", "year_month"], how="left")

    daily_sheet = daily_export[
        [
            "year_month",
            "work_date",
            "employee_id",
            "employee_name",
            "employee_label",
            "department",
            "attendance_uid",
            "出勤時段",
            "event_count",
            "gps_event_count",
            "總出勤時數",
            "有效外勤時數",
            "estimated_total_km",
            "estimated_business_km",
            "預估通勤公里",
            "預估通勤時間(分)",
            "route_confidence",
            "missing_punch_unprocessed_count",
            "forget_punch_application_count",
            "overtime_flag_bool",
            "actual_overtime_flag",
            "最近既有客戶清單",
            "最近醫院清單",
            "系統選定院所清單",
            "claimed_km",
            "difference_km",
            "difference_rate",
            "comparison_light",
            "fuel_subsidy",
            "maintenance_subsidy",
            "per_diem_amount",
            "audit_light",
            "audit_status",
        ]
    ].rename(
        columns={
            "year_month": "月份",
            "work_date": "日期",
            "employee_id": "員工編號",
            "employee_name": "員工姓名",
            "employee_label": "員工",
            "department": "部門",
            "attendance_uid": "attendance_uid",
            "event_count": "打卡次數",
            "gps_event_count": "GPS點數",
            "estimated_total_km": "預估總里程(km)",
            "estimated_business_km": "預估公務里程(km)",
            "route_confidence": "路徑信心",
            "missing_punch_unprocessed_count": "未打卡未處理次數",
            "forget_punch_application_count": "忘刷申請次數",
            "overtime_flag_bool": "超時出勤",
            "actual_overtime_flag": "實際加班",
            "claimed_km": "實際月申請里程(km)",
            "difference_km": "月申請-預估差異(km)",
            "difference_rate": "月申請-預估差異率",
            "comparison_light": "月比較燈號",
            "fuel_subsidy": "參考油資補貼",
            "maintenance_subsidy": "參考維修補貼",
            "per_diem_amount": "參考日當費",
            "audit_light": "財務燈號",
            "audit_status": "財務狀態",
        }
    )
    daily_sheet["日期"] = pd.to_datetime(daily_sheet["日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    for bool_col in ["超時出勤", "實際加班"]:
        daily_sheet[bool_col] = daily_sheet[bool_col].fillna(False).map({True: "是", False: "否"})
    daily_sheet["核定油費"] = ""
    daily_sheet["核定日當費"] = ""
    daily_sheet["核定狀態"] = ""
    daily_sheet["核定備註"] = ""

    monthly_summary = (
        daily_sheet.groupby(["月份", "員工編號", "員工姓名", "員工", "部門"], dropna=False, as_index=False)
        .agg(
            出勤天數=("attendance_uid", "nunique"),
            總打卡次數=("打卡次數", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            總GPS點數=("GPS點數", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            總出勤時數=("總出勤時數", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 2)),
            總有效外勤時數=("有效外勤時數", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 2)),
            預估總里程_km=("預估總里程(km)", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 2)),
            預估公務里程_km=("預估公務里程(km)", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 2)),
            預估通勤公里_km=("預估通勤公里", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 2)),
            預估通勤時間_分=("預估通勤時間(分)", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 1)),
            未打卡未處理次數=("未打卡未處理次數", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            忘刷申請次數=("忘刷申請次數", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            超時出勤天數=("超時出勤", lambda s: int((pd.Series(s).astype(str) == "是").sum())),
            實際加班天數=("實際加班", lambda s: int((pd.Series(s).astype(str) == "是").sum())),
            實際月申請里程_km=("實際月申請里程(km)", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).max(), 2)),
            月申請減預估差異_km=("月申請-預估差異(km)", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).max(), 2)),
            月申請減預估差異率=("月申請-預估差異率", lambda s: pd.to_numeric(s, errors="coerce").dropna().iloc[0] if not pd.to_numeric(s, errors="coerce").dropna().empty else np.nan),
            月比較燈號=("月比較燈號", lambda s: next((value for value in s if pd.notna(value) and str(value).strip()), "")),
            參考油資補貼=("參考油資補貼", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 2)),
            參考維修補貼=("參考維修補貼", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 2)),
            參考日當費=("參考日當費", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 2)),
        )
        .sort_values(["月份", "員工編號"])
    )
    monthly_summary["核定油費"] = ""
    monthly_summary["核定日當費"] = ""
    monthly_summary["核定狀態"] = ""
    monthly_summary["核定備註"] = ""

    detail_sheet = detail_events[
        [
            "work_date",
            "employee_id",
            "employee_name",
            "department",
            "attendance_uid",
            "actual_time_display",
            "card_type",
            "compare_result",
            "source_type",
            "exception_action",
            "overtime_flag",
            "overtime_reason",
            "gps_lat",
            "gps_lon",
            "nearest_client_name",
            "nearest_client_meter",
            "nearest_hospital_only_name",
            "nearest_hospital_only_meter",
            "selected_hospital_label_detail",
            "selected_hospital_meter_detail",
            "selected_hospital_type_detail",
        ]
    ].rename(
        columns={
            "work_date": "日期",
            "employee_id": "員工編號",
            "employee_name": "員工姓名",
            "department": "部門",
            "attendance_uid": "attendance_uid",
            "actual_time_display": "打卡時間",
            "card_type": "卡別",
            "compare_result": "比對結果",
            "source_type": "來源",
            "exception_action": "異常處理",
            "overtime_flag": "超時出勤標記",
            "overtime_reason": "超時出勤原因",
            "gps_lat": "緯度",
            "gps_lon": "經度",
            "nearest_client_name": "最近既有客戶",
            "nearest_client_meter": "最近既有客戶距離(m)",
            "nearest_hospital_only_name": "最近醫院",
            "nearest_hospital_only_meter": "最近醫院距離(m)",
            "selected_hospital_label_detail": "系統選定院所",
            "selected_hospital_meter_detail": "系統選定距離(m)",
            "selected_hospital_type_detail": "系統選定類型",
        }
    )
    detail_sheet["日期"] = pd.to_datetime(detail_sheet["日期"], errors="coerce").dt.strftime("%Y-%m-%d")

    instruction_rows = [
        ["工作表", "用途", "填寫說明"],
        ["員工月度彙總", "給業務助理 / 財會快速查看每位員工每月估算里程與補貼總額。", "可填寫：核定油費、核定日當費、核定狀態、核定備註。"],
        ["月度核定總表", "一列一筆員工單日出勤，供檢視每日里程、時數、預測拜訪院所。", "可依日期、員工、部門篩選，作為日當費 / 油費核定參考。"],
        ["每日拜訪明細", "一列一個打卡點，供追查單點來源、最近既有客戶、最近醫院與系統選定。", "若需要覆核當天拜訪脈絡，可回看這張明細。"],
        ["欄位說明", "系統選定院所 = 既有客戶優先，其次 1000m 內醫院，最後才是潛在院所。", "本報表僅供核定參考，實際核定結果仍以助理 / 財會填寫回傳為準。"],
    ]

    return {
        "sheet_order": ["員工月度彙總", "月度核定總表", "每日拜訪明細", "填寫說明"],
        "sheets": {
            "員工月度彙總": dataframe_to_sheet_rows(monthly_summary),
            "月度核定總表": dataframe_to_sheet_rows(daily_sheet),
            "每日拜訪明細": dataframe_to_sheet_rows(detail_sheet),
            "填寫說明": instruction_rows,
        },
    }


def export_google_sheet_reference_report(payload: dict, output_path: Path) -> Path:
    base_dir = Path(__file__).resolve().parent
    ensure_artifact_tool_node_modules(base_dir)
    builder_path = base_dir / "tools" / "build_google_sheet_report.mjs"
    payload_path = output_path.with_suffix(".json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run(
        [find_node_executable(), str(builder_path), str(payload_path), str(output_path)],
        check=True,
        cwd=base_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return output_path


tables = load_results()
config = tables["config"]
attendance = tables["attendance"]
routes = tables["routes"]
finance = tables["finance"]
daily_metrics = tables["daily_metrics"]
raw_events = tables["raw_events"]
matches = tables["matches"]
employees = tables["employees"]
google_route_summary = tables["google_route_summary"]
google_route_cache = tables["google_route_cache"]
google_route_cache_detail = tables["google_route_cache_detail"]
monthly_claims_path = Path(config.data_dir) / "monthly_claims.csv"
monthly_claims = pd.read_csv(monthly_claims_path, encoding="utf-8-sig") if monthly_claims_path.exists() else pd.DataFrame()
monthly_claim_comparison = build_monthly_claim_comparison(
    routes=routes,
    monthly_claims=monthly_claims,
    green_threshold=float(config.light_green_pct),
    yellow_threshold=float(config.light_yellow_pct),
)

raw_events["employee_label"] = raw_events.apply(
    lambda row: make_employee_label(row["employee_id"], row["employee_name"]),
    axis=1,
)
raw_events["actual_time_display"] = raw_events["actual_time"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("未提供")
attendance_event_flags = build_attendance_event_flags(raw_events)
routes["work_date"] = pd.to_datetime(routes["work_date"], errors="coerce")
finance["work_date"] = pd.to_datetime(finance["work_date"], errors="coerce")

employee_options = (
    attendance[["employee_id", "employee_label"]]
    .dropna(subset=["employee_id"])
    .drop_duplicates()
    .sort_values("employee_id")
)
employee_label_map = dict(zip(employee_options["employee_label"], employee_options["employee_id"]))

st.title("Function Route Report")
st.caption("以單日路徑檢視、個人期間報表與可匯出結果為核心的業務出勤分析介面")
st.markdown(
    """
    <div class="hero-card">
        <div class="hero-title">業務出勤、路徑與月週期報表</div>
        <div class="hero-subtitle">先看單日路徑，再看個人期間報表；同一套介面可支援月報、週報與短期監測。</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("操作")
    st.write(f"資料來源: `{config.data_dir}`")
    st.write(f"輸出路徑: `{config.output_dir}`")
    rerun = st.button("重新整理最新資料", width="stretch")

if rerun:
    st.cache_data.clear()
    st.rerun()


tab_demo, tab_daily, tab_period = st.tabs(["🎉 專案展示 (Demo Home)", "📍 單日出勤軌跡 (Daily Map)", "📊 月報異常稽核 (Audit Report)"])

with tab_demo:
    st.markdown(
        """
        <div style='background: rgba(255, 255, 255, 0.4); backdrop-filter: blur(10px); padding: 4rem 2rem; border-radius: 20px; text-align: center; border: 1px solid rgba(255,255,255,0.6); margin-bottom: 2rem; margin-top: 1rem;'>
            <h1 style='font-size: 3.5rem; font-weight: 900; color: #0f172a; margin-bottom: 1rem;'>Data-Driven Field Sales Audit</h1>
            <p style='font-size: 1.3rem; color: #334155;'>完全無縫整合企業 104 HR 行動打卡紀錄，透過 Google Routes API 軌跡還原技術，<br>自動化排查異常出勤、預估真實公務里程，杜絕浮報油資，打造公平透明的業務績效環境。</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    col1.markdown("""
    <div style='background: rgba(255,255,255,0.8); padding: 2rem; border-radius: 16px; height: 100%; border: 1px solid rgba(0,0,0,0.05); box-shadow: 0 4px 15px rgba(0,0,0,0.03);'>
        <h3 style='font-size: 1.4rem; color: #1d4ed8; margin-bottom: 1rem;'>🎯 科學化軌跡還原</h3>
        <p style='color: #475569; line-height: 1.6;'>打破過去「只看單點距離」的盲點，系統根據打卡時間序重組行車路徑，串接 Google Routes API 計算最真實的行車距離與移動時間，讓好員工不委屈，異常行為無所遁形。</p>
    </div>
    """, unsafe_allow_html=True)
    
    col2.markdown("""
    <div style='background: rgba(255,255,255,0.8); padding: 2rem; border-radius: 16px; height: 100%; border: 1px solid rgba(0,0,0,0.05); box-shadow: 0 4px 15px rgba(0,0,0,0.03);'>
        <h3 style='font-size: 1.4rem; color: #16a34a; margin-bottom: 1rem;'>🚦 自動化異常稽核</h3>
        <p style='color: #475569; line-height: 1.6;'>透過自訂寬容值(例如15%、30%)，系統自動將業務的油資申報與「系統推估值」進行比對，標記出「綠燈(合格)、黃燈(注意)、紅燈(異常)」，讓財務審核時間從數天縮短為數分鐘。</p>
    </div>
    """, unsafe_allow_html=True)
    
    col3.markdown("""
    <div style='background: rgba(255,255,255,0.8); padding: 2rem; border-radius: 16px; height: 100%; border: 1px solid rgba(0,0,0,0.05); box-shadow: 0 4px 15px rgba(0,0,0,0.03);'>
        <h3 style='font-size: 1.4rem; color: #e11d48; margin-bottom: 1rem;'>🔒 無痛零信任導入</h3>
        <p style='color: #475569; line-height: 1.6;'>系統完全不侵犯設備隱私，業務無須安裝任何監控 App 或更改現有操作流程。所有分析均基於既有的人資打卡 GPS 資料運行，實現真正的無痕管理與零信任架構落地。</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style='margin-top: 3rem; background: #f8fafc; padding: 2rem; border-radius: 12px; border-left: 6px solid #475569;'>
        <h4 style='margin: 0 0 1rem 0; color: #334155;'>💡 Demo 情境導覽建議</h4>
        <ul style='color: #475569; line-height: 1.8; margin: 0;'>
            <li><b>單日出勤軌跡</b>: 切換至 [📍 單日出勤軌跡] 頁籤，選擇模範員工「張守規」查看完美還原的拜訪路徑；再切換至問題員工「李繞路」，觀察系統如何精準列出他在家打卡、偏離合理區域出勤等異常點，並藉由打卡推估的正常路線里程，來跟員工浮報的里程作比對。</li>
            <li><b>月報異常稽核</b>: 切換至 [📊 月報異常稽核] 頁籤，查看月度總表。系統會直接把李繞路浮報 85km 的誇張行為標為紅燈，供財會查核。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("<h3 style='text-align: center; color: #1e293b; margin-top:2rem;'>📊 全局差異稽核 (員工申報 vs 系統嚴謹推估)</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; margin-bottom:2rem;'>一眼看穿老實業務與浮報業務的差異，將原本耗時的財務審核縮短為一秒鐘的視覺化判斷。</p>", unsafe_allow_html=True)
    
    if "monthly_claim_comparison" in globals() and not monthly_claim_comparison.empty:
        claim_bar_df = monthly_claim_comparison.melt(
            id_vars=["employee_id", "employee_label", "department"],
            value_vars=["claimed_km", "estimated_business_km"],
            var_name="指標",
            value_name="公里數",
        )
        claim_bar_df["指標"] = claim_bar_df["指標"].replace({"claimed_km": "員工自行申報里程", "estimated_business_km": "系統推估合理里程"})
        fig_claim_bar = px.bar(
            claim_bar_df,
            x="employee_label",
            y="公里數",
            color="指標",
            barmode="group",
            hover_data=["department"],
            labels={"employee_label": "員工", "公里數": "公里數", "department": "部門"},
            color_discrete_sequence=["#e11d48", "#10b981"]
        )
        fig_claim_bar.update_layout(
            height=450,
            margin=dict(l=40, r=40, t=20, b=10),
            xaxis_tickangle=0,
            plot_bgcolor="rgba(255,255,255,0.3)",
            paper_bgcolor="rgba(255,255,255,0)"
        )
        st.plotly_chart(fig_claim_bar, width="stretch")


with tab_daily:
    st.subheader("單日出勤路徑")
    filter_col1, filter_col2, filter_col3 = st.columns([1.65, 1.0, 1.35])
    selected_employee_label = filter_col1.selectbox(
        "選擇業務",
        options=employee_options["employee_label"].tolist(),
        index=0,
    )
    selected_employee_id = employee_label_map[selected_employee_label]
    available_dates = (
        attendance.loc[attendance["employee_id"] == selected_employee_id, "work_date"]
        .dropna()
        .sort_values()
        .dt.date
        .unique()
        .tolist()
    )
    selected_date = filter_col2.selectbox("選擇日期", options=available_dates, index=len(available_dates) - 1)

    day_attendance = attendance.loc[
        (attendance["employee_id"] == selected_employee_id) & (attendance["work_date"].dt.date == selected_date)
    ].copy()
    day_events = raw_events.loc[
        (raw_events["employee_id"] == selected_employee_id) & (raw_events["work_date"].dt.date == selected_date)
    ].copy()
    day_route = routes.loc[routes["attendance_uid"].isin(day_attendance["attendance_uid"])].copy()
    day_finance = finance.loc[finance["attendance_uid"].isin(day_attendance["attendance_uid"])].copy()
    if isinstance(google_route_cache, pd.DataFrame) and not google_route_cache.empty:
        cache_lookup = google_route_cache.copy()
        if "attendance_key" not in cache_lookup.columns:
            cache_lookup["attendance_key"] = cache_lookup["attendance_uid"].astype("string").str.split("_").str[:3].str.join("_")
        day_google_segments = cache_lookup.loc[
            cache_lookup["attendance_key"].isin(day_attendance["attendance_key"])
        ].copy()
    else:
        day_google_segments = pd.DataFrame()

    employee_row = employees.loc[employees["employee_id"] == selected_employee_id].head(1)
    employee_row = employee_row.iloc[0] if not employee_row.empty else None

    simulate_api = st.toggle("👉 模擬串接 Google Routes API (還原實際路徑)", value=False)
    if simulate_api and len(day_events) > 0:
        @st.cache_data(show_spinner=False)
        def fetch_osrm_polyline(lat1, lon1, lat2, lon2):
            import urllib.request, json
            try:
                url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as res:
                    data = json.loads(res.read())
                    return data["routes"][0]["geometry"]
            except Exception:
                return ""

        fake_segments = []
        gps_events_for_curve = day_events.dropna(subset=["gps_lat", "gps_lon"]).sort_values(["actual_time"])
        if not gps_events_for_curve.empty:
            att_uid = day_attendance["attendance_uid"].iloc[0] if not day_attendance.empty else ""
            points = [(float(row["gps_lat"]), float(row["gps_lon"])) for _, row in gps_events_for_curve.iterrows()]
            seg_no = 1
            if employee_row is not None and pd.notna(employee_row.get("home_lat")):
                home_pt = (float(employee_row["home_lat"]), float(employee_row["home_lon"]))
                fake_segments.append({
                    "attendance_uid": att_uid,
                    "segment_no": seg_no, "segment_type": "home_to_first",
                    "polyline": fetch_osrm_polyline(home_pt[0], home_pt[1], points[0][0], points[0][1])
                })
                seg_no += 1
            for i in range(len(points)-1):
                fake_segments.append({
                    "attendance_uid": att_uid,
                    "segment_no": seg_no, "segment_type": "between_points",
                    "polyline": fetch_osrm_polyline(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
                })
                seg_no += 1
            if employee_row is not None and pd.notna(employee_row.get("home_lat")):
                fake_segments.append({
                    "attendance_uid": att_uid,
                    "segment_no": seg_no, "segment_type": "last_to_home",
                    "polyline": fetch_osrm_polyline(points[-1][0], points[-1][1], home_pt[0], home_pt[1])
                })
        day_google_segments = pd.DataFrame(fake_segments)

    filter_col3.markdown(
        f"""
        <div class="section-card" style="padding:0.85rem 1rem;">
            <div class="candidate-title">{selected_employee_label}</div>
            <div class="candidate-sub">日期：{selected_date}</div>
            <div class="candidate-sub">當日事件數：{len(day_events)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    summary_left, summary_mid, summary_right, summary_extra, summary_more, summary_commute = st.columns(
        [1.45, 1.05, 1.1, 1.1, 1.0, 1.15]
    )
    if not day_route.empty and not day_attendance.empty:
        route_row = day_route.iloc[0]
        attendance_row = day_attendance.iloc[0]
        event_flag_row = attendance_event_flags.loc[attendance_event_flags["attendance_uid"] == attendance_row["attendance_uid"]].head(1)
        event_flag_row = event_flag_row.iloc[0] if not event_flag_row.empty else None
        commute_estimate = build_commute_estimate(attendance_row, day_events, employee_row, day_google_segments, config)
        summary_left.metric("出勤時段", f"{str(attendance_row['first_actual_time'])[11:16]}-{str(attendance_row['last_actual_time'])[11:16]}")
        summary_mid.metric("打卡 / GPS 點數", f"{int(attendance_row['event_count'])} / {int(attendance_row['gps_event_count'])}")
        summary_right.metric("預估總里程", f"{route_row['estimated_total_km']:.2f} km")
        summary_extra.metric("公務里程", f"{route_row['estimated_business_km']:.2f} km")
        summary_more.metric("路徑信心", f"{route_row['route_confidence']:.2%}")
        summary_commute.metric("預估通勤時間", f"{commute_estimate['commute_min']:.1f} 分")
        info_col1, info_col2, info_col3, info_col4 = st.columns(4)
        info_col1.caption(f"異常摘要：{attendance_row['compare_result_summary'] if pd.notna(attendance_row['compare_result_summary']) else '無'}")
        info_col2.caption(f"預估移動時間：{route_row['estimated_travel_min']:.1f} 分")
        info_col3.caption(f"匹配院所數：{int(route_row['matched_stop_count'])} / {int(route_row['total_stop_count'])}")
        unresolved_count = int(event_flag_row["missing_punch_unprocessed_count"]) if event_flag_row is not None else 0
        info_col4.caption(f"未打卡未處理：{unresolved_count} 次")

    st.markdown("**地圖路徑**")
    st.markdown('<div class="daily-map-card">', unsafe_allow_html=True)
    st.plotly_chart(build_daily_map(day_events, employee_row, day_google_segments), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)
    if employee_row is not None and pd.notna(employee_row.get("home_lat")) and pd.notna(employee_row.get("home_lon")):
        if not day_google_segments.empty:
            st.caption("已套用 Google Routes basic polyline。地圖中藍色點為住家，藍線為住家到首點，綠線為行車路徑，紫線為末點回住家。里程計算已包含住家到首點與末點回住家。")
        else:
            st.caption("目前里程計算已包含住家到第一個打卡點，以及最後一個打卡點回住家的距離。地圖中藍色點為住家，藍線為住家到首點，紫線為末點回住家。")

    candidate_panel = build_candidate_panel(day_events, matches)
    render_candidate_cards(candidate_panel)

    event_detail = day_events[
        [
            "actual_time_display",
            "card_type",
            "gps_lat",
            "gps_lon",
            "compare_result",
            "source_type",
            "nearest_client_name",
            "nearest_client_meter",
            "nearest_hospital_name",
            "nearest_hospital_meter",
            "nearest_hospital_only_name",
            "nearest_hospital_only_meter",
            "selected_hospital_name",
            "selected_client_tag",
        ]
    ].rename(
        columns={
            "actual_time_display": "時間",
            "card_type": "卡別",
            "gps_lat": "緯度",
            "gps_lon": "經度",
            "compare_result": "比對結果",
            "source_type": "來源",
            "nearest_client_name": "最近既有客戶",
            "nearest_client_meter": "最近既有客戶距離(公尺)",
            "nearest_hospital_name": "最近院所",
            "nearest_hospital_meter": "最近院所距離(公尺)",
            "nearest_hospital_only_name": "最近醫院",
            "nearest_hospital_only_meter": "最近醫院距離(公尺)",
            "selected_hospital_name": "預估院所",
            "selected_client_tag": "院所類型",
        }
    )
    detail_tab, finance_tab = st.tabs(["當日事件明細", "當日財務摘要"])
    with detail_tab:
        st.dataframe(
            event_detail,
            width="stretch",
            hide_index=True,
            column_config={
                "緯度": st.column_config.NumberColumn(format="%.6f"),
                "經度": st.column_config.NumberColumn(format="%.6f"),
                "最近既有客戶距離(公尺)": st.column_config.NumberColumn(format="%.0f m"),
                "最近院所距離(公尺)": st.column_config.NumberColumn(format="%.0f m"),
                "最近醫院距離(公尺)": st.column_config.NumberColumn(format="%.0f m"),
            },
        )
    with finance_tab:
        if not day_finance.empty:
            st.dataframe(
                day_finance[
                    [
                        "employee_label",
                        "employee_claim_km",
                        "approved_business_km",
                        "audit_light",
                        "fuel_subsidy",
                        "maintenance_subsidy",
                        "per_diem_amount",
                        "audit_status",
                    ]
                ].rename(
                    columns={
                        "employee_label": "員工",
                        "employee_claim_km": "月申請里程",
                        "approved_business_km": "當日公務里程",
                        "audit_light": "燈號",
                        "fuel_subsidy": "油資補貼",
                        "maintenance_subsidy": "維修補貼",
                        "per_diem_amount": "日當費",
                        "audit_status": "審核狀態",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("這一天目前沒有財務摘要資料。")

with tab_period:
    st.subheader("個人期間報表")
    period_col1, period_col2, period_col3 = st.columns([1.7, 1.2, 1.2])
    period_employee_label = period_col1.selectbox(
        "選擇員工",
        options=employee_options["employee_label"].tolist(),
        index=0,
        key="period_employee",
    )
    period_employee_id = employee_label_map[period_employee_label]
    period_mode = period_col2.selectbox("報表模式", options=["月報", "週報", "自訂區間"], index=0)

    employee_dates = (
        attendance.loc[attendance["employee_id"] == period_employee_id, "work_date"]
        .dropna()
        .sort_values()
    )
    min_date = employee_dates.min().date()
    max_date = employee_dates.max().date()

    if period_mode == "月報":
        period_list = sorted(employee_dates.dt.to_period("M").astype(str).unique().tolist())
        selected_period = period_col3.selectbox("月份", options=period_list, index=len(period_list) - 1)
        month_dates = employee_dates.loc[employee_dates.dt.to_period("M").astype(str) == selected_period]
        start_date = month_dates.min().date()
        end_date = month_dates.max().date()
    elif period_mode == "週報":
        week_series = employee_dates.dt.strftime("%G-W%V")
        week_list = sorted(week_series.unique().tolist())
        selected_period = period_col3.selectbox("週次", options=week_list, index=len(week_list) - 1)
        week_dates = employee_dates.loc[employee_dates.dt.strftime("%G-W%V") == selected_period]
        start_date = week_dates.min().date()
        end_date = week_dates.max().date()
    else:
        date_range = period_col3.date_input("日期區間", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = min_date
        selected_period = f"{start_date} ~ {end_date}"

    summary_df, detail_df = summarize_period(period_employee_id, start_date, end_date, attendance, daily_metrics, routes, attendance_event_flags)
    period_months = months_in_range(start_date, end_date)
    period_monthly_claims = monthly_claim_comparison.loc[
        (monthly_claim_comparison["employee_id"] == period_employee_id)
        & (monthly_claim_comparison["year_month"].isin(period_months))
    ].copy()

    if summary_df.empty:
        st.warning("目前選擇條件沒有對應資料。")
    else:
        summary_row = summary_df.iloc[0]
        metric_row1 = st.columns(4)
        metric_row1[0].metric("總出勤時數", f"{summary_row['總出勤時數']:.2f} 小時")
        metric_row1[1].metric("總打卡次數", int(summary_row["總打卡次數"]))
        metric_row1[2].metric("異常率", f"{summary_row['異常率']:.2%}")
        metric_row1[3].metric("超時出勤率", f"{summary_row['超時出勤率']:.2%}")
        metric_row2 = st.columns(4)
        metric_row2[0].metric("總有效外勤時數", f"{summary_row['總有效外勤時數']:.2f} 小時")
        metric_row2[1].metric("總GPS點數", int(summary_row["總GPS點數"]))
        metric_row2[2].metric("總計預估里程", f"{summary_row['總計預估里程']:.2f} km")
        metric_row2[3].metric("總計預估公務里程", f"{summary_row['總計預估公務里程']:.2f} km")
        metric_row3 = st.columns(4)
        metric_row3[0].metric("平均每日里程", f"{summary_row['平均每日里程']:.2f} km")
        metric_row3[1].metric("平均每日公務里程", f"{summary_row['平均每日公務里程']:.2f} km")
        metric_row3[2].metric("未打卡未處理次數", int(summary_row["未打卡未處理次數"]))
        metric_row3[3].metric("實際加班率", f"{summary_row['實際加班率']:.2%}")
        metric_row4 = st.columns(4)
        metric_row4[0].metric("忘刷申請總次數", int(summary_row["忘刷申請總次數"]))

        st.markdown("**報表摘要**")
        summary_show = summary_df.rename(columns={"總匹配院所次數": "匹配院所總次數"})
        st.dataframe(summary_show, width="stretch", hide_index=True)

        st.markdown("**月申請里程 vs 系統預估公務里程**")
        st.caption("以所選期間涵蓋到的月份整月比較，因此週報或自訂區間也會顯示對應月份的整月申請與整月預估。")
        period_claim_cols = st.columns(4)
        if period_monthly_claims.empty:
            period_claim_cols[0].metric("月申請里程", "-")
            period_claim_cols[1].metric("月預估公務里程", "-")
            period_claim_cols[2].metric("差異里程", "-")
            period_claim_cols[3].metric("差異率", "-")
            st.info("所選月份目前沒有可比較的月申請里程資料。")
        else:
            claim_total = float(period_monthly_claims["claimed_km"].fillna(0).sum())
            estimate_total = float(period_monthly_claims["estimated_business_km"].fillna(0).sum())
            diff_total = float(period_monthly_claims["difference_km"].fillna(0).sum())
            diff_rate = (diff_total / claim_total) if claim_total > 0 else np.nan
            period_claim_cols[0].metric("月申請里程", f"{claim_total:.2f} km")
            period_claim_cols[1].metric("月預估公務里程", f"{estimate_total:.2f} km")
            period_claim_cols[2].metric("差異里程", f"{diff_total:+.2f} km")
            period_claim_cols[3].metric("差異率", f"{diff_rate:.2%}" if pd.notna(diff_rate) else "-")
            period_claim_table = period_monthly_claims.rename(
                columns={
                    "year_month": "月份",
                    "claimed_km": "實際月申請里程",
                    "estimated_business_km": "系統預估月公務里程",
                    "difference_km": "差異里程",
                    "difference_rate": "差異率",
                    "comparison_light": "比較燈號",
                }
            )
            st.dataframe(
                period_claim_table,
                width="stretch",
                hide_index=True,
                column_config={
                    "實際月申請里程": st.column_config.NumberColumn(format="%.2f km"),
                    "系統預估月公務里程": st.column_config.NumberColumn(format="%.2f km"),
                    "差異里程": st.column_config.NumberColumn(format="%+.2f km"),
                    "差異率": st.column_config.NumberColumn(format="%.2%"),
                },
            )

        employee_matches = matches.loc[
            matches["attendance_uid"].isin(
                attendance.loc[
                    (attendance["employee_id"] == period_employee_id)
                    & attendance["work_date"].dt.date.between(start_date, end_date),
                    "attendance_uid",
                ]
            )
        ].copy()
        top_hospitals = (
            employee_matches.loc[employee_matches["is_selected"] == 1]
            .groupby(["hospital_label", "client_tag"])
            .size()
            .reset_index(name="拜訪次數")
            .sort_values("拜訪次數", ascending=False)
            .head(10)
            .rename(columns={"hospital_label": "院所名稱", "client_tag": "客戶類型"})
        )

        chart_col1, chart_col2 = st.columns([1, 1.25])
        with chart_col1:
            st.markdown("**最常拜訪院所**")
            st.dataframe(top_hospitals, width="stretch", hide_index=True)
        with chart_col2:
            st.markdown("**每日明細**")
            st.dataframe(
                detail_df,
                width="stretch",
                hide_index=True,
                height=420,
                column_config={
                    "預估總里程": st.column_config.NumberColumn(format="%.2f km"),
                    "預估公務里程": st.column_config.NumberColumn(format="%.2f km"),
                    "總出勤分鐘": st.column_config.NumberColumn(format="%.1f"),
                    "有效外勤分鐘": st.column_config.NumberColumn(format="%.1f"),
                    "預估移動分鐘": st.column_config.NumberColumn(format="%.1f"),
                    "未打卡未處理次數": st.column_config.NumberColumn(format="%d"),
                    "未打卡已處理次數": st.column_config.NumberColumn(format="%d"),
                    "忘刷申請次數": st.column_config.NumberColumn(format="%d"),
                    "超時出勤": st.column_config.CheckboxColumn(),
                    "實際加班": st.column_config.CheckboxColumn(),
                    "個人因素超時": st.column_config.CheckboxColumn(),
                },
            )

        export_col1, export_col2 = st.columns(2)
        export_col1.download_button(
            "下載摘要 CSV",
            data=to_csv_bytes(summary_df),
            file_name=f"{period_employee_id}_{selected_period}_summary.csv".replace(" ", "_").replace("~", "to"),
            mime="text/csv",
            width="stretch",
        )
        export_col2.download_button(
            "下載明細 CSV",
            data=to_csv_bytes(detail_df),
            file_name=f"{period_employee_id}_{selected_period}_detail.csv".replace(" ", "_").replace("~", "to"),
            mime="text/csv",
            width="stretch",
        )

        finance_detail = finance.loc[
            (finance["employee_id"] == period_employee_id)
            & finance["work_date"].dt.date.between(start_date, end_date)
        ][
            [
                "work_date",
                "employee_label",
                "employee_claim_km",
                "approved_business_km",
                "audit_light",
                "fuel_subsidy",
                "maintenance_subsidy",
                "per_diem_amount",
                "audit_status",
            ]
        ].rename(
            columns={
                "work_date": "日期",
                "employee_label": "員工",
                "employee_claim_km": "月申請里程",
                "approved_business_km": "當日公務里程",
                "audit_light": "燈號",
                "fuel_subsidy": "油資補貼",
                "maintenance_subsidy": "維修補貼",
                "per_diem_amount": "日當費",
                "audit_status": "審核狀態",
            }
        )
        st.markdown("**期間財務明細**")
        st.dataframe(
            finance_detail,
            width="stretch",
            hide_index=True,
            column_config={
                "月申請里程": st.column_config.NumberColumn(format="%.2f km"),
                "當日公務里程": st.column_config.NumberColumn(format="%.2f km"),
                "油資補貼": st.column_config.NumberColumn(format="%.2f"),
                "維修補貼": st.column_config.NumberColumn(format="%.2f"),
                "日當費": st.column_config.NumberColumn(format="%.2f"),
            },
        )
