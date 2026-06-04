import csv
import io
import zipfile

import pandas as pd

from personal_period_batch_exporter import (
    PersonalPeriodBatchPdfInput,
    build_personal_period_batch_pdf_zip,
    safe_report_filename,
)
from personal_period_pdf_exporter import PersonalPeriodPdfContext


def _context(employee_label: str) -> PersonalPeriodPdfContext:
    return PersonalPeriodPdfContext(
        title="個人期間報表",
        employee_label=employee_label,
        period_label="2026-05-01 ~ 2026-05-31",
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


def test_safe_report_filename_removes_characters_that_break_zip_paths():
    assert safe_report_filename("HS02 李/俊:智 2026-05.pdf") == "HS02_李_俊_智_2026-05.pdf"


def test_build_personal_period_batch_pdf_zip_writes_each_pdf_and_result_csv():
    inputs = [
        PersonalPeriodBatchPdfInput(
            employee_id="HS02",
            employee_label="HS02 李俊智",
            filename="HS02_李俊智_2026-05.pdf",
            context=_context("HS02 李俊智"),
        ),
        PersonalPeriodBatchPdfInput(
            employee_id="WS09",
            employee_label="WS09 陳育錫",
            filename="WS09_陳育錫_2026-05.pdf",
            context=_context("WS09 陳育錫"),
        ),
    ]

    result = build_personal_period_batch_pdf_zip(
        inputs,
        pdf_builder=lambda context: f"%PDF fake {context.employee_label}".encode("utf-8"),
    )

    assert result.success_count == 2
    assert result.failure_count == 0
    with zipfile.ZipFile(io.BytesIO(result.zip_bytes)) as archive:
        assert sorted(archive.namelist()) == [
            "HS02_李俊智_2026-05.pdf",
            "WS09_陳育錫_2026-05.pdf",
            "batch_result.csv",
        ]
        assert archive.read("HS02_李俊智_2026-05.pdf").startswith(b"%PDF fake HS02")
        rows = list(csv.DictReader(io.StringIO(archive.read("batch_result.csv").decode("utf-8-sig"))))

    assert rows == [
        {
            "employee_id": "HS02",
            "employee_label": "HS02 李俊智",
            "filename": "HS02_李俊智_2026-05.pdf",
            "status": "success",
            "message": "",
        },
        {
            "employee_id": "WS09",
            "employee_label": "WS09 陳育錫",
            "filename": "WS09_陳育錫_2026-05.pdf",
            "status": "success",
            "message": "",
        },
    ]


def test_build_personal_period_batch_pdf_zip_keeps_failed_employee_in_result_csv():
    inputs = [
        PersonalPeriodBatchPdfInput(
            employee_id="HS02",
            employee_label="HS02 李俊智",
            filename="HS02.pdf",
            context=_context("HS02 李俊智"),
        ),
        PersonalPeriodBatchPdfInput(
            employee_id="WS09",
            employee_label="WS09 陳育錫",
            filename="WS09.pdf",
            context=_context("WS09 陳育錫"),
        ),
    ]

    def pdf_builder(context: PersonalPeriodPdfContext) -> bytes:
        if context.employee_label.startswith("WS09"):
            raise RuntimeError("render failed")
        return b"%PDF ok"

    result = build_personal_period_batch_pdf_zip(inputs, pdf_builder=pdf_builder)

    assert result.success_count == 1
    assert result.failure_count == 1
    with zipfile.ZipFile(io.BytesIO(result.zip_bytes)) as archive:
        assert "HS02.pdf" in archive.namelist()
        assert "WS09.pdf" not in archive.namelist()
        rows = list(csv.DictReader(io.StringIO(archive.read("batch_result.csv").decode("utf-8-sig"))))

    assert rows[1]["status"] == "failed"
    assert rows[1]["message"] == "render failed"
