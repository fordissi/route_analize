import pandas as pd

from print_presentation import build_print_table_html


def test_build_print_table_html_limits_columns_rows_and_marks_text_columns():
    dataframe = pd.DataFrame(
        [
            {"date": "2026-05-01", "score": 10, "reason": "可能在家附近打卡", "ignored": "x"},
            {"date": "2026-05-02", "score": 3, "reason": "選定與最近候選差距大", "ignored": "y"},
        ]
    )

    html = build_print_table_html(
        dataframe,
        columns=["date", "reason"],
        title="風險摘要",
        max_rows=1,
        wide_text_columns=["reason"],
        table_class="print-table--compact",
    )

    assert "風險摘要" in html
    assert "print-table--compact" in html
    assert "print-col-wide-text" in html
    assert "可能在家附近打卡" in html
    assert "選定與最近候選差距大" not in html
    assert "ignored" not in html
    assert "僅列印前 1 筆" in html


def test_build_print_table_html_escapes_cell_content():
    dataframe = pd.DataFrame([{"name": "<script>alert(1)</script>"}])

    html = build_print_table_html(dataframe)

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_build_print_table_html_marks_reason_summary_columns_as_wide_by_default():
    dataframe = pd.DataFrame([{"追查重點": "可能在家附近打卡", "分數": 6}])

    html = build_print_table_html(dataframe)

    assert "print-col-wide-text" in html
