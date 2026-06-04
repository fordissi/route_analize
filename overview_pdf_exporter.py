from __future__ import annotations

import base64
import html
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd
import plotly.express as px

from risk_presentation import prepare_month_axis_for_pdf


ImageRenderer = Callable[[object, int, int, int], bytes]
PdfRenderer = Callable[[str], bytes]

CHART_COLORS = [
    "#0f766e",
    "#2563eb",
    "#f97316",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
    "#64748b",
    "#84cc16",
]


@dataclass(frozen=True)
class OverviewPdfContext:
    title: str
    period_label: str
    metrics: list[tuple[str, str]]
    rankings: list[tuple[str, list[tuple[str, str]]]]
    charts: list[tuple[str, str]]
    summary_table: pd.DataFrame


def _apply_static_chart_layout(fig: object, title: str, *, height: int, margin: dict[str, int]) -> None:
    chart_text_color = "#111827"
    axis_text_color = "#374151"
    fig.update_layout(
        template="plotly_white",
        title=dict(text=title, x=0, xanchor="left", font=dict(size=22, color=chart_text_color)),
        height=height,
        margin=margin,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color=chart_text_color, size=15),
        colorway=CHART_COLORS,
        legend=dict(font=dict(color=chart_text_color, size=13)),
    )
    fig.update_xaxes(
        gridcolor="#e5e7eb",
        linecolor="#9ca3af",
        zerolinecolor="#9ca3af",
        tickfont=dict(color=axis_text_color, size=13),
        title_font=dict(color=axis_text_color, size=15),
    )
    fig.update_yaxes(
        gridcolor="#e5e7eb",
        linecolor="#9ca3af",
        zerolinecolor="#9ca3af",
        tickfont=dict(color=axis_text_color, size=13),
        title_font=dict(color=axis_text_color, size=15),
    )
    for index, trace in enumerate(fig.data):
        color = CHART_COLORS[index % len(CHART_COLORS)]
        if hasattr(trace, "marker"):
            trace.marker.color = color
        if hasattr(trace, "line"):
            trace.line.color = color
    fig.update_traces(textfont=dict(color=chart_text_color, size=12))


def _show_scatter_employee_labels(fig: object) -> None:
    positions = ["top center", "bottom center", "middle right", "middle left", "top right", "bottom right"]
    for trace in fig.data:
        text_values = list(trace.text) if trace.text is not None else []
        trace.mode = "markers+text"
        trace.textposition = [positions[index % len(positions)] for index, _ in enumerate(text_values)]
        trace.textfont = dict(color="#111827", size=11)
        trace.cliponaxis = False


def _positive_range(series: pd.Series, *, factor: float = 1.12) -> list[float]:
    max_value = pd.to_numeric(series, errors="coerce").fillna(0).max()
    return [0, max(float(max_value) * factor, 1.0)]


def _format_metric(value: object, value_type: str = "float") -> str:
    if pd.isna(value):
        return "-"
    if value_type == "int":
        return f"{int(float(value))}"
    if value_type == "percent":
        return f"{float(value):.2%}"
    if value_type == "km":
        return f"{float(value):.2f} km"
    return f"{float(value):.2f}"


def _ranking_rows(rows: pd.DataFrame, label_col: str, value_col: str, value_type: str) -> list[tuple[str, str]]:
    if rows.empty:
        return []
    result = []
    for _, row in rows.head(5).iterrows():
        result.append((str(row.get(label_col, "") or "未命名"), _format_metric(row.get(value_col), value_type)))
    return result


