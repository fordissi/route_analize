import pandas as pd

from print_presentation import build_print_table_html


def test_build_print_table_html_limits_columns_rows_and_marks_text_columns():
    dataframe = pd.DataFrame(
        [
            {"date": "2026-05-01", "score": 10, "reason": "near home", "ignored": "x"},
            {"date": "2026-05-02", "score": 3, "reason": "far candidate", "ignored": "y"},
        ]
    )

    html = build_print_table_html(
        dataframe,
        columns=["date", "reason"],
        title="Risk summary",
        max_rows=1,
        wide_text_columns=["reason"],
        table_class="print-table--compact",
    )

    assert "Risk summary" in html
    assert "print-table--compact" in html
    assert "print-col-wide-text" in html
    assert "near home" in html
    assert "far candidate" not in html
    assert "ignored" not in html
    assert "1" in html


def test_build_print_table_html_escapes_cell_content():
    dataframe = pd.DataFrame([{"name": "<script>alert(1)</script>"}])

    html = build_print_table_html(dataframe)

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_build_print_table_html_marks_reason_summary_columns_as_wide_by_default():
    dataframe = pd.DataFrame([{"risk_summary": "near home", "count": 6}])

    html = build_print_table_html(dataframe)

    assert "print-col-wide-text" in html


def test_build_print_table_html_limits_wide_detail_tables_for_print_pages():
    dataframe = pd.DataFrame(
        [
            {f"col_{column}": f"{row}-{column}" for column in range(15)}
            for row in range(18)
        ]
    )

    html = build_print_table_html(dataframe)

    assert "period-detail-table" in html
    assert "17-0" not in html
    assert "16" in html


def test_build_print_table_html_handles_duplicate_column_labels():
    dataframe = pd.DataFrame([["判定來源", "候選來源"]], columns=["最近醫院", "最近醫院"])

    html = build_print_table_html(dataframe, columns=["最近醫院"])

    assert "判定來源" in html
