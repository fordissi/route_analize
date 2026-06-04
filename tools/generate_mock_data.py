from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from pipeline import run_pipeline
from settings import build_config


ATTENDANCE_COLUMNS = [
    "#",
    "員工編號",
    "姓名",
    "部門",
    "工作日期",
    "打卡地址",
    "應刷卡時間",
    "實際打卡時間",
    "卡別",
    "比對結果",
    "異常處理",
    "來源",
    "備註",
    "超時出勤",
    "超時出勤原因",
    "超時出勤說明",
]

HOSPITAL_COLUMNS = [
    "機構代碼",
    "機構名稱",
    "電話",
    "縣市區名",
    "地址",
    "科別",
    "Response_Address",
    "Response_X",
    "Response_Y",
]


@dataclass(frozen=True)
class EmployeeScenario:
    employee_id: str
    name: str
    department: str
    persona: str
    home_lat: float
    home_lon: float
    office_lat: float
    office_lon: float
    region: str
    claimed_km_bias: float
    home_only_every: int | None = None


EMPLOYEE_SCENARIOS = [
    EmployeeScenario(
        "A001",
        "林北醫",
        "北區醫院業務部",
        "北區醫院業務",
        25.032,
        121.565,
        25.047,
        121.517,
        "north_hospital",
        1.08,
    ),
    EmployeeScenario(
        "B001",
        "陳南院",
        "南區醫院業務部",
        "南區醫院業務",
        22.666,
        120.303,
        22.627,
        120.301,
        "south_hospital",
        1.38,
    ),
    EmployeeScenario(
        "C001",
        "張北診",
        "北區基層通路部",
        "北區診所藥局業務",
        25.015,
        121.463,
        25.047,
        121.517,
        "north_clinic",
        0.96,
        home_only_every=5,
    ),
    EmployeeScenario(
        "D001",
        "吳中區",
        "中區混合通路部",
        "中區混合業務",
        24.162,
        120.647,
        24.151,
        120.646,
        "central_mixed",
        1.18,
    ),
]


def _month_starts(month_count: int, end_month: str = "2026-05") -> list[pd.Timestamp]:
    end = pd.Period(end_month, freq="M")
    start = end - (month_count - 1)
    return [period.to_timestamp() for period in pd.period_range(start, end, freq="M")]


def _demo_workdays(month: pd.Timestamp) -> list[date]:
    days = pd.date_range(month, month + pd.offsets.MonthEnd(0), freq="B")
    return [day.date() for index, day in enumerate(days) if index % 3 == 0]


def _copy_public_hospitals(root_dir: Path, demo_dir: Path) -> pd.DataFrame:
    source_path = root_dir / "hospitals.csv"
    if not source_path.exists():
        raise FileNotFoundError(f"Missing public hospital source: {source_path}")
    hospitals = pd.read_csv(source_path, encoding="utf-8-sig")
    missing = [column for column in HOSPITAL_COLUMNS if column not in hospitals.columns]
    if missing:
        raise ValueError(f"hospitals.csv missing columns: {missing}")
    hospitals = hospitals[HOSPITAL_COLUMNS].copy()
    hospitals.to_csv(demo_dir / "hospitals.csv", index=False, encoding="utf-8-sig")
    return hospitals


def _filter_places(hospitals: pd.DataFrame, city_keywords: Iterable[str], name_keywords: Iterable[str]) -> pd.DataFrame:
    work = hospitals.dropna(subset=["Response_X", "Response_Y"]).copy()
    city_text = work["縣市區名"].fillna("").astype(str) + work["地址"].fillna("").astype(str)
    name_text = work["機構名稱"].fillna("").astype(str) + work["科別"].fillna("").astype(str)
    city_mask = city_text.apply(lambda value: any(keyword in value for keyword in city_keywords))
    name_mask = name_text.apply(lambda value: any(keyword in value for keyword in name_keywords))
    return work.loc[city_mask & name_mask].drop_duplicates(subset=["機構代碼"]).reset_index(drop=True)