def _build_overview_figures(
    overview_summary: pd.DataFrame,
    overview_claim_employee: pd.DataFrame,
    company_monthly: pd.DataFrame | None,
    month_order: list[str] | None,
) -> list[tuple[str, object, int]]:
    charts: list[tuple[str, object, int]] = []

    if company_monthly is not None and not company_monthly.empty and month_order:
        company_monthly, month_order, tickvals, ticktext = prepare_month_axis_for_pdf(
            company_monthly,
            max_months=12,
            max_ticks=12,
        )
        company_line = company_monthly.melt(
            id_vars=["year_month", "month_label", "month_index"],
            value_vars=["risk_priority_per_day", "risky_employee_rate"],
            var_name="指標",
            value_name="數值",
        )
        company_line["指標"] = company_line["指標"].map(
            {
                "risk_priority_per_day": "每出勤日風險優先分",
                "risky_employee_rate": "需優先追查員工占比",
            }
        )
        fig_company_trend = px.line(company_line, x="month_index", y="數值", color="指標", markers=True)
        fig_company_trend.update_traces(line=dict(width=4))
        fig_company_trend.update_xaxes(
            title_text="月份",
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickangle=-25,
            ticklabeloverflow="allow",
            range=[-0.5, max(len(month_order) - 0.5, 0.5)],
        )
        _apply_static_chart_layout(
            fig_company_trend,
            "風險月趨勢：每出勤日風險優先分 / 需優先追查員工占比",
            height=420,
            margin=dict(l=80, r=140, t=58, b=74),
        )
        charts.append(("風險月趨勢：每出勤日風險優先分 / 需優先追查員工占比", fig_company_trend, 420))

        employee_count_view = company_monthly.rename(
            columns={"employee_count": "納入員工數", "risky_employee_count": "需優先追查員工數"}
        )
        fig_employee_count = px.bar(
            employee_count_view,
            x="month_index",
            y=["納入員工數", "需優先追查員工數"],
            barmode="group",
            labels={"value": "人數", "variable": "指標"},
        )
        fig_employee_count.update_xaxes(
            title_text="月份",
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickangle=-25,
            ticklabeloverflow="allow",
            range=[-0.5, max(len(month_order) - 0.5, 0.5)],
        )
        _apply_static_chart_layout(
            fig_employee_count,
            "風險月趨勢：納入員工數 / 需優先追查員工數",
            height=420,
            margin=dict(l=80, r=140, t=58, b=74),
        )
        charts.append(("風險月趨勢：納入員工數 / 需優先追查員工數", fig_employee_count, 420))

        company_monthly_view = company_monthly.rename(
            columns={
                "high_risk_event_count": "高風險點數",
                "review_event_count": "需覆核點數",
                "home_area_only_days": "僅居家附近天數",
            }
        )
        fig_company_stack = px.bar(
            company_monthly_view,
            x="month_index",
            y=["高風險點數", "需覆核點數", "僅居家附近天數"],
            barmode="group",
            labels={"value": "數量", "variable": "指標"},
        )
        fig_company_stack.update_xaxes(
            title_text="月份",
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickangle=-25,
            ticklabeloverflow="allow",
            range=[-0.5, max(len(month_order) - 0.5, 0.5)],
        )
        _apply_static_chart_layout(
            fig_company_stack,
            "月風險類型分布",
            height=420,
            margin=dict(l=80, r=140, t=58, b=74),
        )
        charts.append(("月風險類型分布", fig_company_stack, 420))

    if not overview_summary.empty:
        fig_km = px.bar(
            overview_summary.sort_values("總計預估里程", ascending=True),
            x="總計預估里程",
            y="employee_label",
            color="department",
            text_auto=".1f",
            orientation="h",
            labels={"employee_label": "員工", "總計預估里程": "總計預估里程(km)", "department": "部門"},
        )
        _apply_static_chart_layout(fig_km, "各業務總計預估里程比較", height=520, margin=dict(l=170, r=180, t=58, b=68))
        fig_km.update_xaxes(range=_positive_range(overview_summary["總計預估里程"]))
        charts.append(("各業務總計預估里程比較", fig_km, 520))

        scatter_overview = overview_summary.copy()
        scatter_overview["需覆核點數標記"] = scatter_overview["需覆核點數"].fillna(0).clip(lower=1)
        fig_scatter = px.scatter(
            scatter_overview,
            x="異常率",
            y="平均風險率",
            size="需覆核點數標記",
            color="department",
            text="employee_id",
            hover_name="employee_label",
            labels={"異常率": "異常率", "平均風險率": "平均風險率", "department": "部門"},
        )
        _apply_static_chart_layout(fig_scatter, "風險率 vs 異常率", height=420, margin=dict(l=80, r=180, t=64, b=74))
        _show_scatter_employee_labels(fig_scatter)
        fig_scatter.update_xaxes(range=_positive_range(scatter_overview["異常率"], factor=1.18))
        fig_scatter.update_yaxes(range=_positive_range(scatter_overview["平均風險率"], factor=1.18))
        charts.append(("風險率 vs 異常率", fig_scatter, 420))

        fig_hours = px.bar(
            overview_summary.sort_values("總出勤時數", ascending=True),
            x=["總出勤時數", "總GPS點數"],
            y="employee_label",
            barmode="group",
            orientation="h",
            labels={"employee_label": "員工", "value": "數值", "variable": "指標"},
        )
        _apply_static_chart_layout(fig_hours, "出勤時數與 GPS 點數比較", height=520, margin=dict(l=170, r=180, t=58, b=68))
        fig_hours.update_xaxes(range=_positive_range(overview_summary[["總出勤時數", "總GPS點數"]].stack()))
        charts.append(("出勤時數與 GPS 點數比較", fig_hours, 520))

        subsidy_chart_data = overview_summary.sort_values("油資補貼", ascending=False)
        fig_subsidy = px.bar(
            subsidy_chart_data,
            x="employee_label",
            y=["油資補貼", "維修補貼", "日當費"],
            barmode="stack",
            labels={"employee_label": "員工", "value": "金額", "variable": "補貼項目"},
        )
        _apply_static_chart_layout(fig_subsidy, "財務補貼總覽", height=420, margin=dict(l=80, r=150, t=58, b=110))
        fig_subsidy.update_layout(xaxis_tickangle=-30)
        charts.append(("財務補貼總覽", fig_subsidy, 420))

        fig_risk_rank = px.bar(
            overview_summary.sort_values("風險優先分", ascending=True),
            x=["需覆核點數", "高風險點數", "低信心點數", "僅居家附近軌跡天數"],
            y="employee_label",
            barmode="group",
            orientation="h",
            labels={"employee_label": "員工", "value": "數量", "variable": "指標"},
        )
        _apply_static_chart_layout(fig_risk_rank, "員工風險排名", height=520, margin=dict(l=170, r=180, t=58, b=68))
        fig_risk_rank.update_xaxes(
            range=_positive_range(overview_summary[["需覆核點數", "高風險點數", "低信心點數", "僅居家附近軌跡天數"]].stack())
        )
        charts.append(("員工風險排名", fig_risk_rank, 520))

        fig_risk_score = px.bar(
            overview_summary.sort_values("風險優先分", ascending=True),
            x="風險優先分",
            y="employee_label",
            color="department",
            orientation="h",
            labels={"employee_label": "員工", "風險優先分": "風險優先分", "department": "部門"},
        )
        _apply_static_chart_layout(fig_risk_score, "風險優先分排名", height=500, margin=dict(l=170, r=180, t=58, b=68))
        fig_risk_score.update_xaxes(range=_positive_range(overview_summary["風險優先分"]))
        charts.append(("風險優先分排名", fig_risk_score, 500))

    if not overview_claim_employee.empty:
        claim_bar_df = overview_claim_employee.melt(
            id_vars=["employee_id", "employee_label", "department"],
            value_vars=["實際月申請里程", "系統預估月公務里程"],
            var_name="指標",
            value_name="公里數",
        )
        fig_claim_bar = px.bar(
            claim_bar_df,
            x="公里數",
            y="employee_label",
            color="指標",
            barmode="group",
            orientation="h",
            labels={"employee_label": "員工", "公里數": "公里數"},
        )
        _apply_static_chart_layout(fig_claim_bar, "員工月申請里程 vs 系統預估公務里程", height=520, margin=dict(l=170, r=180, t=58, b=68))
        fig_claim_bar.update_xaxes(range=_positive_range(claim_bar_df["公里數"]))
        charts.append(("員工月申請里程 vs 系統預估公務里程", fig_claim_bar, 520))

        ranking_df = overview_claim_employee.copy()
        ranking_df["差異率顯示"] = ranking_df["差異率"].fillna(0.0)
        fig_claim_rank = px.bar(
            ranking_df.sort_values("差異率絕對值", ascending=True),
            x="差異率顯示",
            y="employee_label",
            color="department",
            orientation="h",
            labels={"employee_label": "員工", "差異率顯示": "差異率", "department": "部門"},
        )
        _apply_static_chart_layout(fig_claim_rank, "差異率排名", height=500, margin=dict(l=170, r=180, t=58, b=68))
        claim_rank_values = pd.to_numeric(ranking_df["差異率顯示"], errors="coerce").dropna()
        if not claim_rank_values.empty:
            claim_rank_min = float(claim_rank_values.min())
            claim_rank_max = float(claim_rank_values.max())
            claim_rank_span = max(claim_rank_max - claim_rank_min, 1.0)
            fig_claim_rank.update_xaxes(range=[claim_rank_min - claim_rank_span * 0.08, claim_rank_max + claim_rank_span * 0.12])
        charts.append(("差異率排名", fig_claim_rank, 500))

        scatter_df = overview_claim_employee.copy()
        scatter_df["差異率絕對值"] = scatter_df["差異率絕對值"].fillna(0.0)
        scatter_df["比較燈號"] = scatter_df["比較燈號"].fillna("gray")
        max_axis_value = float(max(scatter_df["實際月申請里程"].fillna(0).max(), scatter_df["系統預估月公務里程"].fillna(0).max(), 1.0))
        fig_claim_scatter = px.scatter(
            scatter_df,
            x="系統預估月公務里程",
            y="實際月申請里程",
            color="比較燈號",
            color_discrete_map={"green": "#16a34a", "yellow": "#f59e0b", "red": "#dc2626", "gray": "#94a3b8", "區間不判定": "#94a3b8"},
            size="差異率絕對值",
            text="employee_id",
            hover_name="employee_label",
            labels={"系統預估月公務里程": "系統預估月公務里程", "實際月申請里程": "實際月申請里程"},
        )
        fig_claim_scatter.add_shape(type="line", x0=0, y0=0, x1=max_axis_value, y1=max_axis_value, line=dict(color="#64748b", width=3))
        _apply_static_chart_layout(fig_claim_scatter, "月申請里程散點圖", height=460, margin=dict(l=90, r=180, t=64, b=80))
        _show_scatter_employee_labels(fig_claim_scatter)
        claim_scatter_limit = max(max_axis_value * 1.18, 1.0)
        fig_claim_scatter.update_xaxes(range=[0, claim_scatter_limit])
        fig_claim_scatter.update_yaxes(range=[0, claim_scatter_limit])
        charts.append(("月申請里程散點圖", fig_claim_scatter, 460))

    return charts


