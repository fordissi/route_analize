from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

import pandas as pd
import plotly.express as px

from overview_pdf_exporter import (
    ImageRenderer,
    PdfRenderer,
    _apply_static_chart_layout,
    _default_pdf_renderer,
    _format_metric,
    figure_to_png_data_uri,
)
from risk_presentation import prepare_month_axis_for_pdf


def _ensure_numeric_column(dataframe: pd.DataFrame, column: str, fallback: str | None = None) -> None:
    if column in dataframe.columns:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0)
    elif fallback and fallback in dataframe.columns:
        dataframe[column] = pd.to_numeric(dataframe[fallback], errors="coerce").fillna(0)
    else:
        dataframe[column] = 0


@dataclass(frozen=True)
class PersonalPeriodPdfContext:
    title: str
    employee_label: str
    period_label: str
    selected_period: str
    month_label: str
    risk_metrics: list[tuple[str, str]]
    route_metrics: list[tuple[str, str]]
    claim_metrics: list[tuple[str, str]]
    charts: list[tuple[str, str]]
    summary_table: pd.DataFrame
    claim_table: pd.DataFrame
    place_risk_table: pd.DataFrame
    detail_table: pd.DataFrame


def _first_row(dataframe: pd.DataFrame) -> pd.Series:
    if dataframe.empty:
        return pd.Series(dtype=object)
    return dataframe.iloc[0]


def _safe_value(row: pd.Series, label: str, default: object = 0) -> object:
    return row.get(label, default) if not row.empty else default


def _metric_from_row(row: pd.Series, label: str, value_type: str = "float", suffix: str = "") -> tuple[str, str]:
    value = _format_metric(_safe_value(row, label), value_type)
    if suffix and value != "-":
        value = f"{value} {suffix}"
    return label, value


def _format_percent(value: object) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):.2%}"


def _build_personal_figures(
    monthly_trend: pd.DataFrame,
    month_order: list[str] | None,
) -> list[tuple[str, object, int]]:
    charts: list[tuple[str, object, int]] = []
    if monthly_trend.empty or not month_order:
        return charts

    trend, month_order, tickvals, ticktext = prepare_month_axis_for_pdf(
        monthly_trend,
        max_months=6,
        max_ticks=6,
    )
    _ensure_numeric_column(trend, "risk_score")
    _ensure_numeric_column(trend, "review_score")
    fig_personal_trend = px.line(
        trend,
        x="month_index",
        y="risk_priority_per_day",
        markers=True,
        labels={"risk_priority_per_day": "每出勤日風險優先分"},
    )
    fig_personal_trend.update_traces(line=dict(width=4))
    fig_personal_trend.update_xaxes(
        title_text="月份",
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
        tickangle=-25,
        ticklabeloverflow="allow",
        range=[-0.5, max(len(month_order) - 0.5, 0.5)],
    )
    _apply_static_chart_layout(
        fig_personal_trend,
        "個人風險月趨勢：每出勤日風險優先分",
        height=400,
        margin=dict(l=86, r=96, t=64, b=74),
    )
    charts.append(("個人風險月趨勢：每出勤日風險優先分", fig_personal_trend, 400))

    monthly_event_view = trend.rename(columns={"risk_score": "異常風險分", "review_score": "開發/覆核分"})
    fig_personal_stack = px.bar(
        monthly_event_view,
        x="month_index",
        y=["異常風險分", "開發/覆核分"],
        barmode="group",
        labels={"value": "分數", "variable": "指標"},
    )
    fig_personal_stack.update_xaxes(
        title_text="月份",
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
        tickangle=-25,
        ticklabeloverflow="allow",
        range=[-0.5, max(len(month_order) - 0.5, 0.5)],
    )
    _apply_static_chart_layout(
        fig_personal_stack,
        "個人風險月趨勢：分數拆解",
        height=400,
        margin=dict(l=74, r=132, t=64, b=74),
    )
    charts.append(("個人風險月趨勢：分數拆解", fig_personal_stack, 400))
    return charts