def _select_demo_places(hospitals: pd.DataFrame) -> dict[str, pd.DataFrame]:
    place_sets = {
        "north_hospital": _filter_places(hospitals, ["台北", "臺北", "新北", "桃園", "基隆"], ["醫院", "醫療"]),
        "south_hospital": _filter_places(hospitals, ["高雄", "台南", "臺南", "屏東"], ["醫院", "醫療"]),
        "north_clinic": _filter_places(hospitals, ["台北", "臺北", "新北", "桃園", "基隆"], ["診所", "藥局"]),
        "central_mixed": _filter_places(hospitals, ["台中", "臺中", "彰化", "南投"], ["醫院", "診所", "藥局"]),
    }
    fallback = hospitals.dropna(subset=["Response_X", "Response_Y"]).drop_duplicates(subset=["機構代碼"]).reset_index(drop=True)
    for key, places in place_sets.items():
        if len(places) < 6:
            place_sets[key] = fallback.head(12).copy()
        else:
            place_sets[key] = places.head(24).copy()
    return place_sets


def _write_employees(demo_dir: Path) -> pd.DataFrame:
    employees = pd.DataFrame(
        [
            {
                "員工編號": item.employee_id,
                "姓名": item.name,
                "department": item.department,
                "demo_persona": item.persona,
                "Home_Lat": item.home_lat,
                "Home_Lon": item.home_lon,
                "office_lat": item.office_lat,
                "office_lon": item.office_lon,
                "base_commute_km": "",
                "fuel_rate_override": "",
                "maintenance_rate_override": "",
                "job_grade": "P3",
            }
            for item in EMPLOYEE_SCENARIOS
        ]
    )
    employees.to_csv(demo_dir / "employees.csv", index=False, encoding="utf-8-sig")
    return employees


def _format_dt(work_date: date, clock: time) -> str:
    return datetime.combine(work_date, clock).strftime("%Y-%m-%d %H:%M:%S")


def _gps(lat: float, lon: float) -> str:
    return f"{lat:.6f},{lon:.6f}"


def _attendance_row(
    group_no: int,
    employee: EmployeeScenario,
    work_date: date,
    lat: float,
    lon: float,
    planned_time: time,
    actual_offset_min: int,
    card_type: str,
    note: str = "",
) -> dict[str, object]:
    actual_dt = datetime.combine(work_date, planned_time) + timedelta(minutes=actual_offset_min)
    return {
        "#": group_no,
        "員工編號": employee.employee_id,
        "姓名": employee.name,
        "部門": employee.department,
        "工作日期": work_date.isoformat(),
        "打卡地址": _gps(lat, lon),
        "應刷卡時間": _format_dt(work_date, planned_time),
        "實際打卡時間": actual_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "卡別": card_type,
        "比對結果": "符合",
        "異常處理": "已處理",
        "來源": "GPS",
        "備註": note,
        "超時出勤": "否",
        "超時出勤原因": "",
        "超時出勤說明": "",
    }


