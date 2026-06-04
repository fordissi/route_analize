from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.generate_mock_data import generate_mock_data
from tools.create_clean_demo import build_demo_app


def test_generate_mock_data_builds_multi_month_regional_demo(tmp_path: Path):
    source_hospitals = pd.DataFrame(
        [
            {
                "機構代碼": "N-HOSP-001",
                "機構名稱": "台北示範醫院",
                "電話": "",
                "縣市區名": "台北市信義區",
                "地址": "台北市信義區松仁路1號",
                "科別": "",
                "Response_Address": "台北市信義區松仁路1號",
                "Response_X": 121.568,
                "Response_Y": 25.034,
            },
            {
                "機構代碼": "S-HOSP-001",
                "機構名稱": "高雄示範醫院",
                "電話": "",
                "縣市區名": "高雄市左營區",
                "地址": "高雄市左營區博愛二路1號",
                "科別": "",
                "Response_Address": "高雄市左營區博愛二路1號",
                "Response_X": 120.303,
                "Response_Y": 22.665,
            },
            {
                "機構代碼": "N-CLINIC-001",
                "機構名稱": "北區示範藥局",
                "電話": "",
                "縣市區名": "新北市板橋區",
                "地址": "新北市板橋區文化路1號",
                "科別": "藥局",
                "Response_Address": "新北市板橋區文化路1號",
                "Response_X": 121.466,
                "Response_Y": 25.014,
            },
        ]
    )
    source_hospitals.to_csv(tmp_path / "hospitals.csv", index=False, encoding="utf-8-sig")

    summary = generate_mock_data(
        root_dir=tmp_path,
        run_pipeline_after=False,
        month_count=4,
    )

    demo_dir = tmp_path / "demo_data"
    employees = pd.read_csv(demo_dir / "employees.csv", encoding="utf-8-sig")
    claims = pd.read_csv(demo_dir / "monthly_claims.csv", encoding="utf-8-sig")
    demo_hospitals = pd.read_csv(demo_dir / "hospitals.csv", encoding="utf-8-sig")
    attendance = pd.read_excel(demo_dir / "mock_attendance.xlsx", header=5)

    assert summary["month_count"] == 4
    assert summary["employee_count"] >= 4
    assert set(["北區醫院業務", "南區醫院業務", "北區診所藥局業務"]).issubset(
        set(employees["demo_persona"])
    )
    assert claims["year_month"].nunique() == 4
    assert attendance["工作日期"].nunique() >= 24
    assert demo_hospitals["機構代碼"].tolist() == source_hospitals["機構代碼"].tolist()
    assert demo_hospitals["機構名稱"].tolist() == source_hospitals["機構名稱"].tolist()


def test_build_demo_app_keeps_focused_demo_tabs(tmp_path: Path):
    source = tmp_path / "app.py"
    target = tmp_path / "demo_app.py"
    source.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "from settings import build_config",
                "from pipeline import run_pipeline",
                "def load_results():",
                "    config = build_config()",
                "    run_pipeline(config)",
                "    return {'ok': True}",
                "tables = load_results()",
                "tab_home, tab_daily, tab_weekly, tab_period, tab_overview, tab_route_adjust = st.tabs(['首頁流程', '單日路徑檢視', '週路徑檢視', '個人期間報表', '全業務總覽', '路徑核算調整'])",
                "with tab_home:",
                "    st.write('home')",
                "with tab_daily:",
                "    st.write('daily')",
                "with tab_weekly:",
                "    st.write('weekly')",
                "with tab_period:",
                "    st.write('period')",
                "with tab_overview:",
                "    st.write('overview')",
                "with tab_route_adjust:",
                "    st.write('route adjust')",
            ]
        ),
        encoding="utf-8",
    )

    build_demo_app(root_dir=tmp_path)

    demo_text = target.read_text(encoding="utf-8")
    assert "root_dir=Path(__file__).resolve().parent / 'demo_data'" in demo_text
    assert "run_pipeline(config)" not in demo_text
    assert "Demo Home" in demo_text
    assert "全業務總覽" in demo_text
    assert "route adjust" not in demo_text
