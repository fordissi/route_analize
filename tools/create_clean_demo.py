from __future__ import annotations

from pathlib import Path


DEMO_TABS_LINE = (
    "tab_demo, tab_daily, tab_period, tab_overview = st.tabs("
    "['Demo Home', '單日路徑檢視', '個人期間報表', '全業務總覽']"
    ")"
)

DEMO_HOME = '''
with tab_demo:
    st.markdown(
        """
        <div style="padding: 1.4rem 0 1rem 0;">
            <div style="font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; color: #64748b; font-weight: 700;">Function Route Report Demo</div>
            <h1 style="margin: .35rem 0 .45rem 0; font-size: 2.3rem; line-height: 1.08; color: #102033;">外勤路徑與費用稽核展示資料集</h1>
            <p style="max-width: 860px; color: #475569; font-size: 1.02rem; line-height: 1.7;">
                此 demo 使用跨月份模擬資料，呈現北區醫院、南區醫院、北區診所藥局與中區混合通路的拜訪型態差異，
                讓趨勢、申報差異與風險分布能在總覽與個人期間報表中被看見。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    demo_months = sorted(monthly_claim_comparison["year_month"].dropna().unique().tolist()) if "monthly_claim_comparison" in globals() and not monthly_claim_comparison.empty else []
    demo_metric_cols = st.columns(4)
    demo_metric_cols[0].metric("展示月份", f"{len(demo_months)} 個月")
    demo_metric_cols[1].metric("業務人數", int(employees["employee_id"].nunique()) if "employees" in globals() and not employees.empty else 0)
    demo_metric_cols[2].metric("出勤天數", int(attendance["work_date"].dt.date.nunique()) if "attendance" in globals() and not attendance.empty else 0)
    demo_metric_cols[3].metric("申報筆數", int(len(monthly_claim_comparison)) if "monthly_claim_comparison" in globals() else 0)

    demo_employee_source_path = Path(__file__).resolve().parent / "demo_data" / "employees.csv"
    if demo_employee_source_path.exists():
        persona_source = pd.read_csv(demo_employee_source_path, encoding="utf-8-sig")
        if "員工編號" in persona_source.columns and "employee_label" not in persona_source.columns and "employees" in globals() and not employees.empty:
            persona_source = persona_source.merge(
                employees[["employee_id", "employee_label"]],
                left_on="員工編號",
                right_on="employee_id",
                how="left",
            )
        if "department" not in persona_source.columns and "部門" in persona_source.columns:
            persona_source["department"] = persona_source["部門"]
    else:
        persona_source = employees.copy() if "employees" in globals() and not employees.empty else pd.DataFrame()
    if "demo_persona" in persona_source.columns:
        persona_view = (
            persona_source[["employee_label", "department", "demo_persona"]]
            .rename(columns={"employee_label": "業務", "department": "部門", "demo_persona": "展示角色"})
            .sort_values("展示角色")
        )
        st.markdown("**展示角色**")
        st.dataframe(persona_view, width="stretch", hide_index=True)

    st.markdown("**建議展示焦點**")
    focus_cols = st.columns(3)
    focus_cols[0].markdown(
        "<div style='border-left: 4px solid #2563eb; padding-left: .85rem; color: #334155;'><b>全業務總覽</b><br>用完整月份區間觀察風險員工排行、申報差異與月趨勢。</div>",
        unsafe_allow_html=True,
    )
    focus_cols[1].markdown(
        "<div style='border-left: 4px solid #059669; padding-left: .85rem; color: #334155;'><b>個人期間報表</b><br>切換 A/B/C/D 角色，比較醫院、南區、診所藥局與混合通路型態。</div>",
        unsafe_allow_html=True,
    )
    focus_cols[2].markdown(
        "<div style='border-left: 4px solid #d97706; padding-left: .85rem; color: #334155;'><b>單日路徑檢視</b><br>檢視單日 GPS 點、匹配院所、路徑里程與費用摘要。</div>",
        unsafe_allow_html=True,
    )
'''


def _find_line(lines: list[str], marker: str) -> int:
    for index, line in enumerate(lines):
        if marker in line:
            return index
    raise ValueError(f"Cannot find marker: {marker}")


def _replace_load_results_for_demo(lines: list[str]) -> list[str]:
    result = lines.copy()
    load_idx = _find_line(result, "def load_results():")
    config_idx = next(
        index for index in range(load_idx + 1, len(result)) if "config = build_config()" in result[index]
    )
    result[config_idx] = "    config = build_config(root_dir=Path(__file__).resolve().parent / 'demo_data')"
    if config_idx + 1 < len(result) and "run_pipeline(config)" in result[config_idx + 1]:
        del result[config_idx + 1]
    return result


def _find_tabs_block_end(lines: list[str], start_idx: int) -> int:
    depth = 0
    for index in range(start_idx, len(lines)):
        depth += lines[index].count("(")
        depth -= lines[index].count(")")
        if index > start_idx and depth <= 0:
            return index + 1
    return start_idx + 1


def _section(lines: list[str], start_marker: str, end_marker: str) -> list[str]:
    start = _find_line(lines, start_marker)
    end = _find_line(lines, end_marker)
    return lines[start:end]


def build_demo_app(root_dir: str | Path | None = None) -> Path:
    root = Path(root_dir or Path(__file__).resolve().parent.parent)
    app_path = root / "app.py"
    demo_app_path = root / "demo_app.py"

    lines = _replace_load_results_for_demo(app_path.read_text(encoding="utf-8").splitlines())
    tabs_idx = _find_line(lines, "tab_home, tab_daily")
    tabs_end = _find_tabs_block_end(lines, tabs_idx)

    prefix = lines[:tabs_idx]
    daily_section = _section(lines, "with tab_daily:", "with tab_weekly:")
    period_section = _section(lines, "with tab_period:", "with tab_overview:")
    overview_section = _section(lines, "with tab_overview:", "with tab_route_adjust:")

    final_lines = [
        *prefix,
        DEMO_TABS_LINE,
        DEMO_HOME.strip("\n"),
        *daily_section,
        *period_section,
        *overview_section,
    ]
    demo_app_path.write_text("\n".join(final_lines).rstrip() + "\n", encoding="utf-8")
    return demo_app_path


if __name__ == "__main__":
    path = build_demo_app()
    print(f"Successfully built {path}")