def _select_columns(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe
    available_columns = [column for column in columns if column in dataframe.columns]
    if not available_columns:
        return dataframe
    return dataframe[available_columns].copy()


def build_personal_period_pdf_context(
    *,
    employee_label: str,
    period_label: str,
    selected_period: str,
    month_label: str,
    summary_df: pd.DataFrame,
    detail_df: pd.DataFrame,
    monthly_trend: pd.DataFrame,
    month_order: list[str] | None,
    monthly_claims: pd.DataFrame,
    place_risk_table: pd.DataFrame,
    image_renderer: ImageRenderer | None = None,
) -> PersonalPeriodPdfContext:
    summary_df = summary_df.copy()
    fallback_columns = {
        "綜合優先分": "風險優先分",
        "平均綜合優先分": "平均風險優先分",
        "異常風險分": "風險分數",
        "高風險打卡次數": "高風險點數",
        "未配對打卡次數": "需覆核點數",
    }
    for target, source in fallback_columns.items():
        if target not in summary_df.columns:
            summary_df[target] = summary_df[source] if source in summary_df.columns else 0
    if "開發/覆核分" not in summary_df.columns:
        summary_df["開發/覆核分"] = 0
    summary_row = _first_row(summary_df)

    risk_metrics = [
        _metric_from_row(summary_row, "開發/覆核分", "float"),
        _metric_from_row(summary_row, "異常風險分", "float"),
        _metric_from_row(summary_row, "平均綜合優先分", "float"),
        _metric_from_row(summary_row, "僅居家附近軌跡天數", "int"),
        _metric_from_row(summary_row, "未配對打卡次數", "int"),
    ]
    route_metrics = [
        _metric_from_row(summary_row, "總出勤時數", "float", "小時"),
        _metric_from_row(summary_row, "總打卡次數", "int"),
        ("異常率", _format_percent(_safe_value(summary_row, "異常率"))),
        ("超時出勤率", _format_percent(_safe_value(summary_row, "超時出勤率"))),
        _metric_from_row(summary_row, "總有效外勤時數", "float", "小時"),
        _metric_from_row(summary_row, "總GPS點數", "int"),
        _metric_from_row(summary_row, "總計預估里程", "km"),
        _metric_from_row(summary_row, "總計預估公務里程", "km"),
        _metric_from_row(summary_row, "平均每日里程", "km"),
        _metric_from_row(summary_row, "平均每日公務里程", "km"),
        _metric_from_row(summary_row, "未打卡未處理次數", "int"),
        ("實際加班率", _format_percent(_safe_value(summary_row, "實際加班率"))),
    ]

    if monthly_claims.empty:
        claim_metrics = [("月申請里程", "-"), ("月預估公務里程", "-"), ("差異里程", "-"), ("差異率", "-")]
    else:
        claim_total = float(pd.to_numeric(monthly_claims.get("claimed_km", 0), errors="coerce").fillna(0).sum())
        estimate_total = float(pd.to_numeric(monthly_claims.get("estimated_business_km", 0), errors="coerce").fillna(0).sum())
        diff_total = float(pd.to_numeric(monthly_claims.get("difference_km", 0), errors="coerce").fillna(0).sum())
        diff_rate = diff_total / claim_total if claim_total > 0 else pd.NA
        claim_metrics = [
            ("月申請里程", _format_metric(claim_total, "km")),
            ("月預估公務里程", _format_metric(estimate_total, "km")),
            ("差異里程", _format_metric(diff_total, "km")),
            ("差異率", _format_percent(diff_rate)),
        ]

    charts = [
        (title, figure_to_png_data_uri(fig, image_renderer=image_renderer, width=1200, height=height, scale=1))
        for title, fig, height in _build_personal_figures(monthly_trend, month_order or [])
    ]

    summary_table = _select_columns(
        summary_df,
        [
            "員工",
            "部門",
            "報表起日",
            "報表迄日",
            "出勤天數",
            "總出勤時數",
            "總打卡次數",
            "總GPS點數",
            "總計預估里程",
            "開發/覆核分",
            "未配對打卡次數",
            "高風險打卡次數",
            "平均綜合優先分",
            "異常風險分",
            "主要風險原因",
        ],
    )
    claim_table = monthly_claims.rename(
        columns={
            "year_month": "月份",
            "claimed_km": "實際月申請里程",
            "estimated_business_km": "系統預估月公務里程",
            "difference_km": "差異里程",
            "difference_rate": "差異率",
            "comparison_light": "比較燈號",
        }
    )
    claim_table = _select_columns(
        claim_table,
        ["月份", "實際月申請里程", "系統預估月公務里程", "差異里程", "差異率", "比較燈號"],
    )
    place_table = _select_columns(
        place_risk_table,
        [
            "地點名稱",
            "客戶類型",
            "拜訪次數",
            "高風險",
            "需覆核",
            "正常",
            "風險拜訪次數",
            "主要風險原因",
            "地點風險摘要",
        ],
    )
    detail_table = _select_columns(
        detail_df,
        [
            "日期",
            "打卡次數",
            "GPS點數",
            "預估公務里程",
            "需覆核點數",
            "高風險點數",
            "風險優先分",
            "風險等級",
            "主要風險原因",
            "追查提示",
        ],
    )

    return PersonalPeriodPdfContext(
        title="個人期間報表",
        employee_label=employee_label,
        period_label=period_label,
        selected_period=selected_period,
        month_label=month_label,
        risk_metrics=risk_metrics,
        route_metrics=route_metrics,
        claim_metrics=claim_metrics,
        charts=charts,
        summary_table=summary_table,
        claim_table=claim_table,
        place_risk_table=place_table,
        detail_table=detail_table,
    )


def _format_table_cell(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _render_metric_grid(title: str, metrics: Iterable[tuple[str, str]], columns: int = 4) -> str:
    cards = []
    for label, value in metrics:
        cards.append(
            '<div class="metric-card">'
            f'<div class="metric-label">{html.escape(str(label))}</div>'
            f'<div class="metric-value">{html.escape(str(value))}</div>'
            "</div>"
        )
    return (
        '<section class="report-section">'
        f"<h2>{html.escape(title)}</h2>"
        f'<div class="metric-grid metric-grid-{columns}">'
        + "".join(cards)
        + "</div></section>"
    )


def _render_charts(charts: Iterable[tuple[str, str]]) -> str:
    return "".join(
        '<section class="chart-block">'
        f'<img src="{html.escape(data_uri, quote=True)}" alt="{html.escape(title, quote=True)}" />'
        "</section>"
        for title, data_uri in charts
    )


def _render_table(title: str, dataframe: pd.DataFrame, *, max_rows: int = 18, section_class: str = "") -> str:
    if dataframe.empty:
        return f'<section class="report-section {section_class}"><h2>{html.escape(title)}</h2><p class="muted">無資料</p></section>'
    table = dataframe.head(max_rows).copy()
    headers = "".join(f"<th>{html.escape(str(column))}</th>" for column in table.columns)
    rows = []
    for _, row in table.iterrows():
        cells = "".join(f"<td>{html.escape(_format_table_cell(value))}</td>" for value in row)
        rows.append(f"<tr>{cells}</tr>")
    note = f'<p class="muted">僅顯示前 {max_rows} 筆。</p>' if len(dataframe) > max_rows else ""
    return (
        f'<section class="report-section {section_class}">'
        f"<h2>{html.escape(title)}</h2>"
        f'<div class="table-wrap"><table><thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        f"{note}</section>"
    )


def render_personal_period_html(context: PersonalPeriodPdfContext) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(context.title)}</title>
  <style>
    @page {{ size: A4 portrait; margin: 1cm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #111827;
      background: #ffffff;
      font-family: "Microsoft JhengHei", "Noto Sans TC", Arial, sans-serif;
      font-size: 10px;
      line-height: 1.35;
    }}
    h1 {{ font-size: 18px; margin: 0 0 4px; }}
    h2 {{ font-size: 12px; margin: 0 0 6px; }}
    .report-header {{
      border: 1px solid #111827;
      margin-bottom: 12px;
      padding: 8px 10px;
      break-inside: avoid;
    }}
    .meta-row {{ color: #374151; }}
    .report-section {{ margin: 9px 0 12px; }}
    .metric-grid {{
      display: grid;
      gap: 6px;
      margin-top: 6px;
    }}
    .metric-grid-4 {{ grid-template-columns: repeat(4, 1fr); }}
    .metric-grid-5 {{ grid-template-columns: repeat(5, 1fr); }}
    .metric-card {{
      border: 1px solid #d1d5db;
      padding: 6px 7px;
      min-height: 38px;
      break-inside: avoid;
    }}
    .metric-label {{ font-weight: 700; font-size: 8px; color: #374151; }}
    .metric-value {{ font-size: 13px; font-weight: 800; margin-top: 2px; }}
    .chart-row {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      break-inside: avoid;
      page-break-inside: avoid;
    }}
    .chart-block img {{
      width: 100%;
      display: block;
      border: 0;
    }}
    .page-break {{
      break-before: page;
      page-break-before: always;
    }}
    .table-wrap {{ overflow: visible; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 8.2px;
      line-height: 1.2;
    }}
    thead {{ display: table-header-group; }}
    tr {{ break-inside: avoid; page-break-inside: avoid; }}
    th, td {{ border: 1px solid #111827; padding: 2px 3px; vertical-align: top; word-break: break-word; }}
    th {{ font-weight: 800; background: #f3f4f6; }}
    .muted {{ color: #6b7280; }}
  </style>
</head>
<body>
  <header class="report-header">
    <h1>{html.escape(context.title)}</h1>
    <div class="meta-row">姓名：{html.escape(context.employee_label)}</div>
    <div class="meta-row">期間：{html.escape(context.period_label)}</div>
    <div class="meta-row">月份：{html.escape(context.month_label)}</div>
    <div class="meta-row">篩選：{html.escape(context.selected_period)}</div>
  </header>
  {_render_metric_grid("覆核風險摘要", context.risk_metrics, columns=5)}
  <section class="report-section">
    <h2>個人風險月趨勢</h2>
    <div class="chart-row">{_render_charts(context.charts)}</div>
  </section>
  {_render_metric_grid("出勤與里程摘要", context.route_metrics, columns=4)}
  {_render_table("報表摘要", context.summary_table, max_rows=4)}
  {_render_metric_grid("月申請里程 vs 系統預估公務里程", context.claim_metrics, columns=4)}
  {_render_table("月申請里程明細", context.claim_table, max_rows=8)}
  {_render_table("拜訪場所風險", context.place_risk_table, max_rows=8)}
  {_render_table("每日明細", context.detail_table, max_rows=22, section_class="page-break")}
</body>
</html>"""


def build_personal_period_pdf_bytes(context: PersonalPeriodPdfContext, *, pdf_renderer: PdfRenderer | None = None) -> bytes:
    renderer = pdf_renderer or _default_pdf_renderer
    return renderer(render_personal_period_html(context))