def build_overview_pdf_context(
    *,
    overview_summary: pd.DataFrame,
    overview_claim_employee: pd.DataFrame,
    company_monthly: pd.DataFrame | None,
    month_order: list[str] | None,
    start_date: object,
    end_date: object,
    image_renderer: ImageRenderer | None = None,
) -> OverviewPdfContext:
    metrics = [
        ("納入比較員工數", f"{len(overview_summary)}"),
        ("全員總計預估里程", _format_metric(overview_summary["總計預估里程"].sum() if not overview_summary.empty else 0, "km")),
        ("全員總計公務里程", _format_metric(overview_summary["總計預估公務里程"].sum() if not overview_summary.empty else 0, "km")),
        ("需覆核點數", _format_metric(overview_summary["需覆核點數"].fillna(0).sum() if not overview_summary.empty else 0, "int")),
        ("高風險點數", _format_metric(overview_summary["高風險點數"].fillna(0).sum() if not overview_summary.empty else 0, "int")),
        ("平均異常率", _format_metric(overview_summary["異常率"].mean() if not overview_summary.empty else 0, "percent")),
        ("平均超時率", _format_metric(overview_summary["超時出勤率"].mean() if not overview_summary.empty else 0, "percent")),
        ("平均風險優先分", _format_metric(overview_summary["平均風險優先分"].mean() if not overview_summary.empty else 0, "float")),
    ]

    high_risk_rank = overview_summary.sort_values(["高風險點數", "風險優先分"], ascending=[False, False]) if not overview_summary.empty else overview_summary
    review_rank = overview_summary.sort_values(["需覆核點數", "風險優先分"], ascending=[False, False]) if not overview_summary.empty else overview_summary
    home_rank = overview_summary.sort_values(["僅居家附近軌跡天數", "風險優先分"], ascending=[False, False]) if not overview_summary.empty else overview_summary
    claim_diff_rank = overview_claim_employee.sort_values("差異率絕對值", ascending=False) if not overview_claim_employee.empty else overview_claim_employee

    rankings = [
        ("高風險員工 Top 5", _ranking_rows(high_risk_rank, "employee_label", "高風險點數", "int")),
        ("需覆核點數 Top 5", _ranking_rows(review_rank, "employee_label", "需覆核點數", "int")),
        ("僅居家附近 Top 5", _ranking_rows(home_rank, "employee_label", "僅居家附近軌跡天數", "int")),
        ("申報差異 Top 5", _ranking_rows(claim_diff_rank, "employee_label", "差異率絕對值", "percent")),
    ]

    charts = [
        (title, figure_to_png_data_uri(fig, image_renderer=image_renderer, width=1200, height=height, scale=1))
        for title, fig, height in _build_overview_figures(overview_summary, overview_claim_employee, company_monthly, month_order or [])
    ]

    summary_columns = [
        "employee_id",
        "employee_label",
        "department",
        "出勤天數",
        "總打卡次數",
        "總GPS點數",
        "總計預估里程",
        "需覆核點數",
        "高風險點數",
        "低信心點數",
        "平均風險優先分",
        "主要風險原因",
        "追查提示",
    ]
    summary_table = overview_summary[[column for column in summary_columns if column in overview_summary.columns]].rename(
        columns={"employee_id": "員工編號", "employee_label": "員工", "department": "部門"}
    )

    return OverviewPdfContext(
        title="全業務日期區間總覽",
        period_label=f"{start_date} ~ {end_date}",
        metrics=metrics,
        rankings=rankings,
        charts=charts,
        summary_table=summary_table,
    )


