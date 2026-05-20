from __future__ import annotations

import html as html_lib
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
    load_route_segment_exclusions,
    rebuild_google_route_summary_from_cache,
    upsert_route_segment_exclusions,
)
from risk_service import HIGH_RISK_LABEL, LOW_CONFIDENCE_LABEL, NORMAL_LABEL, REVIEW_LABEL


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
    .weekly-day-card {
        background: rgba(255,255,255,0.98);
        border: 1px solid rgba(15,23,42,0.08);
        border-top: 4px solid #0f766e;
        border-radius: 18px;
        padding: 0.95rem 1rem;
        min-height: 280px;
        box-shadow: 0 10px 24px rgba(15,23,42,0.05);
    }
    .weekly-day-title {
        font-weight: 700;
        font-size: 1rem;
        color: #0f172a;
        margin-bottom: 0.25rem;
    }
    .weekly-day-sub {
        color: #475569;
        font-size: 0.9rem;
        margin-bottom: 0.55rem;
    }
    .weekly-day-list {
        margin: 0.3rem 0 0 0;
        padding-left: 1rem;
        color: #0f172a;
    }
    .weekly-day-list li {
        margin-bottom: 0.35rem;
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
    .tag-risk-normal {
        display: inline-block;
        background: #dcfce7;
        color: #166534;
        border-radius: 999px;
        padding: 0.12rem 0.5rem;
        font-size: 0.82rem;
        font-weight: 700;
        margin-left: 0.35rem;
    }
    .tag-risk-low {
        display: inline-block;
        background: #e0f2fe;
        color: #0369a1;
        border-radius: 999px;
        padding: 0.12rem 0.5rem;
        font-size: 0.82rem;
        font-weight: 700;
        margin-left: 0.35rem;
    }
    .tag-risk-review {
        display: inline-block;
        background: #fef3c7;
        color: #92400e;
        border-radius: 999px;
        padding: 0.12rem 0.5rem;
        font-size: 0.82rem;
        font-weight: 700;
        margin-left: 0.35rem;
    }
    .tag-risk-high {
        display: inline-block;
        background: #fee2e2;
        color: #b91c1c;
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
    .print-only {
        display: none;
    }
    @media print {
        @page {
            size: A4 landscape;
            margin: 15mm;
        }

        html,
        body,
        .stApp,
        .main,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            background: #ffffff !important;
            background-image: none !important;
            color: #000000 !important;
            font-size: 9.5pt !important;
            line-height: 1.35 !important;
            box-shadow: none !important;
            overflow: visible !important;
        }

        * {
            color: #000000 !important;
            text-shadow: none !important;
            box-shadow: none !important;
            box-sizing: border-box !important;
        }

        [data-testid="stSidebar"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        [data-testid="stToastContainer"],
        [data-testid="stModal"],
        [data-testid="stPopover"],
        [data-testid="stFileUploader"],
        [data-testid="stDownloadButton"],
        .app-title-block,
        .hero-card,
        .candidate-panel-header,
        .candidate-card,
        div[data-testid="stHorizontalBlock"]:has(.candidate-card),
        .stButton,
        button,
        footer,
        nav,
        iframe[title="streamlit_navigation"],
        .stTabs [data-baseweb="tab-list"],
        div[data-testid="stMarkdown"]:has(h1),
        div[data-testid="stMarkdown"]:has(h1) + div[data-testid="stMarkdown"],
        div[data-testid="stSelectbox"],
        div[data-baseweb="select"],
        div[data-baseweb="input"],
        div[data-testid="stDateInput"],
        div[data-testid="stNumberInput"],
        div[data-testid="stTextInput"],
        div[data-testid="stCheckbox"] {
            display: none !important;
        }

        .block-container {
            width: 100% !important;
            max-width: 100% !important;
            padding: 0 !important;
        }

        h1,
        h2,
        h3,
        .stMarkdown h1,
        .stMarkdown h2,
        .stMarkdown h3 {
            page-break-after: avoid !important;
            break-after: avoid !important;
            color: #000000 !important;
            line-height: 1.25 !important;
            margin: 0 0 5pt 0 !important;
        }

        h1,
        .stMarkdown h1 {
            font-size: 15pt !important;
        }

        h2,
        .stMarkdown h2 {
            font-size: 12.5pt !important;
        }

        h3,
        .stMarkdown h3 {
            font-size: 11pt !important;
        }

        p,
        li,
        label,
        .stMarkdown,
        .stCaption,
        .stText,
        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"] {
            font-size: 9.5pt !important;
            line-height: 1.35 !important;
            color: #000000 !important;
            word-break: keep-all !important;
            overflow-wrap: break-word !important;
        }

        a[href]::after {
            content: " (" attr(href) ")";
            font-size: 9pt;
            word-break: break-all;
        }

        .block-container,
        div[data-testid="stColumn"],
        div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"] {
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
            overflow: visible !important;
        }

        div[data-testid="stHorizontalBlock"] {
            display: block !important;
            width: 100% !important;
            clear: both !important;
            margin: 0 0 4pt 0 !important;
        }

        div[data-testid="stHorizontalBlock"]::after {
            content: "";
            display: table;
            clear: both;
        }

        div[data-testid="stColumn"] {
            display: block !important;
            float: left !important;
            flex: none !important;
            width: 100% !important;
            min-width: 0 !important;
            max-width: 100% !important;
            margin: 0 0 6pt 0 !important;
            padding: 0 !important;
        }

        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(2):last-child) > div[data-testid="stColumn"] {
            width: 48.5% !important;
            max-width: 48.5% !important;
            margin-right: 1% !important;
        }

        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(3):last-child) > div[data-testid="stColumn"] {
            width: 31.5% !important;
            max-width: 31.5% !important;
            margin-right: 1% !important;
        }

        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(4):last-child) > div[data-testid="stColumn"] {
            width: 23.75% !important;
            max-width: 23.75% !important;
            margin-right: 1% !important;
        }

        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(5):last-child) > div[data-testid="stColumn"] {
            width: 18.75% !important;
            max-width: 18.75% !important;
            margin-right: 1% !important;
        }

        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(6):last-child) > div[data-testid="stColumn"] {
            width: 15.75% !important;
            max-width: 15.75% !important;
            margin-right: 1% !important;
        }

        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child {
            margin-right: 0 !important;
        }

        div[data-testid="stHorizontalBlock"]:has([data-testid="stPlotlyChart"]),
        div[data-testid="stHorizontalBlock"]:has(.weekly-day-card),
        div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
            break-inside: avoid !important;
            page-break-inside: avoid !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.candidate-card),
        .candidate-card {
            break-inside: auto !important;
            page-break-inside: auto !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.candidate-card) ~ .print-only {
            break-before: page !important;
            page-break-before: always !important;
        }

        .hero-card,
        .candidate-card,
        .candidate-panel-header,
        .section-card,
        .daily-map-card,
        .weekly-day-card,
        div[data-testid="stMetric"],
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            width: 100% !important;
            max-width: 100% !important;
            background: #ffffff !important;
            border: 1pt solid #000000 !important;
            border-radius: 0 !important;
            padding: 4pt !important;
            margin: 0 0 5pt 0 !important;
            break-inside: avoid !important;
            page-break-inside: avoid !important;
            overflow: visible !important;
            word-break: keep-all !important;
            overflow-wrap: break-word !important;
        }

        [data-testid="stPlotlyChart"],
        .js-plotly-plot {
            width: 100% !important;
            max-width: 100% !important;
            height: 100mm !important;
            max-height: none !important;
            background: inherit !important;
            border: 0 !important;
            border-radius: 0 !important;
            padding: 0 !important;
            margin: 0 0 6pt 0 !important;
            break-inside: avoid !important;
            page-break-inside: avoid !important;
            overflow: visible !important;
            print-color-adjust: exact !important;
            -webkit-print-color-adjust: exact !important;
        }

        .daily-map-card {
            width: 100% !important;
            height: auto !important;
            max-height: none !important;
            border: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
            break-inside: avoid !important;
            page-break-inside: avoid !important;
        }

        .daily-map-card:empty {
            display: none !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        h3 + div[data-testid="stElementContainer"] + div[data-testid="stElementContainer"] [data-testid="stPlotlyChart"],
        h3 + div[data-testid="stElementContainer"] + div[data-testid="stElementContainer"] .js-plotly-plot {
            height: 100mm !important;
            max-height: none !important;
        }

        [data-testid="stPlotlyChart"]:has(.maplibregl-map),
        [data-testid="stPlotlyChart"]:has(.maplibregl-map) .js-plotly-plot,
        [data-testid="stPlotlyChart"]:has(.maplibregl-map) .plot-container,
        [data-testid="stPlotlyChart"]:has(.maplibregl-map) .svg-container,
        [data-testid="stPlotlyChart"]:has(.maplibregl-map) .main-svg {
            height: 115mm !important;
            max-height: none !important;
        }

        [data-testid="stPlotlyChart"]:has(.maplibregl-map) .maplibregl-map,
        [data-testid="stPlotlyChart"]:has(.maplibregl-map) .maplibregl-canvas {
            height: calc(115mm - 10px) !important;
        }

        div[data-testid="stMetric"] {
            min-height: 0 !important;
            padding: 3pt 4pt !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 10.5pt !important;
            line-height: 1.2 !important;
            word-break: keep-all !important;
            overflow-wrap: break-word !important;
        }

        .tag-client,
        .tag-potential,
        .tag-hospital {
            background: #ffffff !important;
            border: 0.5pt solid #000000 !important;
            color: #000000 !important;
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stDataFrame"] *,
        div[data-testid="stTable"],
        div[data-testid="stTable"] * {
            display: none !important;
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
        }

        .print-only {
            display: block !important;
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 0 12pt 0 !important;
            overflow: visible !important;
            clear: both !important;
        }

        table {
            width: 100% !important;
            border-collapse: collapse !important;
            table-layout: fixed !important;
            font-size: 8pt !important;
            line-height: 1.25 !important;
            page-break-inside: auto !important;
            clear: both !important;
        }

        thead {
            display: table-header-group !important;
        }

        tfoot {
            display: table-footer-group !important;
        }

        tr,
        th,
        td,
        .weekly-day-card,
        .section-card,
        div[data-testid="stMetric"] {
            break-inside: avoid !important;
            page-break-inside: avoid !important;
        }

        th,
        td {
            border: 0.5pt solid #000000 !important;
            padding: 2px 4px !important;
            vertical-align: top !important;
            white-space: nowrap !important;
            word-break: keep-all !important;
            overflow-wrap: normal !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }

        .plot-container,
        .svg-container,
        .main-svg {
            width: 100% !important;
            max-width: 100% !important;
            print-color-adjust: exact !important;
            -webkit-print-color-adjust: exact !important;
        }

        .modebar,
        .plotly-notifier {
            display: none !important;
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


def render_print_table(dataframe: pd.DataFrame, columns: list[str] | None = None) -> None:
    if dataframe.empty:
        return
    print_view = dataframe.copy()
    if columns is not None:
        print_view = print_view[[column for column in columns if column in print_view.columns]].copy()
    html = print_view.to_html(index=False, escape=True, border=0)
    st.markdown(f'<div class="print-only">{html}</div>', unsafe_allow_html=True)


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


def risk_tag_class(risk_level: object) -> str:
    level = str(risk_level or "").strip()
    if level == HIGH_RISK_LABEL:
        return "tag-risk-high"
    if level == REVIEW_LABEL:
        return "tag-risk-review"
    if level == LOW_CONFIDENCE_LABEL:
        return "tag-risk-low"
    return "tag-risk-normal"


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
    config = build_config()
    run_pipeline(config)
    base = config.cleaned_dir
    event_risk_columns = [
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
    ]
    daily_risk_columns = [
        "attendance_uid",
        "employee_id",
        "employee_name",
        "department",
        "work_date",
        "gps_event_count",
        "risk_score",
        "risk_rate",
        "review_event_count",
        "high_risk_event_count",
        "home_area_only_trace",
        "home_start_end_without_field_trace",
        "insufficient_route_evidence",
        "home_near_event_count",
        "max_distance_from_home_m",
        "field_visit_count",
        "risk_level",
        "risk_reason_summary",
    ]
    employee_risk_columns = [
        "employee_id",
        "employee_name",
        "department",
        "attendance_days",
        "gps_event_count",
        "risk_score",
        "risk_rate",
        "review_rate",
        "review_event_count",
        "high_risk_event_count",
        "home_area_only_days",
        "home_start_end_without_field_days",
        "insufficient_route_evidence_days",
        "risk_level",
    ]
    event_risk_numeric_columns = [
        "risk_score",
        "selected_distance_m",
        "nearest_distance_m",
        "distance_gap_m",
        "selected_rank",
    ]
    daily_risk_numeric_columns = [
        "gps_event_count",
        "risk_score",
        "risk_rate",
        "review_event_count",
        "high_risk_event_count",
        "home_area_only_trace",
        "home_start_end_without_field_trace",
        "insufficient_route_evidence",
        "home_near_event_count",
        "max_distance_from_home_m",
        "field_visit_count",
    ]
    employee_risk_numeric_columns = [
        "attendance_days",
        "gps_event_count",
        "risk_score",
        "risk_rate",
        "review_rate",
        "review_event_count",
        "high_risk_event_count",
        "home_area_only_days",
        "home_start_end_without_field_days",
        "insufficient_route_evidence_days",
    ]

    def read_cleaned_csv(
        file_name: str,
        expected_columns: list[str],
        *,
        numeric_columns: list[str] | None = None,
        date_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        path = base / file_name
        if not path.exists():
            return pd.DataFrame(columns=expected_columns)
        dataframe = pd.read_csv(path, encoding="utf-8-sig")
        for column in expected_columns:
            if column not in dataframe.columns:
                dataframe[column] = pd.NA
        for column in numeric_columns or []:
            if column in dataframe.columns:
                dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")
        for column in date_columns or []:
            if column in dataframe.columns:
                dataframe[column] = pd.to_datetime(dataframe[column], errors="coerce")
        return dataframe

    attendance = pd.read_csv(base / "attendance_day_group.csv", encoding="utf-8-sig")
    routes = pd.read_csv(base / "daily_route_summary.csv", encoding="utf-8-sig")
    finance = pd.read_csv(base / "finance_audit_result.csv", encoding="utf-8-sig")
    daily_metrics = pd.read_csv(base / "bi_daily_metrics.csv", encoding="utf-8-sig")
    raw_events = pd.read_csv(base / "raw_check_events.csv", encoding="utf-8-sig")
    matches = pd.read_csv(base / "route_stop_match.csv", encoding="utf-8-sig", low_memory=False)
    hospitals = pd.read_csv(base / "hospital_master_clean.csv", encoding="utf-8-sig")
    clients = pd.read_csv(base / "client_master.csv", encoding="utf-8-sig")
    employees = pd.read_csv(base / "employee_master.csv", encoding="utf-8-sig")
    event_risk = read_cleaned_csv(
        "event_risk_review.csv",
        event_risk_columns,
        numeric_columns=event_risk_numeric_columns,
    )
    daily_risk = read_cleaned_csv(
        "daily_risk_summary.csv",
        daily_risk_columns,
        numeric_columns=daily_risk_numeric_columns,
        date_columns=["work_date"],
    )
    employee_risk = read_cleaned_csv(
        "employee_risk_summary.csv",
        employee_risk_columns,
        numeric_columns=employee_risk_numeric_columns,
    )

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
    route_segment_exclusions = load_route_segment_exclusions(config.sqlite_path)
    if not google_route_summary.empty:
        if "attendance_key" not in google_route_summary.columns:
            google_route_summary["attendance_key"] = google_route_summary["attendance_uid"].astype("string").str.split("_").str[:3].str.join("_")
        google_columns = [
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
        for optional_column in ["raw_estimated_total_km", "excluded_km"]:
            if optional_column in google_route_summary.columns:
                google_columns.append(optional_column)
        routes = routes.merge(
            google_route_summary[google_columns].rename(
                columns={
                    "route_mode": "google_route_mode",
                    "estimated_total_km": "google_estimated_total_km",
                    "estimated_business_km": "google_estimated_business_km",
                    "estimated_travel_min": "google_estimated_travel_min",
                    "route_start_type": "google_route_start_type",
                    "route_end_type": "google_route_end_type",
                    "route_confidence": "google_route_confidence",
                    "route_notes": "google_route_notes",
                    "raw_estimated_total_km": "google_raw_estimated_total_km",
                    "excluded_km": "google_excluded_km",
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
            ("raw_estimated_total_km", "google_raw_estimated_total_km"),
            ("excluded_km", "google_excluded_km"),
        ]:
            if google_col in routes.columns:
                if base_col in routes.columns:
                    routes[base_col] = routes[google_col].combine_first(routes[base_col])
                else:
                    routes[base_col] = routes[google_col]

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
    event_risk_merge_columns = [
        "event_uid",
        "risk_level",
        "risk_score",
        "risk_reason_codes",
        "risk_reason_text",
        "selected_distance_m",
        "nearest_distance_m",
        "distance_gap_m",
        "selected_rank",
    ]
    if "event_uid" in raw_events.columns and "event_uid" in event_risk.columns:
        risk_value_columns = [column for column in event_risk_merge_columns if column != "event_uid"]
        raw_events = raw_events.drop(columns=risk_value_columns, errors="ignore")
        raw_events["event_uid"] = raw_events["event_uid"].astype("string")
        event_risk_for_merge = event_risk[event_risk_merge_columns].copy()
        event_risk_for_merge["event_uid"] = event_risk_for_merge["event_uid"].astype("string")
        event_risk_for_merge = event_risk_for_merge.dropna(subset=["event_uid"])
        if not event_risk_for_merge.empty:
            raw_events = raw_events.merge(event_risk_for_merge, on="event_uid", how="left")

    return {
        "config": config,
        "attendance": attendance,
        "routes": routes,
        "finance": finance,
        "daily_metrics": daily_metrics,
        "raw_events": raw_events,
        "matches": match_enriched,
        "employees": employees,
        "event_risk": event_risk,
        "daily_risk": daily_risk,
        "employee_risk": employee_risk,
        "google_route_summary": google_route_summary,
        "google_route_cache": google_route_cache,
        "google_route_cache_detail": google_route_cache_detail,
        "route_segment_exclusions": route_segment_exclusions,
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


WEEKDAY_LABELS = {
    0: "週一",
    1: "週二",
    2: "週三",
    3: "週四",
    4: "週五",
    5: "週六",
    6: "週日",
}


def get_weekday_label(value) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return "未指定"
    return WEEKDAY_LABELS.get(int(timestamp.weekday()), timestamp.strftime("%Y-%m-%d"))


def build_weekly_point_label(work_date, seq_no: int) -> str:
    timestamp = pd.to_datetime(work_date, errors="coerce")
    weekday_no = int(timestamp.weekday()) + 1 if pd.notna(timestamp) else 0
    return f"{weekday_no}.{seq_no}"


def pick_nearest_place(day_events: pd.DataFrame, name_col: str, meter_col: str) -> dict[str, object] | None:
    if day_events.empty or name_col not in day_events.columns or meter_col not in day_events.columns:
        return None
    subset = day_events[[name_col, meter_col, "actual_time", "source_row_no"]].copy()
    subset[meter_col] = pd.to_numeric(subset[meter_col], errors="coerce")
    subset = subset.loc[subset[name_col].notna() & subset[meter_col].notna()].sort_values(
        [meter_col, "actual_time", "source_row_no"]
    )
    if subset.empty:
        return None
    row = subset.iloc[0]
    return {"name": str(row[name_col]), "meter": float(row[meter_col])}


def summarize_selected_stops(day_events: pd.DataFrame) -> list[dict[str, object]]:
    if day_events.empty or "selected_hospital_name" not in day_events.columns:
        return []
    selected = day_events.loc[day_events["selected_hospital_name"].notna()].copy()
    if selected.empty:
        return []
    selected["selected_client_tag"] = selected["selected_client_tag"].fillna("未標示")
    summary = (
        selected.groupby(["selected_hospital_name", "selected_client_tag"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["count", "selected_hospital_name"], ascending=[False, True])
    )
    return summary.rename(
        columns={
            "selected_hospital_name": "name",
            "selected_client_tag": "tag",
        }
    ).to_dict("records")


def build_weekly_summary_cards(week_events: pd.DataFrame, week_start) -> list[dict[str, object]]:
    week_start_ts = pd.to_datetime(week_start, errors="coerce")
    if pd.isna(week_start_ts):
        return []

    cards: list[dict[str, object]] = []
    for day_offset in range(5):
        current_date = (week_start_ts + pd.Timedelta(days=day_offset)).date()
        day_events = week_events.loc[week_events["work_date"].dt.date == current_date].copy()
        nearest_client = pick_nearest_place(day_events, "nearest_client_name", "nearest_client_meter")
        nearest_hospital = pick_nearest_place(day_events, "nearest_hospital_only_name", "nearest_hospital_only_meter")
        risk_counts = (
            day_events["risk_level"].fillna(NORMAL_LABEL).value_counts().to_dict()
            if "risk_level" in day_events.columns
            else {}
        )
        review_count = int(sum(risk_counts.get(level, 0) for level in [REVIEW_LABEL, HIGH_RISK_LABEL]))
        cards.append(
            {
                "date": current_date,
                "label": get_weekday_label(current_date),
                "event_count": int(len(day_events)),
                "gps_event_count": int(day_events["gps_lat"].notna().sum()) if "gps_lat" in day_events.columns else 0,
                "review_count": review_count,
                "risk_counts": risk_counts,
                "nearest_client": nearest_client,
                "nearest_hospital": nearest_hospital,
                "selected_stops": summarize_selected_stops(day_events),
            }
        )
    return cards


def render_weekly_summary_cards(cards: list[dict[str, object]]) -> None:
    if not cards:
        st.info("本週沒有可呈現的每日摘要。")
        return

    columns = st.columns(5)
    for column, card in zip(columns, cards):
        selected_items = card["selected_stops"]
        if selected_items:
            selected_html = "".join(
                [
                    (
                        f"<li>{item['name']} x {int(item['count'])} "
                        f"<span class=\"{'tag-client' if item['tag'] == '既有客戶' else 'tag-hospital' if item['tag'] == '醫院' else 'tag-potential'}\">"
                        f"{item['tag']}</span></li>"
                    )
                    for item in selected_items
                ]
            )
        else:
            selected_html = "<li>本日無系統選定院所</li>"

        nearest_client = card["nearest_client"]
        nearest_client_text = (
            f"{nearest_client['name']} 距 {nearest_client['meter']:.0f} m"
            if nearest_client
            else "本日無最近既有客戶"
        )
        nearest_hospital = card["nearest_hospital"]
        nearest_hospital_text = (
            f"{nearest_hospital['name']} 距 {nearest_hospital['meter']:.0f} m"
            if nearest_hospital
            else "本日無最近醫院"
        )
        risk_counts = card.get("risk_counts", {}) or {}
        risk_summary_parts = [
            f"{label} {int(risk_counts.get(label, 0))}"
            for label in [HIGH_RISK_LABEL, REVIEW_LABEL, LOW_CONFIDENCE_LABEL]
            if int(risk_counts.get(label, 0)) > 0
        ]
        risk_summary_text = " / ".join(risk_summary_parts) if risk_summary_parts else "無需覆核"
        html = f"""
        <div class="weekly-day-card">
            <div class="weekly-day-title">{card['label']}</div>
            <div class="weekly-day-sub">{card['date']} | 打卡 {card['event_count']} 點 / GPS {card['gps_event_count']} 點</div>
            <div class="candidate-sub">需覆核點數：{card.get('review_count', 0)}</div>
            <div class="candidate-sub">風險摘要：{risk_summary_text}</div>
            <div class="candidate-sub">最近既有客戶：{nearest_client_text}</div>
            <div class="candidate-sub">最近醫院：{nearest_hospital_text}</div>
            <div class="candidate-sub">系統選定院所</div>
            <ul class="weekly-day-list">{selected_html}</ul>
        </div>
        """
        column.markdown(html, unsafe_allow_html=True)


def build_weekly_map(
    week_events: pd.DataFrame,
    employee_row: pd.Series | None = None,
    google_segments: pd.DataFrame | None = None,
) -> go.Figure:
    gps_events = week_events.dropna(subset=["gps_lat", "gps_lon"]).copy()
    gps_events = gps_events.sort_values(["work_date", "actual_time", "source_row_no"])
    fig = go.Figure()
    if gps_events.empty:
        fig.update_layout(height=780, margin=dict(l=0, r=0, t=30, b=0))
        return fig

    has_home = (
        employee_row is not None
        and pd.notna(employee_row.get("home_lat"))
        and pd.notna(employee_row.get("home_lon"))
    )
    fit_latitudes = gps_events["gps_lat"].astype(float).tolist()
    fit_longitudes = gps_events["gps_lon"].astype(float).tolist()
    day_palette = {
        0: "#0f766e",
        1: "#2563eb",
        2: "#dc2626",
        3: "#f59e0b",
        4: "#7c3aed",
        5: "#0891b2",
        6: "#be123c",
    }

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
                text=["家"],
                textposition="top center",
                textfont=dict(size=14, color="#1e3a8a"),
                marker=dict(size=20, color="#1d4ed8"),
                hovertemplate="<b>員工住家</b><br>%{lat:.6f}, %{lon:.6f}<extra></extra>",
                name="住家",
            )
        )

    for work_date, day_group in gps_events.groupby(gps_events["work_date"].dt.date, sort=True):
        day_group = day_group.sort_values(["actual_time", "source_row_no"]).copy()
        day_ts = pd.to_datetime(work_date)
        day_color = day_palette.get(int(day_ts.weekday()), "#0f766e")
        day_label = get_weekday_label(work_date)

        attendance_key_groups: list[tuple[object, pd.DataFrame]] = []
        if "attendance_key" in day_group.columns and day_group["attendance_key"].notna().any():
            attendance_key_groups = list(day_group.groupby("attendance_key", dropna=False, sort=False))
        else:
            attendance_key_groups = [(None, day_group)]

        first_segment_for_day = True
        for attendance_key, route_group in attendance_key_groups:
            route_group = route_group.sort_values(["actual_time", "source_row_no"]).copy()
            if route_group.empty:
                continue

            first_point = route_group.iloc[0]
            last_point = route_group.iloc[-1]
            fallback_segments: list[dict[str, object]] = []
            segment_no = 1

            if has_home:
                fallback_segments.append(
                    {
                        "segment_no": segment_no,
                        "segment_type": "home_to_first",
                        "lat": [home_lat, float(first_point["gps_lat"])],
                        "lon": [home_lon, float(first_point["gps_lon"])],
                    }
                )
                segment_no += 1

            gps_points = route_group[["gps_lat", "gps_lon"]].astype(float).to_dict("records")
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
            segment_slice = google_segments.copy() if isinstance(google_segments, pd.DataFrame) else pd.DataFrame()
            if attendance_key is not None and not segment_slice.empty:
                if "attendance_key" not in segment_slice.columns:
                    segment_slice["attendance_key"] = (
                        segment_slice["attendance_uid"].astype("string").str.split("_").str[:3].str.join("_")
                    )
                segment_slice = segment_slice.loc[segment_slice["attendance_key"] == attendance_key].copy()
                for _, segment in segment_slice.sort_values("segment_no").iterrows():
                    points = decode_polyline(segment.get("polyline"))
                    if len(points) >= 2:
                        google_polyline_lookup[(int(segment["segment_no"]), str(segment["segment_type"]))] = points

            for segment in fallback_segments:
                key = (int(segment["segment_no"]), str(segment["segment_type"]))
                google_points = google_polyline_lookup.get(key)
                trace_name = f"{day_label} 路徑"
                if google_points:
                    fit_latitudes.extend([point[0] for point in google_points])
                    fit_longitudes.extend([point[1] for point in google_points])
                    fig.add_trace(
                        go.Scattermap(
                            lat=[point[0] for point in google_points],
                            lon=[point[1] for point in google_points],
                            mode="lines",
                            line=dict(width=4, color=day_color),
                            opacity=0.88,
                            hoverinfo="skip",
                            name=trace_name,
                            showlegend=first_segment_for_day,
                        )
                    )
                else:
                    fig.add_trace(
                        go.Scattermap(
                            lat=segment["lat"],
                            lon=segment["lon"],
                            mode="lines",
                            line=dict(width=3, color=day_color),
                            opacity=0.52,
                            hoverinfo="skip",
                            name=trace_name,
                            showlegend=first_segment_for_day,
                        )
                    )
                first_segment_for_day = False

    marker_labels: list[str] = []
    marker_colors: list[str] = []
    marker_sizes: list[int] = []
    customdata: list[list[object]] = []
    for work_date, day_group in gps_events.groupby(gps_events["work_date"].dt.date, sort=True):
        day_group = day_group.sort_values(["actual_time", "source_row_no"]).reset_index(drop=True)
        day_color = day_palette.get(pd.to_datetime(work_date).weekday(), "#0f766e")
        day_label = get_weekday_label(work_date)
        for index, row in day_group.iterrows():
            marker_labels.append(build_weekly_point_label(work_date, index + 1))
            marker_colors.append(day_color)
            marker_sizes.append(28 if index in (0, len(day_group) - 1) else 24)
            customdata.append(
                [
                    day_label,
                    row.actual_time_display if pd.notna(row.actual_time_display) else "未判定",
                    row.selected_hospital_name if pd.notna(row.selected_hospital_name) else "未判定",
                    row.selected_client_tag if pd.notna(row.selected_client_tag) else "未判定",
                    build_weekly_point_label(work_date, index + 1),
                ]
            )

    fig.add_trace(
        go.Scattermap(
            lat=gps_events["gps_lat"],
            lon=gps_events["gps_lon"],
            mode="markers+text",
            text=marker_labels,
            textposition="middle center",
            textfont=dict(size=11, color="white"),
            marker=dict(size=marker_sizes, color=marker_colors, opacity=0.96),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "編號：%{customdata[4]}<br>"
                "時間：%{customdata[1]}<br>"
                "座標：%{lat:.6f}, %{lon:.6f}<br>"
                "系統選定：%{customdata[2]}<br>"
                "類型：%{customdata[3]}<extra></extra>"
            ),
            customdata=customdata,
            name="週打卡點",
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
            zoom=max(compute_zoom(padded_lats, padded_lons) - 1.15, 2.2),
            bounds=dict(
                west=min(padded_lons),
                east=max(padded_lons),
                south=min(padded_lats),
                north=max(padded_lats),
            ),
        ),
        height=820,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.01),
    )
    return fig

def build_candidate_panel(day_events: pd.DataFrame, matches: pd.DataFrame) -> list[dict]:
    gps_events = day_events.dropna(subset=["gps_lat", "gps_lon"]).copy()
    if gps_events.empty:
        return []
    risk_columns = ["risk_level", "risk_score", "risk_reason_text"]
    for column in risk_columns:
        if column not in gps_events.columns:
            gps_events[column] = pd.NA

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
                "risk_level",
                "risk_score",
                "risk_reason_text",
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
                "risk_level": first_row["risk_level"] if pd.notna(first_row["risk_level"]) else NORMAL_LABEL,
                "risk_score": float(first_row["risk_score"]) if pd.notna(first_row["risk_score"]) else 0.0,
                "risk_reason_text": first_row["risk_reason_text"] if pd.notna(first_row["risk_reason_text"]) else "",
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
            risk_level = panel.get("risk_level") or NORMAL_LABEL
            risk_score = float(panel.get("risk_score") or 0)
            risk_reason = str(panel.get("risk_reason_text") or "").strip()
            risk_html = (
                f'<div class="candidate-sub">覆核狀態：'
                f'<span class="{risk_tag_class(risk_level)}">{html_lib.escape(str(risk_level))}</span>'
                f"（{risk_score:.0f} 分）</div>"
            )
            if risk_reason:
                risk_html += f'<div class="candidate-sub">覆核原因：{html_lib.escape(risk_reason)}</div>'
            html = f"""
            <div class="candidate-card">
                <div class="candidate-title">#{panel['seq_no']} {panel['time']}</div>
                <div class="candidate-sub">座標：{panel['lat']:.6f}, {panel['lon']:.6f}</div>
                <div class="candidate-sub">最近既有客戶：{nearest_client_text}</div>
                <div class="candidate-sub">最近醫院：{nearest_text}</div>
                <div class="candidate-sub">系統選定：{selected_name}<span class="{selected_tag_class}">{selected_tag}</span></div>
                {risk_html}
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
    daily_risk: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    attendance_mask = attendance["work_date"].dt.date.between(start_date, end_date)
    metrics_mask = daily_metrics["work_date"].dt.date.between(start_date, end_date)
    routes_mask = routes["work_date"].dt.date.between(start_date, end_date)
    period_attendance = attendance.loc[(attendance["employee_id"] == employee_id) & attendance_mask].copy()
    period_metrics = daily_metrics.loc[(daily_metrics["employee_id"] == employee_id) & metrics_mask].copy()
    period_routes = routes.loc[(routes["employee_id"] == employee_id) & routes_mask].copy()
    risk_columns = [
        "attendance_uid",
        "risk_score",
        "risk_rate",
        "review_event_count",
        "high_risk_event_count",
        "home_area_only_trace",
        "home_start_end_without_field_trace",
        "insufficient_route_evidence",
        "home_near_event_count",
        "max_distance_from_home_m",
        "field_visit_count",
        "risk_level",
        "risk_reason_summary",
    ]
    if daily_risk.empty:
        period_risk = pd.DataFrame(columns=risk_columns)
    else:
        risk_mask = daily_risk["work_date"].dt.date.between(start_date, end_date)
        period_risk = daily_risk.loc[(daily_risk["employee_id"] == employee_id) & risk_mask].copy()
        for column in risk_columns:
            if column not in period_risk.columns:
                period_risk[column] = pd.NA
        period_risk = period_risk[risk_columns]

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
        .merge(period_risk, on="attendance_uid", how="left")
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
    for column in [
        "risk_score",
        "risk_rate",
        "review_event_count",
        "high_risk_event_count",
        "home_area_only_trace",
        "home_start_end_without_field_trace",
        "insufficient_route_evidence",
        "home_near_event_count",
        "max_distance_from_home_m",
        "field_visit_count",
    ]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0)
    merged["risk_level"] = merged["risk_level"].fillna(NORMAL_LABEL)
    merged["risk_reason_summary"] = merged["risk_reason_summary"].fillna("")

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
                "需覆核點數": int(merged["review_event_count"].sum()),
                "高風險點數": int(merged["high_risk_event_count"].sum()),
                "風險分數": round(float(merged["risk_score"].sum()), 2),
                "平均風險率": round(float(merged["risk_rate"].mean()), 4),
                "僅居家附近軌跡天數": int((merged["home_area_only_trace"] > 0).sum()),
                "住家起訖但缺外勤軌跡天數": int((merged["home_start_end_without_field_trace"] > 0).sum()),
                "路線佐證不足天數": int((merged["insufficient_route_evidence"] > 0).sum()),
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
            "risk_level",
            "risk_score",
            "risk_rate",
            "review_event_count",
            "high_risk_event_count",
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
            "home_near_event_count",
            "max_distance_from_home_m",
            "field_visit_count",
            "risk_reason_summary",
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
            "risk_level": "覆核狀態",
            "risk_score": "風險分數",
            "risk_rate": "風險率",
            "review_event_count": "需覆核點數",
            "high_risk_event_count": "高風險點數",
            "home_area_only_trace": "僅居家附近軌跡",
            "home_start_end_without_field_trace": "住家起訖但缺外勤軌跡",
            "insufficient_route_evidence": "路線佐證不足",
            "home_near_event_count": "住家附近打卡點數",
            "max_distance_from_home_m": "離家最遠距離(公尺)",
            "field_visit_count": "外勤拜訪佐證數",
            "risk_reason_summary": "覆核原因摘要",
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
    daily_risk: pd.DataFrame,
    start_date,
    end_date,
) -> pd.DataFrame:
    attendance_mask = attendance["work_date"].dt.date.between(start_date, end_date)
    metrics_mask = daily_metrics["work_date"].dt.date.between(start_date, end_date)
    routes_mask = routes["work_date"].dt.date.between(start_date, end_date)
    finance_mask = finance["work_date"].dt.date.between(start_date, end_date)
    risk_columns = [
        "attendance_uid",
        "risk_score",
        "risk_rate",
        "review_event_count",
        "high_risk_event_count",
        "home_area_only_trace",
        "home_start_end_without_field_trace",
        "insufficient_route_evidence",
    ]

    base = attendance.loc[attendance_mask].copy()
    metrics = daily_metrics.loc[metrics_mask, ["attendance_uid", "raw_span_minutes", "effective_field_minutes", "anomaly_flag", "gps_event_count"]]
    route_slice = routes.loc[routes_mask, ["attendance_uid", "estimated_total_km", "estimated_business_km", "estimated_travel_min", "route_confidence"]]
    finance_slice = finance.loc[finance_mask, ["attendance_uid", "audit_light", "fuel_subsidy", "maintenance_subsidy", "per_diem_amount"]]
    if daily_risk.empty:
        risk_slice = pd.DataFrame(columns=risk_columns)
    else:
        risk_mask = daily_risk["work_date"].dt.date.between(start_date, end_date)
        risk_slice = daily_risk.loc[risk_mask].copy()
        for column in risk_columns:
            if column not in risk_slice.columns:
                risk_slice[column] = pd.NA
        risk_slice = risk_slice[risk_columns]
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
    merged = merged.merge(risk_slice, on="attendance_uid", how="left")
    merged = merged.merge(event_flag_slice, on="attendance_uid", how="left")
    for column in ["overtime_flag_bool", "actual_overtime_flag", "personal_overtime_flag"]:
        merged[column] = merged[column].fillna(False).astype(bool)
    for column in [
        "risk_score",
        "risk_rate",
        "review_event_count",
        "high_risk_event_count",
        "home_area_only_trace",
        "home_start_end_without_field_trace",
        "insufficient_route_evidence",
    ]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0)

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
            需覆核點數=("review_event_count", lambda s: int(s.fillna(0).sum())),
            高風險點數=("high_risk_event_count", lambda s: int(s.fillna(0).sum())),
            風險分數=("risk_score", lambda s: round(s.fillna(0).sum(), 2)),
            僅居家附近軌跡天數=("home_area_only_trace", lambda s: int((s.fillna(0) > 0).sum())),
            住家起訖但缺外勤軌跡天數=("home_start_end_without_field_trace", lambda s: int((s.fillna(0) > 0).sum())),
            路線佐證不足天數=("insufficient_route_evidence", lambda s: int((s.fillna(0) > 0).sum())),
            平均路徑信心=("route_confidence", lambda s: round(s.fillna(0).mean(), 4)),
            異常率=("anomaly_flag", lambda s: round(float(s.fillna(False).mean()), 4)),
            超時出勤率=("overtime_flag_bool", lambda s: round(float(s.fillna(False).mean()), 4)),
            實際加班率=("actual_overtime_flag", lambda s: round(float(s.fillna(False).mean()), 4)),
            油資補貼=("fuel_subsidy", lambda s: round(s.fillna(0).sum(), 2)),
            維修補貼=("maintenance_subsidy", lambda s: round(s.fillna(0).sum(), 2)),
            日當費=("per_diem_amount", lambda s: round(s.fillna(0).sum(), 2)),
        )
        .reset_index()
    )
    summary["平均風險率"] = (summary["風險分數"] / summary["總GPS點數"].clip(lower=1)).round(4)
    summary = summary.sort_values(["平均風險率", "風險分數", "總計預估里程"], ascending=[False, False, False])
    return summary


def normalize_year_month_value(value) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    for fmt in ("%Y-%m", "%Y/%m", "%Y-%m-%d", "%Y/%m/%d", "%b-%y", "%y-%b", "%b-%Y", "%Y%m", "%m/%Y"):
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


def apply_live_monthly_claims_to_finance(
    finance: pd.DataFrame,
    monthly_claims: pd.DataFrame | None,
) -> pd.DataFrame:
    if finance.empty or monthly_claims is None or monthly_claims.empty:
        return finance

    claims = monthly_claims.copy()
    claims["employee_id"] = claims["employee_id"].astype("string").str.strip()
    claims["year_month"] = claims["year_month"].apply(normalize_year_month_value)
    claims["claimed_km"] = pd.to_numeric(claims["claimed_km"], errors="coerce")
    claims = (
        claims.dropna(subset=["employee_id", "year_month", "claimed_km"])
        .groupby(["employee_id", "year_month"], dropna=False, as_index=False)["claimed_km"]
        .sum()
    )
    if claims.empty:
        return finance

    updated = finance.copy()
    updated["employee_id"] = updated["employee_id"].astype("string").str.strip()
    updated["year_month"] = pd.to_datetime(updated["work_date"], errors="coerce").dt.strftime("%Y-%m")
    updated = updated.merge(claims, on=["employee_id", "year_month"], how="left")
    updated["employee_claim_km"] = updated["claimed_km"].combine_first(updated.get("employee_claim_km"))
    updated = updated.drop(columns=["claimed_km", "year_month"], errors="ignore")
    return updated


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
    daily_risk: pd.DataFrame,
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
    daily_risk_columns = [
        "attendance_uid",
        "risk_level",
        "risk_score",
        "risk_rate",
        "review_event_count",
        "high_risk_event_count",
        "home_area_only_trace",
        "home_start_end_without_field_trace",
        "insufficient_route_evidence",
        "home_near_event_count",
        "max_distance_from_home_m",
        "field_visit_count",
        "risk_reason_summary",
    ]
    if daily_risk.empty:
        risk_slice = pd.DataFrame(columns=daily_risk_columns)
    else:
        risk_slice = daily_risk.loc[
            daily_risk["attendance_uid"].isin(attendance_slice["attendance_uid"])
        ].copy()
        for column in daily_risk_columns:
            if column not in risk_slice.columns:
                risk_slice[column] = pd.NA
        risk_slice = risk_slice[daily_risk_columns]

    daily_export = attendance_slice.merge(metrics_slice, on="attendance_uid", how="left")
    daily_export = daily_export.merge(route_slice, on="attendance_uid", how="left")
    daily_export = daily_export.merge(finance_slice, on="attendance_uid", how="left")
    daily_export = daily_export.merge(flag_slice, on="attendance_uid", how="left")
    daily_export = daily_export.merge(risk_slice, on="attendance_uid", how="left")
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
    for column, default_value in [
        ("risk_level", NORMAL_LABEL),
        ("risk_score", 0),
        ("risk_reason_text", ""),
    ]:
        if column not in detail_events.columns:
            detail_events[column] = default_value
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
            "risk_level",
            "risk_score",
            "risk_rate",
            "review_event_count",
            "high_risk_event_count",
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
            "home_near_event_count",
            "max_distance_from_home_m",
            "field_visit_count",
            "risk_reason_summary",
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
            "risk_level": "覆核狀態",
            "risk_score": "風險分數",
            "risk_rate": "風險率",
            "review_event_count": "需覆核點數",
            "high_risk_event_count": "高風險點數",
            "home_area_only_trace": "僅居家附近軌跡",
            "home_start_end_without_field_trace": "住家起訖但缺外勤軌跡",
            "insufficient_route_evidence": "路線佐證不足",
            "home_near_event_count": "住家附近打卡點數",
            "max_distance_from_home_m": "離家最遠距離(m)",
            "field_visit_count": "外勤拜訪佐證數",
            "risk_reason_summary": "覆核原因代碼",
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
    for bool_col in ["僅居家附近軌跡", "住家起訖但缺外勤軌跡", "路線佐證不足"]:
        daily_sheet[bool_col] = pd.to_numeric(daily_sheet[bool_col], errors="coerce").fillna(0).gt(0).map({True: "是", False: "否"})
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
            需覆核點數=("需覆核點數", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            高風險點數=("高風險點數", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            風險分數=("風險分數", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 2)),
            僅居家附近軌跡天數=("僅居家附近軌跡", lambda s: int((pd.Series(s).astype(str) == "是").sum())),
            住家起訖但缺外勤軌跡天數=("住家起訖但缺外勤軌跡", lambda s: int((pd.Series(s).astype(str) == "是").sum())),
            路線佐證不足天數=("路線佐證不足", lambda s: int((pd.Series(s).astype(str) == "是").sum())),
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
            "risk_level",
            "risk_score",
            "risk_reason_text",
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
            "risk_level": "覆核狀態",
            "risk_score": "風險分數",
            "risk_reason_text": "覆核原因",
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
event_risk = tables["event_risk"]
daily_risk = tables["daily_risk"]
employee_risk = tables["employee_risk"]
google_route_summary = tables["google_route_summary"]
google_route_cache = tables["google_route_cache"]
google_route_cache_detail = tables["google_route_cache_detail"]
route_segment_exclusions = tables["route_segment_exclusions"]
monthly_claims_path = Path(config.data_dir) / "monthly_claims.csv"
monthly_claims = pd.read_csv(monthly_claims_path, encoding="utf-8-sig") if monthly_claims_path.exists() else pd.DataFrame()
monthly_claim_comparison = build_monthly_claim_comparison(
    routes=routes,
    monthly_claims=monthly_claims,
    green_threshold=float(config.light_green_pct),
    yellow_threshold=float(config.light_yellow_pct),
)
finance = apply_live_monthly_claims_to_finance(finance, monthly_claims)

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

st.markdown(
    """
    <div class="app-title-block">
        <h1>Function Route Report</h1>
        <p>以單日路徑檢視、個人期間報表與可匯出結果為核心的業務出勤分析介面</p>
    </div>
    """,
    unsafe_allow_html=True,
)
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

tab_home, tab_daily, tab_weekly, tab_period, tab_overview, tab_route_adjust, tab_routes_api, tab_settings, tab_guide, tab_quality = st.tabs(
    ["首頁流程", "單日路徑檢視", "週路徑檢視", "個人期間報表", "全業務總覽", "路徑核算調整", "Google Routes 執行", "參數設定", "指標說明", "資料品質與說明"]
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

    employee_row = employees.loc[employees["employee_id"] == selected_employee_id].head(1)
    employee_row = employee_row.iloc[0] if not employee_row.empty else None

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

    for risk_column, default_value in [
        ("risk_level", NORMAL_LABEL),
        ("risk_score", 0),
        ("risk_reason_text", ""),
    ]:
        if risk_column not in day_events.columns:
            day_events[risk_column] = default_value

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
            "risk_level",
            "risk_score",
            "risk_reason_text",
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
            "selected_hospital_name": "系統選定院所",
            "selected_client_tag": "客戶類型",
            "risk_level": "覆核狀態",
            "risk_score": "風險分數",
            "risk_reason_text": "覆核原因",
        }
    )
    detail_tab, finance_tab = st.tabs(["當日事件明細", "當日財務摘要"])
    with detail_tab:
        render_print_table(
            event_detail,
            [
                "時間",
                "卡別",
                "比對結果",
                "來源",
                "最近既有客戶",
                "最近既有客戶距離(公尺)",
                "最近醫院",
                "最近醫院距離(公尺)",
                "系統選定院所",
                "客戶類型",
                "覆核狀態",
                "風險分數",
                "覆核原因",
            ],
        )
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
                "風險分數": st.column_config.NumberColumn(format="%.0f"),
            },
        )
    with finance_tab:
        if not day_finance.empty:
            day_finance_view = day_finance[
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
            )
            render_print_table(day_finance_view)
            st.dataframe(
                day_finance_view,
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("這一天目前沒有財務摘要資料。")

with tab_weekly:
    st.subheader("週出勤路徑")
    week_col1, week_col2, week_col3 = st.columns([1.65, 1.0, 1.35])
    weekly_employee_label = week_col1.selectbox(
        "選擇業務員",
        options=employee_options["employee_label"].tolist(),
        index=0,
        key="weekly_employee",
    )
    weekly_employee_id = employee_label_map[weekly_employee_label]
    weekly_employee_dates = (
        attendance.loc[attendance["employee_id"] == weekly_employee_id, "work_date"]
        .dropna()
        .sort_values()
    )
    weekly_options = weekly_employee_dates.dt.strftime("%G-W%V").unique().tolist()
    selected_week = (
        week_col2.selectbox(
            "選擇週次",
            options=weekly_options,
            index=len(weekly_options) - 1,
            key="weekly_period",
        )
        if weekly_options
        else None
    )

    if weekly_employee_dates.empty:
        week_start = pd.Timestamp.today().date()
        week_end = week_start
        week_attendance = attendance.iloc[0:0].copy()
        week_events = raw_events.iloc[0:0].copy()
        week_routes = routes.iloc[0:0].copy()
        week_google_segments = pd.DataFrame()
    else:
        selected_week_dates = weekly_employee_dates.loc[weekly_employee_dates.dt.strftime("%G-W%V") == selected_week]
        week_anchor = selected_week_dates.min() if not selected_week_dates.empty else weekly_employee_dates.max()
        week_start = (week_anchor - pd.Timedelta(days=int(week_anchor.weekday()))).date()
        week_end = (pd.to_datetime(week_start) + pd.Timedelta(days=4)).date()

        week_attendance = attendance.loc[
            (attendance["employee_id"] == weekly_employee_id)
            & attendance["work_date"].dt.date.between(week_start, week_end)
        ].copy()
        week_events = raw_events.loc[
            (raw_events["employee_id"] == weekly_employee_id)
            & raw_events["work_date"].dt.date.between(week_start, week_end)
        ].copy()
        if not week_attendance.empty:
            week_events = week_events.merge(
                week_attendance[["attendance_uid", "attendance_key"]].drop_duplicates(),
                on="attendance_uid",
                how="left",
            )
        week_routes = routes.loc[routes["attendance_uid"].isin(week_attendance["attendance_uid"])].copy()
        if isinstance(google_route_cache, pd.DataFrame) and not google_route_cache.empty and not week_attendance.empty:
            week_google_segments = google_route_cache.copy()
            if "attendance_key" not in week_google_segments.columns:
                week_google_segments["attendance_key"] = (
                    week_google_segments["attendance_uid"].astype("string").str.split("_").str[:3].str.join("_")
                )
            week_google_segments = week_google_segments.loc[
                week_google_segments["attendance_key"].isin(week_attendance["attendance_key"])
            ].copy()
        else:
            week_google_segments = pd.DataFrame()

    week_col3.markdown(
        f"""
        <div class="section-card" style="padding:0.85rem 1rem;">
            <div class="candidate-title">{weekly_employee_label}</div>
            <div class="candidate-sub">{selected_week if weekly_options else '無可用週次'} | {week_start} ~ {week_end}</div>
            <div class="candidate-sub">出勤 {int(week_attendance['attendance_uid'].nunique()) if not week_attendance.empty else 0} 天 / GPS {int(week_events['gps_lat'].notna().sum()) if isinstance(week_events, pd.DataFrame) and 'gps_lat' in week_events.columns else 0} 點</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    weekly_employee_row = employees.loc[employees["employee_id"] == weekly_employee_id].head(1)
    weekly_employee_row = weekly_employee_row.iloc[0] if not weekly_employee_row.empty else None

    week_metric1, week_metric2, week_metric3, week_metric4 = st.columns(4)
    week_metric1.metric("出勤天數", int(week_attendance["attendance_uid"].nunique()) if not week_attendance.empty else 0)
    week_metric2.metric(
        "打卡 / GPS 點數",
        f"{int(len(week_events)) if isinstance(week_events, pd.DataFrame) else 0} / {int(week_events['gps_lat'].notna().sum()) if isinstance(week_events, pd.DataFrame) and 'gps_lat' in week_events.columns else 0}",
    )
    week_metric3.metric(
        "預估總里程",
        f"{week_routes['estimated_total_km'].fillna(0).sum():.2f} km" if not week_routes.empty else "0.00 km",
    )
    week_metric4.metric(
        "公務里程",
        f"{week_routes['estimated_business_km'].fillna(0).sum():.2f} km" if not week_routes.empty else "0.00 km",
    )

    st.markdown("**週地圖路徑**")
    st.markdown('<div class="daily-map-card">', unsafe_allow_html=True)
    st.plotly_chart(build_weekly_map(week_events, weekly_employee_row, week_google_segments), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption("週版地圖以週一到週五整週呈現，打卡點編號採用「週次序號.當日點位序號」格式，例如 1.1 代表週一第一個點。")

    st.markdown("**每日摘要卡**")
    render_weekly_summary_cards(build_weekly_summary_cards(week_events, week_start))

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

    summary_df, detail_df = summarize_period(
        period_employee_id,
        start_date,
        end_date,
        attendance,
        daily_metrics,
        routes,
        attendance_event_flags,
        daily_risk,
    )
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
        metric_row4[1].metric("需覆核點數", int(summary_row["需覆核點數"]))
        metric_row4[2].metric("高風險點數", int(summary_row["高風險點數"]))
        metric_row4[3].metric("僅居家附近軌跡天數", int(summary_row["僅居家附近軌跡天數"]))

        st.markdown("**報表摘要**")
        summary_show = summary_df.rename(columns={"總匹配院所次數": "匹配院所總次數"})
        render_print_table(summary_show)
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
            render_print_table(period_claim_table)
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
            render_print_table(top_hospitals)
            st.dataframe(top_hospitals, width="stretch", hide_index=True)
        with chart_col2:
            st.markdown("**每日明細**")
            render_print_table(
                detail_df,
                [
                    "日期",
                    "打卡次數",
                    "GPS點數",
                    "總出勤分鐘",
                    "有效外勤分鐘",
                    "預估總里程",
                    "預估公務里程",
                    "覆核狀態",
                    "需覆核點數",
                    "高風險點數",
                    "風險分數",
                    "覆核原因摘要",
                    "未打卡未處理次數",
                    "忘刷申請次數",
                    "比對摘要",
                ],
            )
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
                    "風險分數": st.column_config.NumberColumn(format="%.0f"),
                    "風險率": st.column_config.NumberColumn(format="%.2f"),
                    "需覆核點數": st.column_config.NumberColumn(format="%d"),
                    "高風險點數": st.column_config.NumberColumn(format="%d"),
                    "住家附近打卡點數": st.column_config.NumberColumn(format="%d"),
                    "離家最遠距離(公尺)": st.column_config.NumberColumn(format="%.0f m"),
                    "外勤拜訪佐證數": st.column_config.NumberColumn(format="%d"),
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
        render_print_table(
            finance_detail,
            [
                "日期",
                "月申請里程",
                "當日公務里程",
                "燈號",
                "油資補貼",
                "維修補貼",
                "日當費",
                "審核狀態",
            ],
        )
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
        attendance_event_flags,
        daily_risk,
        overview_start_date,
        overview_end_date,
    )
    overview_months = months_in_range(overview_start_date, overview_end_date)
    overview_start_ts = pd.Timestamp(overview_start_date)
    overview_end_ts = pd.Timestamp(overview_end_date)
    overview_period = overview_start_ts.to_period("M")
    overview_month_dates = all_dates.loc[all_dates.dt.to_period("M") == overview_period]
    overview_is_full_single_month = (
        overview_period == overview_end_ts.to_period("M")
        and not overview_month_dates.empty
        and overview_start_date == overview_month_dates.min().date()
        and overview_end_date == overview_month_dates.max().date()
    )
    overview_claims = monthly_claim_comparison.loc[
        monthly_claim_comparison["year_month"].isin(overview_months)
    ].copy()
    if overview_claims.empty:
        overview_claim_employee = pd.DataFrame(
            columns=[
                "employee_id",
                "employee_label",
                "department",
                "實際月申請里程",
                "系統預估月公務里程",
                "差異里程",
                "差異率",
                "差異率絕對值",
                "比較燈號",
            ]
        )
    else:
        overview_claim_employee = (
            overview_claims.groupby(["employee_id", "employee_label", "department"], dropna=False, as_index=False)
            .agg(
                實際月申請里程=("claimed_km", lambda s: round(s.fillna(0).sum(), 2)),
                系統預估月公務里程=("estimated_business_km", lambda s: round(s.fillna(0).sum(), 2)),
                差異里程=("difference_km", lambda s: round(s.fillna(0).sum(), 2)),
                比較燈號=("comparison_light", lambda s: next((value for value in s if pd.notna(value)), "gray")),
            )
        )
        denominator = overview_claim_employee["實際月申請里程"].where(overview_claim_employee["實際月申請里程"] > 0)
        overview_claim_employee["差異率"] = overview_claim_employee["差異里程"] / denominator
        overview_claim_employee["差異率絕對值"] = overview_claim_employee["差異率"].abs()
        if not overview_is_full_single_month:
            overview_claim_employee["比較燈號"] = "區間不判定"
        overview_claim_employee = overview_claim_employee.sort_values("差異率絕對值", ascending=False)

    overview_col2.metric("納入比較員工數", len(overview_summary))
    top_row = st.columns(4)
    top_row[0].metric("全員總計預估里程", f"{overview_summary['總計預估里程'].sum():.2f} km")
    top_row[1].metric("全員總計公務里程", f"{overview_summary['總計預估公務里程'].sum():.2f} km")
    top_row[2].metric("需覆核點數", int(overview_summary["需覆核點數"].fillna(0).sum()) if not overview_summary.empty else 0)
    top_row[3].metric("高風險點數", int(overview_summary["高風險點數"].fillna(0).sum()) if not overview_summary.empty else 0)
    risk_top_row = st.columns(4)
    risk_top_row[0].metric("平均異常率", f"{overview_summary['異常率'].mean():.2%}" if not overview_summary.empty else "0.00%")
    risk_top_row[1].metric("平均超時率", f"{overview_summary['超時出勤率'].mean():.2%}" if not overview_summary.empty else "0.00%")
    risk_top_row[2].metric("平均風險率", f"{overview_summary['平均風險率'].mean():.2f}" if not overview_summary.empty else "0.00")
    risk_top_row[3].metric("僅居家附近軌跡天數", int(overview_summary["僅居家附近軌跡天數"].fillna(0).sum()) if not overview_summary.empty else 0)

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
        st.markdown("**風險率 vs 異常率**")
        if overview_summary.empty:
            st.info("目前日期區間沒有資料。")
        else:
            scatter_overview = overview_summary.copy()
            scatter_overview["需覆核點數標記"] = scatter_overview["需覆核點數"].fillna(0).clip(lower=1)
            fig_scatter = px.scatter(
                scatter_overview,
                x="異常率",
                y="平均風險率",
                size="需覆核點數標記",
                color="department",
                hover_name="employee_label",
                labels={"異常率": "異常率", "平均風險率": "平均風險率", "department": "部門"},
                hover_data={"需覆核點數": True, "需覆核點數標記": False},
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

    risk_chart1, risk_chart2 = st.columns(2)
    with risk_chart1:
        st.markdown("**員工風險排名**")
        if overview_summary.empty:
            st.info("目前日期區間沒有資料。")
        else:
            fig_risk_rank = px.bar(
                overview_summary.sort_values("風險分數", ascending=False),
                x="employee_label",
                y=["需覆核點數", "高風險點數", "僅居家附近軌跡天數"],
                barmode="group",
                labels={"employee_label": "員工", "value": "數量", "variable": "指標"},
            )
            fig_risk_rank.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), xaxis_tickangle=-35)
            st.plotly_chart(fig_risk_rank, width="stretch")
    with risk_chart2:
        st.markdown("**風險分數排名**")
        if overview_summary.empty:
            st.info("目前日期區間沒有資料。")
        else:
            fig_risk_score = px.bar(
                overview_summary.sort_values("風險分數", ascending=True),
                x="風險分數",
                y="employee_label",
                color="department",
                orientation="h",
                labels={"employee_label": "員工", "風險分數": "風險分數", "department": "部門"},
                hover_data={"需覆核點數": True, "高風險點數": True, "平均風險率": ":.2f"},
            )
            fig_risk_score.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_risk_score, width="stretch")

    claim_chart1, claim_chart2 = st.columns(2)
    with claim_chart1:
        st.markdown("**員工月申請里程 vs 系統預估公務里程**")
        if overview_claim_employee.empty:
            st.info("所選月份目前沒有可比較的月申請里程資料。")
        else:
            claim_bar_df = overview_claim_employee.melt(
                id_vars=["employee_id", "employee_label", "department"],
                value_vars=["實際月申請里程", "系統預估月公務里程"],
                var_name="指標",
                value_name="公里數",
            )
            fig_claim_bar = px.bar(
                claim_bar_df,
                x="employee_label",
                y="公里數",
                color="指標",
                barmode="group",
                hover_data=["department"],
                labels={"employee_label": "員工", "公里數": "公里數", "department": "部門"},
            )
            fig_claim_bar.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), xaxis_tickangle=-35)
            st.plotly_chart(fig_claim_bar, width="stretch")
    with claim_chart2:
        st.markdown("**差異率排名**")
        if overview_claim_employee.empty:
            st.info("所選月份目前沒有可比較的月申請里程資料。")
        else:
            ranking_df = overview_claim_employee.copy()
            ranking_df["差異率顯示"] = ranking_df["差異率"].fillna(0.0)
            fig_claim_rank = px.bar(
                ranking_df.sort_values("差異率絕對值", ascending=True),
                x="差異率顯示",
                y="employee_label",
                color="department",
                orientation="h",
                labels={"employee_label": "員工", "差異率顯示": "差異率", "department": "部門"},
                hover_data={
                    "實際月申請里程": ":.2f",
                    "系統預估月公務里程": ":.2f",
                    "差異里程": ":.2f",
                    "差異率絕對值": False,
                },
            )
            fig_claim_rank.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_claim_rank, width="stretch")

    st.markdown("**月申請里程散點圖**")
    if overview_claim_employee.empty:
        st.info("所選月份目前沒有可比較的月申請里程資料。")
    else:
        scatter_df = overview_claim_employee.copy()
        scatter_df["差異率絕對值"] = scatter_df["差異率絕對值"].fillna(0.0)
        scatter_df["比較燈號"] = scatter_df["比較燈號"].fillna("gray")
        max_axis_value = float(
            max(
                scatter_df["實際月申請里程"].fillna(0).max(),
                scatter_df["系統預估月公務里程"].fillna(0).max(),
                1.0,
            )
        )
        fig_claim_scatter = px.scatter(
            scatter_df,
            x="系統預估月公務里程",
            y="實際月申請里程",
            color="比較燈號",
            color_discrete_map={
                "green": "#16a34a",
                "yellow": "#f59e0b",
                "red": "#dc2626",
                "gray": "#94a3b8",
                "區間不判定": "#94a3b8",
            },
            category_orders={"比較燈號": ["green", "yellow", "red", "gray", "區間不判定"]},
            size="差異率絕對值",
            hover_name="employee_label",
            hover_data={
                "department": True,
                "比較燈號": True,
                "差異里程": ":.2f",
                "差異率": ":.2%",
            },
            labels={
                "系統預估月公務里程": "系統預估月公務里程",
                "實際月申請里程": "實際月申請里程",
                "department": "部門",
                "比較燈號": "比較燈號",
                "差異率絕對值": "差異率絕對值",
            },
        )
        fig_claim_scatter.add_shape(
            type="line",
            x0=0,
            y0=0,
            x1=max_axis_value,
            y1=max_axis_value,
            line=dict(color="#64748b", width=2),
        )
        fig_claim_scatter.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_claim_scatter, width="stretch")
        if overview_is_full_single_month:
            st.caption(
                f"月申請里程比較燈號門檻沿用財務設定：綠燈差異率 <= {float(config.light_green_pct):.0%}，"
                f"黃燈差異率 <= {float(config.light_yellow_pct):.0%}，超過則視為紅燈。差異率以實際月申請里程為分母。"
            )
        else:
            st.caption("燈號僅在選擇完整單月時套用；目前日期區間不是完整單月，散點圖以灰色呈現且不做燈號判定。")

    st.markdown("**全業務明細表**")
    overview_summary_view = overview_summary.rename(
        columns={
            "employee_id": "員工編號",
            "employee_label": "員工",
            "department": "部門",
        }
    )
    render_print_table(
        overview_summary_view,
        [
            "員工編號",
            "員工",
            "部門",
            "出勤天數",
            "總打卡次數",
            "總GPS點數",
            "總計預估里程",
            "總計預估公務里程",
            "未打卡未處理次數",
            "需覆核點數",
            "高風險點數",
            "風險分數",
            "平均風險率",
            "僅居家附近軌跡天數",
            "異常率",
            "超時出勤率",
            "油資補貼",
            "維修補貼",
            "日當費",
        ],
    )
    st.dataframe(
        overview_summary_view,
        width="stretch",
        hide_index=True,
        column_config={
            "總計預估里程": st.column_config.NumberColumn(format="%.2f km"),
            "總計預估公務里程": st.column_config.NumberColumn(format="%.2f km"),
            "平均路徑信心": st.column_config.NumberColumn(format="%.2f"),
            "未打卡未處理次數": st.column_config.NumberColumn(format="%d"),
            "需覆核點數": st.column_config.NumberColumn(format="%d"),
            "高風險點數": st.column_config.NumberColumn(format="%d"),
            "風險分數": st.column_config.NumberColumn(format="%.0f"),
            "平均風險率": st.column_config.NumberColumn(format="%.2f"),
            "僅居家附近軌跡天數": st.column_config.NumberColumn(format="%d"),
            "異常率": st.column_config.NumberColumn(format="%.2%"),
            "超時出勤率": st.column_config.NumberColumn(format="%.2%"),
            "實際加班率": st.column_config.NumberColumn(format="%.2%"),
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

    st.markdown("**Google Sheet 友善版核定參考報表**")
    st.caption("會產出一份可上傳到 Google Drive 並轉成 Google Sheet 的 Excel 檔，包含員工月度彙總、月度核定總表、每日拜訪明細與填寫說明。")
    if st.button("產生核定參考報表 (.xlsx)", key="export_google_sheet_reference", width="stretch"):
        try:
            report_payload = build_google_sheet_reference_payload(
                attendance=attendance,
                daily_metrics=daily_metrics,
                routes=routes,
                finance=finance,
                daily_risk=daily_risk,
                raw_events=raw_events,
                matches=matches,
                employees=employees,
                event_flags=attendance_event_flags,
                monthly_claim_comparison=monthly_claim_comparison,
                google_route_cache=google_route_cache,
                config=config,
                start_date=overview_start_date,
                end_date=overview_end_date,
            )
            reference_output_path = config.reports_dir / reference_report_filename(overview_start_date, overview_end_date)
            export_google_sheet_reference_report(report_payload, reference_output_path)
            st.session_state["reference_report_path"] = str(reference_output_path)
            st.success(f"已產出核定參考報表：{reference_output_path.name}")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

    reference_report_path_text = st.session_state.get("reference_report_path")
    if reference_report_path_text:
        reference_report_path = Path(reference_report_path_text)
        if reference_report_path.exists():
            export_cols = st.columns([1.4, 1.0])
            export_cols[0].caption(f"報表路徑：`{reference_report_path}`")
            export_cols[1].download_button(
                "下載核定參考報表",
                data=reference_report_path.read_bytes(),
                file_name=reference_report_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
                key="download_reference_report",
            )

with tab_route_adjust:
    st.subheader("路徑核算調整")
    st.caption("勾選不應計入自駕里程的 Google Routes 路段；原始路徑距離會保留，報表與財務核算改用排除後里程。")
    if not isinstance(google_route_cache, pd.DataFrame) or google_route_cache.empty:
        st.info("目前沒有 Google Routes 路段快取。請先到「Google Routes 執行」頁面產生路徑資料。")
    else:
        adjust_col1, adjust_col2 = st.columns([1.4, 1.2])
        adjust_employee_options = ["全部員工", *employee_options["employee_label"].tolist()]
        adjust_employee_label = adjust_col1.selectbox(
            "員工",
            options=adjust_employee_options,
            key="route_adjust_employee",
        )
        adjust_dates = attendance["work_date"].dropna().sort_values()
        adjust_default_start = adjust_dates.min().date()
        adjust_default_end = adjust_dates.max().date()
        adjust_range = adjust_col2.date_input(
            "日期區間",
            value=(adjust_default_start, adjust_default_end),
            min_value=adjust_default_start,
            max_value=adjust_default_end,
            key="route_adjust_range",
        )
        if isinstance(adjust_range, tuple) and len(adjust_range) == 2:
            adjust_start_date, adjust_end_date = adjust_range
        else:
            adjust_start_date = adjust_end_date = adjust_default_start

        adjust_attendance = attendance.loc[
            attendance["work_date"].dt.date.between(adjust_start_date, adjust_end_date)
        ].copy()
        if adjust_employee_label != "全部員工":
            adjust_employee_id = employee_label_map[adjust_employee_label]
            adjust_attendance = adjust_attendance.loc[adjust_attendance["employee_id"] == adjust_employee_id].copy()

        segment_view = google_route_cache.copy()
        if "attendance_key" not in segment_view.columns:
            segment_view["attendance_key"] = segment_view["attendance_uid"].astype("string").str.split("_").str[:3].str.join("_")
        segment_view = segment_view.loc[
            segment_view["attendance_key"].isin(adjust_attendance["attendance_key"])
        ].copy()

        if segment_view.empty:
            st.info("所選條件沒有可調整的 Google Routes 路段。")
        else:
            exclusion_view = route_segment_exclusions.copy() if isinstance(route_segment_exclusions, pd.DataFrame) else pd.DataFrame()
            if exclusion_view.empty:
                exclusion_view = pd.DataFrame(columns=["cache_key", "exclude_reason", "exclude_note", "updated_by", "updated_at"])
            segment_view = segment_view.merge(
                exclusion_view[["cache_key", "exclude_reason", "exclude_note", "updated_by", "updated_at"]].drop_duplicates("cache_key"),
                on="cache_key",
                how="left",
            )
            segment_view = segment_view.merge(
                adjust_attendance[["attendance_key", "employee_label", "employee_id", "work_date"]],
                on="attendance_key",
                how="left",
            )
            segment_view["work_date"] = pd.to_datetime(segment_view["work_date"], errors="coerce").dt.strftime("%Y-%m-%d")
            segment_view["不計入預估里程"] = segment_view["exclude_reason"].notna()
            segment_view["路段"] = segment_view["segment_type"].map(
                {
                    "home_to_first": "住家到第一點",
                    "between_points": "打卡點之間",
                    "last_to_home": "最後一點回住家",
                }
            ).fillna(segment_view["segment_type"])
            segment_view["距離(km)"] = pd.to_numeric(segment_view["distance_meters"], errors="coerce").fillna(0) / 1000.0
            segment_view["時間(分)"] = pd.to_numeric(segment_view["duration_seconds"], errors="coerce").fillna(0) / 60.0
            segment_view["排除原因"] = segment_view["exclude_reason"].fillna("未排除").replace({"": "未排除", "None": "未排除"})
            segment_view["備註"] = segment_view["exclude_note"].fillna("")
            edit_columns = [
                "不計入預估里程",
                "排除原因",
                "備註",
                "work_date",
                "employee_label",
                "segment_no",
                "路段",
                "距離(km)",
                "時間(分)",
                "cache_key",
                "attendance_uid",
                "attendance_key",
                "segment_type",
            ]
            edited_segments = st.data_editor(
                segment_view[edit_columns],
                width="stretch",
                hide_index=True,
                disabled=[
                    "work_date",
                    "employee_label",
                    "segment_no",
                    "路段",
                    "距離(km)",
                    "時間(分)",
                    "cache_key",
                    "attendance_uid",
                    "attendance_key",
                    "segment_type",
                ],
                column_config={
                    "不計入預估里程": st.column_config.CheckboxColumn("不計入預估里程"),
                    "排除原因": st.column_config.SelectboxColumn(
                        "排除原因",
                        options=["未排除", "高鐵/公共運輸", "總公司會議", "非自駕", "私人行程", "其他"],
                    ),
                    "距離(km)": st.column_config.NumberColumn("距離(km)", format="%.2f"),
                    "時間(分)": st.column_config.NumberColumn("時間(分)", format="%.1f"),
                    "cache_key": None,
                    "attendance_uid": None,
                    "attendance_key": None,
                    "segment_type": None,
                },
                key="route_segment_adjust_editor",
            )
            excluded_km_preview = float(
                edited_segments.loc[edited_segments["不計入預估里程"], "距離(km)"].fillna(0).sum()
            )
            st.metric("本次畫面勾選排除里程", f"{excluded_km_preview:.2f} km")
            if st.button("儲存路徑核算調整", key="save_route_segment_adjustments", width="stretch"):
                rows_to_save = []
                for _, row in edited_segments.iterrows():
                    is_excluded = bool(row["不計入預估里程"])
                    rows_to_save.append(
                        {
                            "cache_key": row["cache_key"],
                            "attendance_uid": row["attendance_uid"],
                            "attendance_key": row["attendance_key"],
                            "segment_no": int(row["segment_no"]),
                            "segment_type": row["segment_type"],
                            "exclude_from_mileage": is_excluded,
                            "exclude_reason": row["排除原因"] if is_excluded and row["排除原因"] != "未排除" else "",
                            "exclude_note": row["備註"] if is_excluded else "",
                            "updated_by": "streamlit",
                        }
                    )
                upsert_route_segment_exclusions(config.sqlite_path, rows_to_save)
                rebuild_google_route_summary_from_cache(
                    db_path=config.sqlite_path,
                    attendance_slice=adjust_attendance,
                    raw_events=raw_events,
                    employees=employees,
                    route_mode=config.route_mode,
                )
                st.success("已儲存調整，並重新計算排除後里程。")
                st.cache_data.clear()
                st.rerun()

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
