from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from bi_service import BIService
from checkin_importer import CheckinImporter
from db_manager import DatabaseManager
from finance_auditor import FinanceAuditor
from google_routes_service import rebuild_google_route_summary_from_cache
from master_data_service import MasterDataService
from matcher import Matcher
from routing_engine import RoutingEngine
from settings import AppConfig, build_config, ensure_directories


def load_optional_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path, encoding="utf-8-sig")


def create_input_templates(config: AppConfig) -> None:
    monthly_claims = pd.DataFrame(
        [
            {
                "year_month": "2026-04",
                "employee_id": "HS03",
                "claimed_km": "",
                "claim_source": "assistant_import",
                "submitted_at": "",
                "remark": "",
            }
        ]
    )
    attendance_aux = pd.DataFrame(
        [
            {
                "attendance_uid": "",
                "attendance_status": "正常出勤",
                "daily_report_submitted": True,
                "meals_provided_count": 0,
                "remark": "",
            }
        ]
    )
    monthly_claims.to_csv(config.templates_dir / "monthly_claims_template.csv", index=False, encoding="utf-8-sig")
    attendance_aux.to_csv(config.templates_dir / "attendance_aux_template.csv", index=False, encoding="utf-8-sig")


def write_import_manifest(config: AppConfig, source_file: Path, original_file_name: str | None = None) -> None:
    manifest_path = config.reports_dir / "attendance_import_manifest.json"
    existing_payload: dict = {}
    existing_original_name: str | None = None
    if manifest_path.exists():
        try:
            existing_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            existing_original_name = existing_payload.get("original_file_name")
        except Exception:  # noqa: BLE001
            existing_payload = {}
            existing_original_name = None
    payload = {
        "active_attendance_file": str(source_file),
        "stored_file_name": source_file.name,
        "original_file_name": original_file_name or existing_original_name or source_file.name,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "import_file_count": len(existing_payload.get("imports", [])),
        "imports": existing_payload.get("imports", []),
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def select_attendance_excel(data_dir: Path) -> Path:
    candidates = sorted(
        data_dir.glob("*.xlsx"),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("找不到任何 xlsx 打卡檔")
    return candidates[0]


def select_attendance_sources(config: AppConfig) -> list[Path]:
    imported_files = sorted(
        config.attendance_import_dir.glob("*.xlsx"),
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    if imported_files:
        write_import_manifest(config, imported_files[-1], imported_files[-1].name)
        return imported_files

    source = select_attendance_excel(config.data_dir)
    write_import_manifest(config, source)
    return [source]


def import_attendance_batches(importer: CheckinImporter, source_files: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_batches: list[pd.DataFrame] = []
    attendance_batches: list[pd.DataFrame] = []
    for import_order, source_file in enumerate(source_files, start=1):
        raw_events, attendance = importer.import_events(str(source_file))
        raw_events["source_file_name"] = source_file.name
        raw_events["import_order"] = import_order
        attendance["source_file_name"] = source_file.name
        attendance["import_order"] = import_order
        raw_batches.append(raw_events)
        attendance_batches.append(attendance)

    raw_all = pd.concat(raw_batches, ignore_index=True) if raw_batches else pd.DataFrame()
    attendance_all = pd.concat(attendance_batches, ignore_index=True) if attendance_batches else pd.DataFrame()
    if raw_all.empty or attendance_all.empty:
        return raw_all, attendance_all

    latest_order_by_date = (
        attendance_all.dropna(subset=["work_date"])
        .groupby("work_date", dropna=False)["import_order"]
        .max()
        .rename("latest_import_order")
        .reset_index()
    )
    attendance_all = attendance_all.merge(latest_order_by_date, on="work_date", how="left")
    attendance_all = attendance_all.loc[
        attendance_all["latest_import_order"].isna() | (attendance_all["import_order"] == attendance_all["latest_import_order"])
    ].copy()

    raw_all = raw_all.merge(latest_order_by_date, on="work_date", how="left")
    raw_all = raw_all.loc[
        raw_all["latest_import_order"].isna() | (raw_all["import_order"] == raw_all["latest_import_order"])
    ].copy()

    raw_all = raw_all.drop(columns=["latest_import_order", "import_order"], errors="ignore")
    attendance_all = attendance_all.drop(columns=["latest_import_order", "import_order"], errors="ignore")
    return raw_all, attendance_all


def run_pipeline(config: AppConfig | None = None) -> dict[str, pd.DataFrame]:
    config = config or build_config()
    ensure_directories(config)
    create_input_templates(config)

    master_service = MasterDataService(config.data_dir)
    importer = CheckinImporter(config.data_dir)
    matcher = Matcher(
        top_n=config.candidate_top_n,
        hospital_keywords=config.hospital_keywords,
        hospital_exclude_keywords=config.hospital_exclude_keywords,
    )
    routing = RoutingEngine(
        detour_index=config.detour_index,
        average_speed_kmph=config.average_speed_kmph,
        route_mode=config.route_mode,
    )
    finance = FinanceAuditor(
        fuel_rate=config.fuel_rate,
        maintenance_rate=config.maintenance_rate,
        light_green_pct=config.light_green_pct,
        light_yellow_pct=config.light_yellow_pct,
    )
    bi_service = BIService(break_minutes=config.break_minutes)
    db = DatabaseManager(config.sqlite_path)
    db.initialize()

    employees = master_service.load_employees()
    clients = master_service.load_clients()
    hospital_raw, hospital_clean = master_service.load_hospitals()
    xlsx_sources = select_attendance_sources(config)
    raw_events, attendance = import_attendance_batches(importer, xlsx_sources)
    stop_matches = matcher.build_matches(raw_events, attendance, hospital_clean, clients)
    route_summary = routing.summarize_routes(raw_events, attendance, employees, stop_matches)

    monthly_claims = load_optional_csv(config.data_dir / "monthly_claims.csv")
    attendance_aux = load_optional_csv(config.data_dir / "attendance_aux.csv")
    finance_result = finance.audit(route_summary, employees, monthly_claims, attendance_aux)
    daily_metrics = bi_service.build_daily_metrics(attendance, route_summary, stop_matches)
    summary_tables = bi_service.build_summary(daily_metrics, finance_result)

    result_tables = {
        "employee_master": employees,
        "hospital_master_raw": hospital_raw,
        "hospital_master_clean": hospital_clean,
        "client_master": clients,
        "raw_check_events": raw_events,
        "attendance_day_group": attendance,
        "route_stop_match": stop_matches,
        "daily_route_summary": route_summary,
        "finance_audit_result": finance_result,
        "bi_daily_metrics": daily_metrics,
        **summary_tables,
    }

    with db.connect() as conn:
        for table_name in [
            "employee_master",
            "hospital_master_raw",
            "hospital_master_clean",
            "client_master",
            "raw_check_events",
            "attendance_day_group",
            "route_stop_match",
            "daily_route_summary",
            "finance_audit_result",
        ]:
            db.replace_table(conn, table_name, result_tables[table_name])

    rebuild_google_route_summary_from_cache(
        db_path=config.sqlite_path,
        attendance_slice=attendance,
        raw_events=raw_events,
        employees=employees,
        route_mode=config.route_mode,
    )

    for table_name, dataframe in result_tables.items():
        dataframe.to_csv(config.cleaned_dir / f"{table_name}.csv", index=False, encoding="utf-8-sig")

    summary_payload = {
        "employee_count": int(len(employees)),
        "attendance_group_count": int(len(attendance)),
        "raw_event_count": int(len(raw_events)),
        "gps_match_count": int(stop_matches["event_uid"].nunique()) if not stop_matches.empty else 0,
        "route_summary_count": int(len(route_summary)),
        "finance_gray_count": int((finance_result["audit_light"] == "gray").sum()),
        "attendance_source_file": xlsx_sources[-1].name,
        "attendance_source_files": [path.name for path in xlsx_sources],
        "sqlite_path": str(config.sqlite_path),
    }
    (config.reports_dir / "run_summary.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame([summary_payload]).to_csv(
        config.reports_dir / "run_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return result_tables


if __name__ == "__main__":
    run_pipeline()
