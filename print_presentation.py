from __future__ import annotations

import html
from typing import Any

import pandas as pd


def _cell_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def build_print_table_html(
    dataframe: pd.DataFrame,
    columns: list[str] | None = None,
    *,
    title: str | None = None,
    max_rows: int | None = None,
    wide_text_columns: list[str] | None = None,
    table_class: str = "",
) -> str:
    if dataframe.empty:
        return ""

    print_view = dataframe.copy()
    if columns is not None:
        print_view = print_view[[column for column in columns if column in print_view.columns]].copy()
    if max_rows is not None and max_rows > 0:
        original_count = len(print_view)
        print_view = print_view.head(max_rows).copy()
    else:
        original_count = len(print_view)

    if wide_text_columns is None:
        wide_keywords = ("原因", "摘要", "重點", "提示", "reason", "summary", "focus", "evidence")
        wide_columns = {
            column
            for column in print_view.columns
            if any(keyword in str(column).lower() for keyword in wide_keywords)
        }
    else:
        wide_columns = set(wide_text_columns)
    class_tokens = ["print-table"]
    if table_class:
        class_tokens.extend(token for token in table_class.split() if token)

    title_html = f'<div class="print-section-title">{html.escape(title)}</div>' if title else ""
    head_cells = []
    for column in print_view.columns:
        column_class = ' class="print-col-wide-text"' if column in wide_columns else ""
        head_cells.append(f"<th{column_class}>{html.escape(str(column))}</th>")

    body_rows = []
    for _, row in print_view.iterrows():
        cells = []
        for column in print_view.columns:
            column_class = ' class="print-col-wide-text"' if column in wide_columns else ""
            cells.append(f"<td{column_class}>{html.escape(_cell_text(row[column]))}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    limit_note = ""
    if max_rows is not None and max_rows > 0 and original_count > len(print_view):
        limit_note = f'<div class="print-table-note">僅列印前 {len(print_view)} 筆，共 {original_count} 筆。</div>'

    return (
        '<div class="print-only print-table-block">'
        f"{title_html}"
        f'<table class="{" ".join(class_tokens)}">'
        f"<thead><tr>{''.join(head_cells)}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        f"{limit_note}"
        "</div>"
    )
