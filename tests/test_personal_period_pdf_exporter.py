import base64

import pandas as pd
import plotly.express as px

from personal_period_pdf_exporter import (
    PersonalPeriodPdfContext,
    build_personal_period_pdf_bytes,
    build_personal_period_pdf_context,
    render_personal_period_html,
)


def test_render_personal_period_html_includes_header_charts_and_tables():
    html = render_personal_period_html(
        PersonalPeriodPdfContext(
            title="個人期間報表",
            employee_label="HS02 李俊智",
            period_label="2026-05-04 ~ 2026-05-29",
            selected_period="2026-05",
            month_label="2026-05",
            risk_metrics=[("需覆核點數", "16"), ("平均風險優先分", "12.75")],
            route_metrics=[("總出勤時數", "86.47 小時")],
            claim_metrics=[("月申請里程", "0.00 km")],
            charts=[("個人風險月趨勢", "data:image/png;base64,abc")],
            summary_table=pd.DataFrame([{"員工": "HS02 李俊智", "需覆核點數": 16}]),
            claim_table=pd.DataFrame([{"月份": "2026-05", "差異里程": -1360.31}]),
            place_risk_table=pd.DataFrame([{"地點名稱": "德風藥局", "風險拜訪次數": 1}]),
            detail_table=pd.DataFrame([{"日期": "2026-05-14", "主要風險原因": "高風險打卡點"}]),
        )
    )

    assert "@page" in html
    assert "A4 portrait" in html
    assert "HS02 李俊智" in html
    assert "data:image/png;base64,abc" in html
    assert "德風藥局" in html


def test_build_personal_period_pdf_bytes_returns_renderer_output():
    context = PersonalPeriodPdfContext(
        title="個人期間報表",
        employee_label="HS02 李俊智",
        period_label="2026-05-04 ~ 2026-05-29",
        selected_period="2026-05",
        month_label="2026-05",
        risk_metrics=[],
        route_metrics=[],
        claim_metrics=[],
        charts=[],
        summary_table=pd.DataFrame(),
        claim_table=pd.DataFrame(),
        place_risk_table=pd.DataFrame(),
        detail_table=pd.DataFrame(),
    )

    pdf = build_personal_period_pdf_bytes(context, pdf_renderer=lambda html: b"%PDF-1.4\nfake")

    assert pdf.startswith(b"%PDF")