def _build_attendance_rows(month_count: int, place_sets: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    visit_records: list[dict[str, object]] = []
    group_no = 1
    for month_index, month in enumerate(_month_starts(month_count)):
        for workday_index, work_date in enumerate(_demo_workdays(month)):
            for employee_index, employee in enumerate(EMPLOYEE_SCENARIOS):
                if (workday_index + employee_index) % 2 == 1:
                    continue
                is_home_only = employee.home_only_every and (workday_index + month_index) % employee.home_only_every == 0
                rows.append(
                    _attendance_row(
                        group_no,
                        employee,
                        work_date,
                        employee.home_lat,
                        employee.home_lon,
                        time(8, 50),
                        employee_index * 2,
                        "上班",
                        "住家出發",
                    )
                )
                places = place_sets[employee.region]
                day_places = []
                if is_home_only:
                    day_places = [
                        {
                            "Response_Y": employee.home_lat + 0.001,
                            "Response_X": employee.home_lon + 0.001,
                            "機構代碼": "HOME-AREA",
                            "機構名稱": "住家附近非客戶點",
                        }
                    ]
                else:
                    first_index = (workday_index + month_index + employee_index) % len(places)
                    second_index = (first_index + 5 + employee_index) % len(places)
                    day_places = [places.iloc[first_index].to_dict(), places.iloc[second_index].to_dict()]

                for visit_index, place in enumerate(day_places):
                    visit_time = time(10 + visit_index * 3, 10 + employee_index)
                    rows.append(
                        _attendance_row(
                            group_no,
                            employee,
                            work_date,
                            float(place["Response_Y"]),
                            float(place["Response_X"]),
                            visit_time,
                            4 + visit_index * 3,
                            "外勤",
                            str(place["機構名稱"]),
                        )
                    )
                    if str(place.get("機構代碼")) != "HOME-AREA":
                        visit_records.append(
                            {
                                "employee_id": employee.employee_id,
                                "year_month": month.strftime("%Y-%m"),
                                "hospital_id": str(place["機構代碼"]),
                                "hospital_name": str(place["機構名稱"]),
                            }
                        )

                rows.append(
                    _attendance_row(
                        group_no,
                        employee,
                        work_date,
                        employee.home_lat,
                        employee.home_lon,
                        time(18, 0),
                        -3 + employee_index,
                        "下班",
                        "返家",
                    )
                )
                group_no += 1
    return pd.DataFrame(rows, columns=ATTENDANCE_COLUMNS), pd.DataFrame(visit_records)


def _write_attendance_excel(demo_dir: Path, attendance: pd.DataFrame) -> Path:
    path = demo_dir / "mock_attendance.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        attendance.to_excel(writer, index=False, startrow=5)
    return path


def _write_existing_clients(demo_dir: Path, visit_records: pd.DataFrame) -> pd.DataFrame:
    if visit_records.empty:
        clients = pd.DataFrame(columns=["機構代碼", "機構名稱"])
    else:
        clients = (
            visit_records[["hospital_id", "hospital_name"]]
            .drop_duplicates()
            .head(80)
            .rename(columns={"hospital_id": "機構代碼", "hospital_name": "機構名稱"})
        )
    clients.to_csv(demo_dir / "existing_clients.csv", index=False, encoding="utf-8-sig")
    return clients


def _write_monthly_claims(demo_dir: Path, month_count: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    months = [month.strftime("%Y-%m") for month in _month_starts(month_count)]
    for month_index, year_month in enumerate(months):
        for employee in EMPLOYEE_SCENARIOS:
            base = 180 + month_index * 18
            if employee.employee_id == "B001":
                base += month_index * 26
            if employee.employee_id == "C001":
                base -= month_index * 8
            claimed = round(max(base * employee.claimed_km_bias, 40), 1)
            rows.append(
                {
                    "year_month": year_month,
                    "employee_id": employee.employee_id,
                    "claimed_km": claimed,
                    "claim_source": "demo_mock",
                    "submitted_at": f"{pd.Period(year_month).end_time.date() + timedelta(days=2)} 10:00:00",
                    "remark": f"{employee.persona} demo trend month {month_index + 1}",
                }
            )
    claims = pd.DataFrame(rows)
    claims.to_csv(demo_dir / "monthly_claims.csv", index=False, encoding="utf-8-sig")
    return claims


def generate_mock_data(
    root_dir: str | Path | None = None,
    *,
    run_pipeline_after: bool = True,
    month_count: int = 4,
) -> dict[str, int | str]:
    root = Path(root_dir or project_root).resolve()
    demo_dir = root / "demo_data"
    demo_dir.mkdir(parents=True, exist_ok=True)

    hospitals = _copy_public_hospitals(root, demo_dir)
    place_sets = _select_demo_places(hospitals)
    employees = _write_employees(demo_dir)
    attendance, visit_records = _build_attendance_rows(month_count, place_sets)
    attendance_path = _write_attendance_excel(demo_dir, attendance)
    clients = _write_existing_clients(demo_dir, visit_records)
    claims = _write_monthly_claims(demo_dir, month_count)

    if run_pipeline_after:
        config = build_config(root_dir=demo_dir)
        config.attendance_import_dir.mkdir(parents=True, exist_ok=True)
        imported_path = config.attendance_import_dir / attendance_path.name
        shutil.copy(attendance_path, imported_path)
        run_pipeline(config)

    return {
        "demo_dir": str(demo_dir),
        "month_count": month_count,
        "employee_count": int(len(employees)),
        "hospital_count": int(len(hospitals)),
        "client_count": int(len(clients)),
        "claim_row_count": int(len(claims)),
        "attendance_row_count": int(len(attendance)),
    }


if __name__ == "__main__":
    summary = generate_mock_data()
    print(summary)
