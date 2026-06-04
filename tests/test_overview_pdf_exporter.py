import base64

import pandas as pd
import plotly.express as px

from overview_pdf_exporter import (
    OverviewPdfContext,
    build_overview_pdf_context,
    build_overview_pdf_bytes,
    figure_to_png_data_uri,
    render_overview_html,
)


def test_figure_to_png_data_uri_uses_static_png_renderer():
    fig = px.bar(pd.DataFrame({"employee": ["A"], "score": [3]}), x="score", y="employee")

    data_uri = figure_to_png_data_uri(
        fig,
        image_renderer=lambda figure, width, height, scale: b"\x89PNG\r\nfake",
        width=1200,
        height=360,
        scale=2,
    )

    assert data_uri.startswith("data:image/png;base64,")
    assert base64.b64decode(data_uri.split(",", 1)[1]).startswith(b"\x89PNG")


def test_render_overview_html_includes_metrics_charts_and_table():
    html = render_overview_html(
        OverviewPdfContext(
            title="全業務日期區間總覽",
            period_label="2026-01-01 ~ 2026-01-31",
            metrics=[("需覆核點數", "12"), ("平均風險優先分", "8.50")],
            rankings=[("高風險員工 Top 5", [("HS01 李小明", "7")])],
            charts=[("員工風險排名", "data:image/png;base64,abc")],
            summary_table=pd.DataFrame([{"員工": "HS01 李小明", "主要風險原因": "高風險打卡點"}]),
        )
    )

    assert "@page" in html
    assert "A4 portrait" in html
    assert "全業務日期區間總覽" in html
    assert "data:image/png;base64,abc" in html
    assert "HS01 李小明" in html


def test_build_overview_pdf_bytes_returns_renderer_output():
    context = OverviewPdfContext(
        title="全業務日期區間總覽",
        period_label="2026-01",
        metrics=[],
        rankings=[],
        charts=[],
        summary_table=pd.DataFrame(),
    )

    pdf = build_overview_pdf_bytes(context, pdf_renderer=lambda html: b"%PDF-1.4\nfake")

    assert pdf.startswith(b"%PDF")


def test_build_overview_pdf_context_builds_overview_charts_and_rankings():
    overview_summary = pd.DataFrame(
        [
            {
                "employee_id": "HS01",
                "employee_label": "HS01 李小明",
                "department": "北區",
                "出勤天數": 2,
                "總打卡次數": 6,
                "總GPS點數": 5,
                "總出勤時數": 8.5,
                "總計預估里程": 120.0,
                "總計預估公務里程": 100.0,
                "需覆核點數": 3,
                "高風險點數": 2,
                "低信心點數": 1,
                "僅居家附近軌跡天數": 1,
                "風險優先分": 30.0,
                "平均風險優先分": 15.0,
                "平均風險率": 4.0,
                "異常率": 0.2,
                "超時出勤率": 0.1,
                "油資補貼": 1000.0,
                "維修補貼": 0.0,
                "日當費": 500.0,
                "主要風險原因": "高風險打卡點",
                "追查提示": "查看個人報表",
            }
        ]
    )
    claim_employee = pd.DataFrame(
        [
            {
                "employee_id": "HS01",
                "employee_label": "HS01 李小明",
                "department": "北區",
                "實際月申請里程": 90.0,
                "系統預估月公務里程": 100.0,
                "差異里程": -10.0,
                "差異率": -0.1,
                "差異率絕對值": 0.1,
                "比較燈號": "green",
            }
        ]
    )
    company_monthly = pd.DataFrame(
        [
            {
                "year_month": "2026-01",
                "month_label": "2026-01",
                "month_index": 0,
                "employee_count": 1,
                "risky_employee_count": 1,
                "risky_employee_rate": 1.0,
                "risk_priority_per_day": 15.0,
                "high_risk_event_count": 2,
                "review_event_count": 3,
                "home_area_only_days": 1,
            }
        ]
    )

    rendered_figures = []

    def capture_figure(figure, width, height, scale):
        rendered_figures.append(figure)
        return b"\x89PNG\r\nfake"

    context = build_overview_pdf_context(
        overview_summary=overview_summary,
        overview_claim_employee=claim_employee,
        company_monthly=company_monthly,
        month_order=["2026-01"],
        start_date="2026-01-01",
        end_date="2026-01-31",
        image_renderer=capture_figure,
    )

    assert context.period_label == "2026-01-01 ~ 2026-01-31"
    assert len(context.charts) >= 10
    assert context.rankings[0][1][0] == ("HS01 李小明", "2")
    assert "員工" in context.summary_table.columns

    scatter_figures = [
        figure
        for figure in rendered_figures
        if figure.layout.title.text in {"風險率 vs 異常率", "月申請里程散點圖"}
    ]
    assert len(scatter_figures) == 2
    for figure in scatter_figures:
        assert any(trace.mode == "markers+text" for trace in figure.data)
        assert any("HS01" in [str(text) for text in trace.text] for trace in figure.data if trace.text is not None)


def test_overview_pdf_context_limits_monthly_charts_to_recent_twelve_months():
    company_monthly = pd.DataFrame(
        [
            {
                "year_month": f"2025-{month:02d}",
                "month_label": f"2025-{month:02d}",
                "month_index": month - 1,
                "employee_count": 10,
                "risky_employee_count": 5,
                "risky_employee_rate": 0.5,
                "risk_priority_per_day": float(month),
                "high_risk_event_count": month,
                "review_event_count": month,
                "home_area_only_days": 0,
            }
            for month in range(1, 13)
        ]
        + [
            {
                "year_month": f"2026-{month:02d}",
                "month_label": f"2026-{month:02d}",
                "month_index": month + 11,
                "employee_count": 10,
                "risky_employee_count": 5,
                "risky_employee_rate": 0.5,
                "risk_priority_per_day": float(month),
                "high_risk_event_count": month,
                "review_event_count": month,
                "home_area_only_days": 0,
            }
            for month in range(1, 7)
        ]
    )
    rendered_figures = []

    build_overview_pdf_context(
        overview_summary=pd.DataFrame(),
        overview_claim_employee=pd.DataFrame(),
        company_monthly=company_monthly,
        month_order=[*company_monthly["year_month"].tolist()],
        start_date="2025-01-01",
        end_date="2026-06-30",
        image_renderer=lambda figure, width, height, scale: (rendered_figures.append(figure) or b"\x89PNG\r\nfake"),
    )

    assert len(rendered_figures) == 3
    for figure in rendered_figures:
        assert list(figure.layout.xaxis.ticktext) == [
            "2025-07",
            "2025-08",
            "2025-09",
            "2025-10",
            "2025-11",
            "2025-12",
            "2026-01",
            "2026-02",
            "2026-03",
            "2026-04",
            "2026-05",
            "2026-06",
        ]
        assert list(figure.layout.xaxis.range) == [-0.5, 11.5]
