from __future__ import annotations

import json
from io import StringIO
from math import cos, log, radians
import os

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
    include = tuple(hospital_keywords or ("醫院", "醫學中心", "榮總"))
    exclude = tuple(exclude_keywords or ("診所", "藥局", "衛生所"))
    return any(keyword in text for keyword in include) and not any(keyword in text for keyword in exclude)

def chunked(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


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
    config = build_config()
    run_pipeline(config)
    base = config.cleaned_dir
    attendance = pd.read_csv(base / "attendance_day_group.csv", encoding="utf-8-sig")
    routes = pd.read_csv(base / "daily_route_summary.csv", encoding="utf-8-sig")
    finance = pd.read_csv(base / "finance_audit_result.csv", encoding="utf-8-sig")
    daily_metrics = pd.read_csv(base / "bi_daily_metrics.csv", encoding="utf-8-sig")
    raw_events = pd.read_csv(base / "raw_check_events.csv", encoding="utf-8-sig")
    matches = pd.read_csv(base / "route_stop_match.csv", encoding="utf-8-sig")
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

    selected_match = (
        match_enriched.loc[match_enriched["is_selected"] == 1, ["event_uid", "hospital_id", "hospital_name", "client_tag"]]
        .drop_duplicates(subset=["event_uid"])
        .rename(
            columns={
                "hospital_id": "selected_hospital_id",
                "hospital_name": "selected_hospital_name",
                "client_tag": "selected_client_tag",
            }
        )
    )
    nearest_match = (
        match_enriched.loc[match_enriched["candidate_rank"] == 1, ["event_uid", "hospital_name", "beeline_meter"]]
        .drop_duplicates(subset=["event_uid"])
        .rename(columns={"hospital_name": "nearest_hospital_name", "beeline_meter": "nearest_hospital_meter"})
    )
    nearest_hospital_only = build_nearest_hospital_lookup(raw_events, hospitals, config)
    raw_events = raw_events.merge(selected_match, on="event_uid", how="left")
    raw_events = raw_events.merge(nearest_match, on="event_uid", how="left")
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
        candidate_items = []
        for _, row in group.head(5).iterrows():
            candidate_items.append(
                {
                    "rank": int(row["candidate_rank"]),
                    "name": row["hospital_label"],
                    "distance": float(row["beeline_meter"]),
                    "tag": row["client_tag"],
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
            <div class="candidate-sub">依每個 GPS 打卡點列出最近院所、最近醫院、系統選定院所與前五候選名單。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for row_panels in chunked(candidate_panels, 3):
        columns = st.columns(3)
        for column, panel in zip(columns, row_panels):
            selected_tag_class = "tag-client" if panel["selected_client_tag"] == "既有客戶" else "tag-potential"
            selected_tag = panel["selected_client_tag"] or "未判定"
            nearest_facility_text = (
                f"{panel['nearest_hospital_name']} · {panel['nearest_hospital_meter']:.0f} m"
                if panel["nearest_hospital_name"] and panel["nearest_hospital_meter"] is not None
                else "無最近院所資料"
            )
            nearest_text = (
                f"{panel['nearest_hospital_only_name']} · {panel['nearest_hospital_only_meter']:.0f} m"
                if panel["nearest_hospital_only_name"] and panel["nearest_hospital_only_meter"] is not None
                else "醫院主檔中沒有可判定為醫院的院所"
            )
            list_items = []
            for item in panel["candidates"]:
                tag_class = "tag-client" if item["tag"] == "既有客戶" else "tag-potential"
                list_items.append(
                    f"<li>{item['rank']}. {item['name']} · {item['distance']:.0f} m "
                    f"<span class=\"{tag_class}\">{item['tag']}</span></li>"
                )
            selected_name = panel["selected_hospital_name"] or "未判定"
            html = f"""
            <div class="candidate-card">
                <div class="candidate-title">#{panel['seq_no']} {panel['time']}</div>
                <div class="candidate-sub">座標：{panel['lat']:.6f}, {panel['lon']:.6f}</div>
                <div class="candidate-sub">最近院所：{nearest_facility_text}</div>
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
    merged["overtime_flag_bool"] = merged["compare_result_summary"].fillna("").astype(str).str.contains("超時")
    merged["employee_label"] = merged["employee_label"].fillna(
        merged.apply(lambda row: make_employee_label(row["employee_id"], row["employee_name"]), axis=1)
    )

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
                "異常率": round(float(merged["anomaly_flag"].fillna(False).mean()), 4),
                "超時出勤率": round(float(merged["overtime_flag_bool"].fillna(False).mean()), 4),
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

    merged = base.merge(metrics, on="attendance_uid", how="left", suffixes=("", "_metric"))
    merged = merged.merge(route_slice, on="attendance_uid", how="left")
    merged = merged.merge(finance_slice, on="attendance_uid", how="left")
    merged["overtime_flag_bool"] = merged["compare_result_summary"].fillna("").astype(str).str.contains("超時")

    summary = (
        merged.groupby(["employee_id", "employee_label", "department"], dropna=False)
        .agg(
            出勤天數=("attendance_uid", "nunique"),
            總出勤時數=("raw_span_minutes", lambda s: round(s.fillna(0).sum() / 60, 2)),
            總GPS點數=("gps_event_count", lambda s: int(s.fillna(0).sum())),
            總打卡次數=("event_count", lambda s: int(s.fillna(0).sum())),
            總計預估里程=("estimated_total_km", lambda s: round(s.fillna(0).sum(), 2)),
            總計預估公務里程=("estimated_business_km", lambda s: round(s.fillna(0).sum(), 2)),
            平均路徑信心=("route_confidence", lambda s: round(s.fillna(0).mean(), 4)),
            異常率=("anomaly_flag", lambda s: round(float(s.fillna(False).mean()), 4)),
            超時出勤率=("overtime_flag_bool", lambda s: round(float(s.fillna(False).mean()), 4)),
            油資補貼=("fuel_subsidy", lambda s: round(s.fillna(0).sum(), 2)),
            維修補貼=("maintenance_subsidy", lambda s: round(s.fillna(0).sum(), 2)),
            日當費=("per_diem_amount", lambda s: round(s.fillna(0).sum(), 2)),
        )
        .reset_index()
        .sort_values(["總計預估里程", "異常率"], ascending=[False, False])
    )
    return summary


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

raw_events["employee_label"] = raw_events.apply(
    lambda row: make_employee_label(row["employee_id"], row["employee_name"]),
    axis=1,
)
raw_events["actual_time_display"] = raw_events["actual_time"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("未提供")
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

tab_home, tab_daily, tab_period, tab_overview, tab_routes_api, tab_settings, tab_guide, tab_quality = st.tabs(
    ["首頁流程", "單日路徑檢視", "個人期間報表", "全業務總覽", "Google Routes 執行", "參數設定", "指標說明", "資料品質與說明"]
)

with tab_home:
    st.subheader("實務操作流程")
    st.caption("依實際月度作業流程設計。點擊節點後，會在下方展開對應的編輯或匯入區塊。")
    action_rows = [
        [
            ("醫療院所資料設定", "hospitals"),
            ("既有客戶資料", "clients"),
            ("員工資料", "employees"),
        ],
        [
            ("打卡資料匯入", "attendance"),
            ("Google Routes 手動執行", "routes"),
            ("日當費 / 里程核定", "finance"),
        ],
        [
            ("重新整理結果", "refresh"),
        ],
    ]
    for row in action_rows:
        row_cols = st.columns(len(row))
        for column, (label, action) in zip(row_cols, row):
            if column.button(label, key=f"home_{action}", width="stretch"):
                if action == "refresh":
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.session_state["home_action"] = action
    st.markdown("**流程**：主檔設定 → 打卡匯入 → Google Routes 計算（選用） → 日當費 / 里程核定 → 檢視報表與匯出")
    selected_home_action = st.session_state.get("home_action", "employees")
    render_home_action(selected_home_action)


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

    summary_left, summary_mid, summary_right, summary_extra, summary_more = st.columns(5)
    if not day_route.empty and not day_attendance.empty:
        route_row = day_route.iloc[0]
        attendance_row = day_attendance.iloc[0]
        summary_left.metric("出勤時段", f"{str(attendance_row['first_actual_time'])[11:16]} - {str(attendance_row['last_actual_time'])[11:16]}")
        summary_mid.metric("打卡 / GPS 點數", f"{int(attendance_row['event_count'])} / {int(attendance_row['gps_event_count'])}")
        summary_right.metric("預估總里程", f"{route_row['estimated_total_km']:.2f} km")
        summary_extra.metric("公務里程", f"{route_row['estimated_business_km']:.2f} km")
        summary_more.metric("路徑信心", f"{route_row['route_confidence']:.2%}")
        info_col1, info_col2, info_col3 = st.columns(3)
        info_col1.caption(f"異常摘要：{attendance_row['compare_result_summary'] if pd.notna(attendance_row['compare_result_summary']) else '無'}")
        info_col2.caption(f"預估移動時間：{route_row['estimated_travel_min']:.1f} 分")
        info_col3.caption(f"匹配院所數：{int(route_row['matched_stop_count'])} / {int(route_row['total_stop_count'])}")

    employee_row = employees.loc[employees["employee_id"] == selected_employee_id].head(1)
    employee_row = employee_row.iloc[0] if not employee_row.empty else None
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

    summary_df, detail_df = summarize_period(period_employee_id, start_date, end_date, attendance, daily_metrics, routes)

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
        metric_row3 = st.columns(2)
        metric_row3[0].metric("平均每日里程", f"{summary_row['平均每日里程']:.2f} km")
        metric_row3[1].metric("平均每日公務里程", f"{summary_row['平均每日公務里程']:.2f} km")

        st.markdown("**報表摘要**")
        summary_show = summary_df.rename(columns={"總匹配院所次數": "匹配院所總次數"})
        st.dataframe(summary_show, width="stretch", hide_index=True)

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

with tab_overview:
    st.subheader("全業務日期區間總覽")
    overview_col1, overview_col2 = st.columns([1.3, 1.3])
    all_dates = attendance["work_date"].dropna().sort_values()
    overview_start = all_dates.min().date()
    overview_end = all_dates.max().date()
    overview_range = overview_col1.date_input(
        "選擇日期區間",
        value=(overview_start, overview_end),
        min_value=overview_start,
        max_value=overview_end,
        key="overview_range",
    )
    if isinstance(overview_range, tuple) and len(overview_range) == 2:
        overview_start_date, overview_end_date = overview_range
    else:
        overview_start_date = overview_end_date = overview_start

    overview_summary = build_overview_summary(
        attendance,
        daily_metrics,
        routes,
        finance,
        overview_start_date,
        overview_end_date,
    )

    overview_col2.metric("納入比較員工數", len(overview_summary))
    top_row = st.columns(4)
    top_row[0].metric("全員總計預估里程", f"{overview_summary['總計預估里程'].sum():.2f} km")
    top_row[1].metric("全員總計公務里程", f"{overview_summary['總計預估公務里程'].sum():.2f} km")
    top_row[2].metric("平均異常率", f"{overview_summary['異常率'].mean():.2%}" if not overview_summary.empty else "0.00%")
    top_row[3].metric("平均超時率", f"{overview_summary['超時出勤率'].mean():.2%}" if not overview_summary.empty else "0.00%")

    chart1, chart2 = st.columns(2)
    with chart1:
        st.markdown("**各業務總計預估里程比較**")
        if overview_summary.empty:
            st.info("目前日期區間沒有資料。")
        else:
            fig_km = px.bar(
                overview_summary.sort_values("總計預估里程", ascending=False),
                x="employee_label",
                y="總計預估里程",
                color="department",
                text_auto=".1f",
                labels={"employee_label": "員工", "總計預估里程": "總計預估里程(km)", "department": "部門"},
            )
            fig_km.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), xaxis_tickangle=-35)
            st.plotly_chart(fig_km, width="stretch")
    with chart2:
        st.markdown("**異常率 vs 超時出勤率**")
        if overview_summary.empty:
            st.info("目前日期區間沒有資料。")
        else:
            fig_scatter = px.scatter(
                overview_summary,
                x="異常率",
                y="超時出勤率",
                size="總計預估里程",
                color="department",
                hover_name="employee_label",
                labels={"異常率": "異常率", "超時出勤率": "超時出勤率", "department": "部門"},
            )
            fig_scatter.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_scatter, width="stretch")

    chart3, chart4 = st.columns(2)
    with chart3:
        st.markdown("**出勤時數與 GPS 點數比較**")
        if overview_summary.empty:
            st.info("目前日期區間沒有資料。")
        else:
            fig_hours = px.bar(
                overview_summary.sort_values("總出勤時數", ascending=False),
                x="employee_label",
                y=["總出勤時數", "總GPS點數"],
                barmode="group",
                labels={"employee_label": "員工", "value": "數值", "variable": "指標"},
            )
            fig_hours.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), xaxis_tickangle=-35)
            st.plotly_chart(fig_hours, width="stretch")
    with chart4:
        st.markdown("**財務補貼總覽**")
        if overview_summary.empty:
            st.info("目前日期區間沒有資料。")
        else:
            fig_subsidy = px.bar(
                overview_summary.sort_values("油資補貼", ascending=False),
                x="employee_label",
                y=["油資補貼", "維修補貼", "日當費"],
                barmode="stack",
                labels={"employee_label": "員工", "value": "金額", "variable": "補貼項目"},
            )
            fig_subsidy.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), xaxis_tickangle=-35)
            st.plotly_chart(fig_subsidy, width="stretch")

    st.markdown("**全業務明細表**")
    st.dataframe(
        overview_summary.rename(
            columns={
                "employee_id": "員工編號",
                "employee_label": "員工",
                "department": "部門",
            }
        ),
        width="stretch",
        hide_index=True,
        column_config={
            "總計預估里程": st.column_config.NumberColumn(format="%.2f km"),
            "總計預估公務里程": st.column_config.NumberColumn(format="%.2f km"),
            "平均路徑信心": st.column_config.NumberColumn(format="%.2f"),
            "異常率": st.column_config.NumberColumn(format="%.2%"),
            "超時出勤率": st.column_config.NumberColumn(format="%.2%"),
            "油資補貼": st.column_config.NumberColumn(format="%.2f"),
            "維修補貼": st.column_config.NumberColumn(format="%.2f"),
            "日當費": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    st.download_button(
        "下載全業務總覽 CSV",
        data=to_csv_bytes(overview_summary),
        file_name=f"all_employee_overview_{overview_start_date}_to_{overview_end_date}.csv",
        mime="text/csv",
        width="stretch",
    )

with tab_routes_api:
    st.subheader("Google Routes API 手動執行")
    st.caption("若未手動執行，系統會沿用目前的離線估算；執行後會將 Google 路徑結果快取到 SQLite，後續優先取用快取。")
    route_api_col1, route_api_col2, route_api_col3 = st.columns([1.2, 1.2, 1.6])
    all_dates = attendance["work_date"].dropna().sort_values()
    default_start = all_dates.min().date()
    default_end = all_dates.max().date()
    route_api_range = route_api_col1.date_input(
        "估算 / 執行日期區間",
        value=(default_start, default_end),
        min_value=default_start,
        max_value=default_end,
        key="google_routes_range",
    )
    if isinstance(route_api_range, tuple) and len(route_api_range) == 2:
        route_api_start, route_api_end = route_api_range
    else:
        route_api_start = route_api_end = default_start

    route_api_key = route_api_col2.text_input(
        "Google Maps API Key",
        value=os.environ.get("GOOGLE_MAPS_API_KEY", ""),
        type="password",
        help="可直接貼上 API Key，也可先設定 GOOGLE_MAPS_API_KEY 環境變數。",
    )
    current_cache_count = len(google_route_summary) if isinstance(google_route_summary, pd.DataFrame) else 0
    route_api_col3.metric("目前已快取出勤群組", current_cache_count)
    coord_precision = route_api_col3.selectbox(
        "座標快取小數位",
        options=[2, 3, 4, 5, 6],
        index=2,
        help="座標會先四捨五入到指定小數位後再組 cache key，用來容忍 GPS 小幅漂移。",
    )
    st.caption("小數位對應的約略距離：2 位約 1 公里、3 位約 100 公尺、4 位約 10 公尺、5 位約 1 公尺、6 位約 0.1 公尺。")
    if coord_precision < 4:
        st.warning(
            f"目前選擇的是第 {coord_precision} 位小數，這種粒度較容易讓不同路段共用同一個快取鍵。"
            "雖然有機會節省 API 使用量，但也比較可能出現部分路段共用快取、地圖顯示直線補線的情況。"
        )

    attendance_slice = attendance.loc[attendance["work_date"].dt.date.between(route_api_start, route_api_end)].copy()
    estimator = estimate_monthly_usage(
        attendance_slice,
        raw_events,
        employees,
        config.route_mode,
        coord_precision=coord_precision,
    )

    est_cols = st.columns(5)
    est_cols[0].metric("估算員工數", estimator["employees"])
    est_cols[1].metric("估算出勤日", estimator["attendance_days"])
    est_cols[2].metric("GPS 點數", estimator["gps_points"])
    est_cols[3].metric("預估 Routes 呼叫數", estimator["estimated_compute_routes_calls"])
    est_cols[4].metric("Essentials 免費剩餘", estimator["free_cap_remaining"])
    if estimator["free_cap_exceeded"]:
        st.warning("預估本次執行會超過 Essentials 免費額度。")
    else:
        st.success("預估本次執行仍在 Essentials 免費額度內。")

    st.markdown("**月度用量估算器**")
    usage_df = pd.DataFrame([
        {
            "員工數": estimator["employees"],
            "出勤日數": estimator["attendance_days"],
            "GPS 點數": estimator["gps_points"],
            "路徑段數": estimator["route_segments"],
            "預估 Compute Routes 呼叫數": estimator["estimated_compute_routes_calls"],
            "Essentials 免費上限": estimator["free_cap_essentials"],
            "Essentials 免費剩餘": estimator["free_cap_remaining"],
            "是否超額": estimator["free_cap_exceeded"],
            "座標小數位": coord_precision,
        }
    ])
    st.dataframe(usage_df, width="stretch", hide_index=True)

    if st.button("手動執行 Google Routes 計算", width="stretch"):
        if not route_api_key.strip():
            st.error("請先輸入 Google Maps API Key。")
        else:
            with st.spinner("正在呼叫 Google Routes API 並寫入本地快取..."):
                run_result = compute_and_cache_routes(
                    db_path=config.sqlite_path,
                    attendance_slice=attendance_slice,
                    raw_events=raw_events,
                    employees=employees,
                    route_mode=config.route_mode,
                    api_key=route_api_key.strip(),
                    coord_precision=coord_precision,
                )
            st.session_state["last_google_routes_run"] = {
                "start_date": str(route_api_start),
                "end_date": str(route_api_end),
                "coord_precision_selected": int(coord_precision),
                "coord_precision_executed": int(coord_precision),
                "segments": int(run_result["segments"]),
                "api_calls": int(run_result["api_calls"]),
                "cache_hits": int(run_result["cache_hits"]),
                "failed_segments": int(run_result.get("failed_segments", 0)),
            }
            st.success(
                f"已完成 Google Routes 計算：總段數 {run_result['segments']}，新呼叫 API {run_result['api_calls']} 段，命中快取 {run_result['cache_hits']} 段，失敗 {run_result.get('failed_segments', 0)} 段。"
            )
            st.cache_data.clear()
            st.rerun()

    last_google_routes_run = st.session_state.get("last_google_routes_run")
    if last_google_routes_run and last_google_routes_run.get("start_date") == str(route_api_start) and last_google_routes_run.get("end_date") == str(route_api_end):
        st.markdown("**本次執行摘要**")
        run_cols = st.columns(4)
        run_cols[0].metric("本次總段數", last_google_routes_run.get("segments", 0))
        run_cols[1].metric("本次 API 新成功", last_google_routes_run.get("api_calls", 0))
        run_cols[2].metric("本次快取命中", last_google_routes_run.get("cache_hits", 0))
        run_cols[3].metric("本次失敗段數", last_google_routes_run.get("failed_segments", 0))
        st.caption(
            f"本次實際執行使用第 {last_google_routes_run.get('coord_precision_executed')} 位小數作為快取鍵粒度。"
        )

    diagnostics_df = build_google_routes_diagnostics(
        attendance_slice=attendance_slice,
        raw_events=raw_events,
        employees=employees,
        route_mode=config.route_mode,
        coord_precision=coord_precision,
        google_route_summary=google_route_summary,
        google_route_cache_detail=google_route_cache_detail,
    )

    st.markdown("**Google Routes 診斷明細**")
    st.caption("顯示選定日期區間內，每個日期 / attendance_uid 的 API 成功、失敗、只命中快取與缺 polyline 狀況。")
    if diagnostics_df.empty:
        st.info("目前這個日期區間沒有可診斷的出勤資料。")
    else:
        diag_metric_cols = st.columns(5)
        diag_metric_cols[0].metric("出勤群組", len(diagnostics_df))
        diag_metric_cols[1].metric("API 成功", int((diagnostics_df["診斷結果"] == "API 成功").sum()))
        diag_metric_cols[2].metric("只命中快取", int((diagnostics_df["診斷結果"] == "只命中快取").sum()))
        diag_metric_cols[3].metric("有 API 失敗", int((diagnostics_df["失敗段數"] > 0).sum()))
        diag_metric_cols[4].metric("缺 polyline", int((diagnostics_df["缺 polyline 段數"] > 0).sum()))

        diag_labels = ["全部", "API 成功", "只命中快取", "有 API 失敗", "缺 polyline"]
        diag_tabs = st.tabs(diag_labels)
        diag_filters = [
            diagnostics_df,
            diagnostics_df.loc[diagnostics_df["診斷結果"] == "API 成功"],
            diagnostics_df.loc[diagnostics_df["診斷結果"] == "只命中快取"],
            diagnostics_df.loc[diagnostics_df["失敗段數"] > 0],
            diagnostics_df.loc[diagnostics_df["缺 polyline 段數"] > 0],
        ]
        for label, tab, diag_view in zip(diag_labels, diag_tabs, diag_filters):
            with tab:
                if diag_view.empty:
                    st.info("這個分類目前沒有資料。")
                else:
                    st.dataframe(diag_view, width="stretch", hide_index=True)
                    st.download_button(
                        f"下載 {label} 診斷 CSV",
                        data=to_csv_bytes(diag_view),
                        file_name=f"google_routes_diagnostics_{label}_{route_api_start}_to_{route_api_end}.csv",
                        mime="text/csv",
                        width="stretch",
                        key=f"download_diag_{label}",
                    )

with tab_settings:
    st.subheader("參數設定")
    editable = config_to_editable_dict(config)

    with st.form("settings_form"):
        setting_col1, setting_col2 = st.columns(2)
        with setting_col1:
            st.markdown("**路徑與估算參數**")
            route_mode = st.selectbox(
                "Route mode",
                options=["hybrid_rule_based", "home_based", "gps_only"],
                index=["hybrid_rule_based", "home_based", "gps_only"].index(editable["route_mode"]) if editable["route_mode"] in ["hybrid_rule_based", "home_based", "gps_only"] else 0,
            )
            detour_index = st.number_input("Detour index", min_value=1.0, max_value=3.0, value=float(editable["detour_index"]), step=0.05)
            average_speed_kmph = st.number_input("Average speed (km/h)", min_value=1.0, max_value=120.0, value=float(editable["average_speed_kmph"]), step=1.0)
            candidate_top_n = st.number_input("Candidate top N", min_value=1, max_value=20, value=int(editable["candidate_top_n"]), step=1)
            confidence_distance_m = st.number_input("Confidence distance (m)", min_value=0.0, max_value=5000.0, value=float(editable["confidence_distance_m"]), step=10.0)
            ambiguous_distance_m = st.number_input("Ambiguous distance (m)", min_value=0.0, max_value=5000.0, value=float(editable["ambiguous_distance_m"]), step=10.0)

        with setting_col2:
            st.markdown("**財務與制度參數**")
            fuel_rate = st.number_input("Fuel rate", min_value=0.0, max_value=100.0, value=float(editable["fuel_rate"]), step=0.1)
            maintenance_rate = st.number_input("Maintenance rate", min_value=0.0, max_value=100.0, value=float(editable["maintenance_rate"]), step=0.1)
            break_minutes = st.number_input("Break minutes", min_value=0, max_value=240, value=int(editable["break_minutes"]), step=5)
            light_green_pct = st.number_input("Green threshold", min_value=0.0, max_value=1.0, value=float(editable["light_green_pct"]), step=0.01, format="%.2f")
            light_yellow_pct = st.number_input("Yellow threshold", min_value=0.0, max_value=1.0, value=float(editable["light_yellow_pct"]), step=0.01, format="%.2f")
            google_maps_enabled = st.checkbox("Google Maps enabled", value=bool(editable["google_maps_enabled"]))
            st.caption("若 `employees.csv` 提供 `fuel_rate_override` 或 `maintenance_rate_override`，系統會優先使用員工個別費率，否則才使用這裡的全域預設。")

        st.markdown("**最近醫院判定規則**")
        st.caption("資料來源為候選匹配結果 `route_stop_match`，用於單日頁面顯示「最近醫院」。最近醫院會從全部醫院主檔中尋找，不受前五候選限制。")
        hospital_rule_col1, hospital_rule_col2 = st.columns(2)
        with hospital_rule_col1:
            hospital_keywords = st.text_input("包含關鍵字", value=", ".join(editable["hospital_keywords"]))
        with hospital_rule_col2:
            hospital_exclude_keywords = st.text_input("排除關鍵字", value=", ".join(editable["hospital_exclude_keywords"]))

        submitted = st.form_submit_button("儲存設定", width="stretch")

    st.markdown("**資料位置**")
    st.write(f"資料來源: `{config.data_dir}`")
    st.write(f"輸出路徑: `{config.output_dir}`")
    st.write(f"SQLite: `{config.sqlite_path}`")
    st.write(f"設定檔: `{config.settings_path}`")

    if submitted:
        save_user_settings(
            config.settings_path,
            {
                "route_mode": route_mode,
                "detour_index": detour_index,
                "average_speed_kmph": average_speed_kmph,
                "candidate_top_n": candidate_top_n,
                "confidence_distance_m": confidence_distance_m,
                "ambiguous_distance_m": ambiguous_distance_m,
                "fuel_rate": fuel_rate,
                "maintenance_rate": maintenance_rate,
                "break_minutes": break_minutes,
                "light_green_pct": light_green_pct,
                "light_yellow_pct": light_yellow_pct,
                "google_maps_enabled": google_maps_enabled,
                "hospital_keywords": [item.strip() for item in hospital_keywords.split(",") if item.strip()],
                "hospital_exclude_keywords": [item.strip() for item in hospital_exclude_keywords.split(",") if item.strip()],
            },
        )
        st.success(f"設定已儲存到 {config.settings_path}")
        st.cache_data.clear()
        st.rerun()

with tab_guide:
    st.subheader("指標說明")
    guide_path = Path(__file__).resolve().parent / "METRICS_GUIDE.md"
    st.caption(f"說明檔位置：`{guide_path}`")
    st.markdown(guide_path.read_text(encoding="utf-8"))

with tab_quality:
    st.subheader("資料品質與匯出週期適用性")
    quality_df = attendance["source_quality_status"].value_counts().rename_axis("status").reset_index(name="count")
    st.dataframe(quality_df, width="stretch", hide_index=True)
    st.markdown(
        """
        **適用說明**

        - 月報模式：適合固定每月匯出一次的正式追蹤。
        - 週報模式：適合新到職員工或短期密集監測。
        - 自訂區間：適合特殊專案、試用期或臨時稽核。
        - 所有圖表與匯出都會顯示 `員工編號 + 姓名`，院所顯示為名稱而非只看代碼。
        """
    )
    st.info("HR BI 指標為管理分析用途，不作為單一懲處依據。")