def test_build_personal_period_pdf_context_builds_static_charts_and_metrics():
    summary_df = pd.DataFrame(
        [
            {
                "員工": "HS02 李俊智",
                "部門": "中區營業處",
                "報表起日": "2026-05-04",
                "報表迄日": "2026-05-29",
                "出勤天數": 20,
                "總出勤時數": 86.47,
                "總有效外勤時數": 47.88,
                "總打卡次數": 50,
                "總GPS點數": 44,
                "總計預估里程": 1360.31,
                "總計預估公務里程": 1360.31,
                "平均每日里程": 68.02,
                "平均每日公務里程": 68.02,
                "未打卡未處理次數": 6,
                "異常率": 0.85,
                "超時出勤率": 0.0,
                "實際加班率": 0.0,
                "需覆核點數": 16,
                "高風險點數": 16,
                "低信心點數": 4,
                "風險優先分": 255.0,
                "綜合優先分": 255.0,
                "異常風險分": 80.0,
                "開發/覆核分": 16.0,
                "未配對打卡次數": 4,
                "平均風險優先分": 12.75,
                "平均綜合優先分": 12.75,
                "僅居家附近軌跡天數": 0,
            }
        ]
    )
    detail_df = pd.DataFrame(
        [
            {"日期": "2026-05-14", "主要風險原因": "高風險打卡點", "風險優先分": 25.0},
            {"日期": "2026-05-15", "主要風險原因": "可能在家附近打卡", "風險優先分": 12.0},
        ]
    )
    monthly_trend = pd.DataFrame(
        [
            {
                "year_month": "2026-04",
                "month_label": "2026-04",
                "month_index": 0,
                "risk_priority_per_day": 15.5,
                "risk_score": 20,
                "review_score": 8,
                "high_risk_event_count": 14,
                "review_event_count": 14,
                "home_area_only_days": 1,
            },
            {
                "year_month": "2026-05",
                "month_label": "2026-05",
                "month_index": 1,
                "risk_priority_per_day": 12.75,
                "risk_score": 16,
                "review_score": 16,
                "high_risk_event_count": 16,
                "review_event_count": 16,
                "home_area_only_days": 0,
            },
        ]
    )
    monthly_claims = pd.DataFrame(
        [
            {
                "year_month": "2026-05",
                "claimed_km": 0.0,
                "estimated_business_km": 1360.31,
                "difference_km": -1360.31,
                "difference_rate": pd.NA,
                "comparison_light": "gray",
            }
        ]
    )
    place_risk_table = pd.DataFrame([{"地點名稱": "德風藥局", "風險拜訪次數": 1}])
    rendered_figures = []

    def capture_figure(figure, width, height, scale):
        rendered_figures.append(figure)
        return b"\x89PNG\r\nfake"

    context = build_personal_period_pdf_context(
        employee_label="HS02 李俊智",
        period_label="2026-05-04 ~ 2026-05-29",
        selected_period="2026-05",
        month_label="2026-05",
        summary_df=summary_df,
        detail_df=detail_df,
        monthly_trend=monthly_trend,
        month_order=["2026-04", "2026-05"],
        monthly_claims=monthly_claims,
        place_risk_table=place_risk_table,
        image_renderer=capture_figure,
    )

    assert context.employee_label == "HS02 李俊智"
    assert ("開發/覆核分", "16.00") in context.risk_metrics
    assert ("未配對打卡次數", "4") in context.risk_metrics
    assert ("總出勤時數", "86.47 小時") in context.route_metrics
    assert ("月申請里程", "0.00 km") in context.claim_metrics
    assert len(context.charts) == 2
    assert base64.b64decode(context.charts[0][1].split(",", 1)[1]).startswith(b"\x89PNG")
    assert [figure.layout.title.text for figure in rendered_figures] == [
        "個人風險月趨勢：每出勤日風險優先分",
        "個人風險月趨勢：分數拆解",
    ]


def test_personal_period_pdf_context_limits_monthly_charts_to_recent_six_months():
    monthly_trend = pd.DataFrame(
        [
            {
                "year_month": f"2026-{month:02d}",
                "month_label": f"2026-{month:02d}",
                "month_index": month - 1,
                "risk_priority_per_day": float(month),
                "high_risk_event_count": month,
                "review_event_count": month,
                "home_area_only_days": 0,
            }
            for month in range(1, 10)
        ]
    )
    rendered_figures = []

    build_personal_period_pdf_context(
        employee_label="HS02 李俊智",
        period_label="2026-01-01 ~ 2026-09-30",
        selected_period="2026-01 ~ 2026-09",
        month_label="2026-01、2026-02、2026-03、2026-04、2026-05、2026-06、2026-07、2026-08、2026-09",
        summary_df=pd.DataFrame(),
        detail_df=pd.DataFrame(),
        monthly_trend=monthly_trend,
        month_order=[f"2026-{month:02d}" for month in range(1, 10)],
        monthly_claims=pd.DataFrame(),
        place_risk_table=pd.DataFrame(),
        image_renderer=lambda figure, width, height, scale: (rendered_figures.append(figure) or b"\x89PNG\r\nfake"),
    )

    for figure in rendered_figures:
        assert list(figure.layout.xaxis.ticktext) == [
            "2026-04",
            "2026-05",
            "2026-06",
            "2026-07",
            "2026-08",
            "2026-09",
        ]
        assert list(figure.layout.xaxis.range) == [-0.5, 5.5]
