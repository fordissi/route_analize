from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from typing import Callable, Iterable

from personal_period_pdf_exporter import PersonalPeriodPdfContext, build_personal_period_pdf_bytes


PdfBuilder = Callable[[PersonalPeriodPdfContext], bytes]


@dataclass(frozen=True)
class PersonalPeriodBatchPdfInput:
    employee_id: str
    employee_label: str
    filename: str
    context: PersonalPeriodPdfContext


@dataclass(frozen=True)
class PersonalPeriodBatchPdfResult:
    zip_bytes: bytes
    success_count: int
    failure_count: int
    rows: list[dict[str, str]]


def safe_report_filename(filename: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "_", str(filename).strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return cleaned or "personal_period_report.pdf"


def build_personal_period_batch_pdf_zip(
    inputs: Iterable[PersonalPeriodBatchPdfInput],
    *,
    pdf_builder: PdfBuilder = build_personal_period_pdf_bytes,
) -> PersonalPeriodBatchPdfResult:
    archive_buffer = io.BytesIO()
    rows: list[dict[str, str]] = []
    success_count = 0
    failure_count = 0

    with zipfile.ZipFile(archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in inputs:
            filename = safe_report_filename(item.filename)
            try:
                pdf_bytes = pdf_builder(item.context)
                archive.writestr(filename, pdf_bytes)
                status = "success"
                message = ""
                success_count += 1
            except Exception as exc:
                status = "failed"
                message = str(exc)
                failure_count += 1

            rows.append(
                {
                    "employee_id": str(item.employee_id),
                    "employee_label": str(item.employee_label),
                    "filename": filename,
                    "status": status,
                    "message": message,
                }
            )

        csv_buffer = io.StringIO()
        fieldnames = ["employee_id", "employee_label", "filename", "status", "message"]
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        archive.writestr("batch_result.csv", "\ufeff" + csv_buffer.getvalue())

    return PersonalPeriodBatchPdfResult(
        zip_bytes=archive_buffer.getvalue(),
        success_count=success_count,
        failure_count=failure_count,
        rows=rows,
    )