def _default_image_renderer(fig: object, width: int, height: int, scale: int) -> bytes:
    return fig.to_image(format="png", width=width, height=height, scale=scale, engine="kaleido")


def figure_to_png_data_uri(
    fig: object,
    *,
    image_renderer: ImageRenderer | None = None,
    width: int = 1200,
    height: int = 360,
    scale: int = 2,
) -> str:
    renderer = image_renderer or _default_image_renderer
    png_bytes = renderer(fig, width, height, scale)
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _format_table_cell(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _render_metric_cards(metrics: Iterable[tuple[str, str]]) -> str:
    cards = []
    for label, value in metrics:
        cards.append(
            '<div class="metric-card">'
            f"<div class=\"metric-label\">{html.escape(str(label))}</div>"
            f"<div class=\"metric-value\">{html.escape(str(value))}</div>"
            "</div>"
        )
    return '<section class="metric-grid">' + "".join(cards) + "</section>"


def _render_rankings(rankings: Iterable[tuple[str, list[tuple[str, str]]]]) -> str:
    blocks = []
    for title, rows in rankings:
        items = []
        if not rows:
            items.append('<li><span>無資料</span><strong>-</strong></li>')
        else:
            for label, value in rows[:5]:
                items.append(
                    "<li>"
                    f"<span>{html.escape(str(label))}</span>"
                    f"<strong>{html.escape(str(value))}</strong>"
                    "</li>"
                )
        blocks.append(
            '<article class="ranking-card">'
            f"<h3>{html.escape(str(title))}</h3>"
            f"<ol>{''.join(items)}</ol>"
            "</article>"
        )
    return '<section class="ranking-grid">' + "".join(blocks) + "</section>"


def _render_charts(charts: Iterable[tuple[str, str]]) -> str:
    items = []
    for title, data_uri in charts:
        items.append(
            '<section class="chart-block">'
            f'<img src="{html.escape(data_uri, quote=True)}" alt="{html.escape(str(title), quote=True)}" />'
            "</section>"
        )
    return "".join(items)


def _render_summary_table(summary_table: pd.DataFrame, *, max_rows: int = 18) -> str:
    if summary_table.empty:
        return '<p class="muted">目前沒有明細資料。</p>'
    table = summary_table.head(max_rows).copy()
    headers = "".join(f"<th>{html.escape(str(column))}</th>" for column in table.columns)
    rows = []
    for _, row in table.iterrows():
        cells = "".join(f"<td>{html.escape(_format_table_cell(value))}</td>" for value in row)
        rows.append(f"<tr>{cells}</tr>")
    note = f'<p class="muted">僅列出前 {max_rows} 筆明細。</p>' if len(summary_table) > max_rows else ""
    return f'<div class="table-wrap"><table><thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>{note}'


def render_overview_html(context: OverviewPdfContext) -> str:
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
    h2 {{ font-size: 13px; margin: 0 0 6px; }}
    h3 {{ font-size: 10px; margin: 0 0 4px; }}
    .report-header {{
      border-bottom: 1px solid #d1d5db;
      margin-bottom: 12px;
      padding-bottom: 8px;
    }}
    .period {{ color: #4b5563; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 6px;
      margin: 8px 0 12px;
    }}
    .metric-card {{
      border: 1px solid #d1d5db;
      padding: 6px 7px;
      min-height: 38px;
      break-inside: avoid;
    }}
    .metric-label {{ font-weight: 700; font-size: 8px; color: #374151; }}
    .metric-value {{ font-size: 13px; font-weight: 800; margin-top: 2px; }}
    .ranking-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px;
      margin: 8px 0 12px;
      break-inside: avoid;
    }}
    .ranking-card {{ border: 1px solid #111827; padding: 5px 7px; }}
    .ranking-card ol {{ margin: 0; padding-left: 16px; }}
    .ranking-card li {{ display: flex; justify-content: space-between; gap: 8px; border-bottom: 1px solid #e5e7eb; padding: 2px 0; }}
    .chart-block {{
      margin: 10px 0 14px;
      break-inside: avoid;
      page-break-inside: avoid;
    }}
    .chart-block img {{
      width: 100%;
      display: block;
      border: 0;
    }}
    .table-wrap {{ overflow: visible; }}
    .summary-table {{
      break-before: page;
      page-break-before: always;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 8.5px;
      line-height: 1.22;
    }}
    thead {{ display: table-header-group; }}
    tbody {{ display: table-row-group; }}
    tr {{ break-inside: avoid; page-break-inside: avoid; }}
    th, td {{ border: 1px solid #111827; padding: 2px 3px; vertical-align: top; word-break: break-word; }}
    th {{ font-weight: 800; background: #f3f4f6; }}
    .muted {{ color: #6b7280; }}
  </style>
</head>
<body>
  <header class="report-header">
    <h1>{html.escape(context.title)}</h1>
    <div class="period">{html.escape(context.period_label)}</div>
  </header>
  {_render_metric_cards(context.metrics)}
  {_render_rankings(context.rankings)}
  {_render_charts(context.charts)}
  <section class="summary-table">
    <h2>全業務明細表</h2>
    {_render_summary_table(context.summary_table)}
  </section>
</body>
</html>"""


def _default_pdf_renderer(html_content: str) -> bytes:
    script_path = Path(__file__).with_name("tools") / "html_to_pdf.mjs"
    if not script_path.exists():
        raise FileNotFoundError(f"Missing PDF renderer script: {script_path}")

    with tempfile.TemporaryDirectory(prefix="overview_pdf_") as temp_dir:
        temp_path = Path(temp_dir)
        html_path = temp_path / "overview_report.html"
        pdf_path = temp_path / "overview_report.pdf"
        html_path.write_text(html_content, encoding="utf-8")
        subprocess.run(
            ["node", str(script_path), str(html_path), str(pdf_path)],
            check=True,
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
        )
        return pdf_path.read_bytes()


def build_overview_pdf_bytes(context: OverviewPdfContext, *, pdf_renderer: PdfRenderer | None = None) -> bytes:
    renderer = pdf_renderer or _default_pdf_renderer
    return renderer(render_overview_html(context))
