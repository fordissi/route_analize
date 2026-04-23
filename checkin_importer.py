from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


GROUP_FILL_COLUMNS = ["#", "員工編號", "姓名", "部門", "工作日期"]
NOW_FMT = "%Y-%m-%d %H:%M:%S"


def _now_text() -> str:
    return datetime.now().strftime(NOW_FMT)


def parse_gps_value(value: object) -> tuple[float | None, float | None]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, None
    text = str(value).strip()
    if not text or "," not in text:
        return None, None
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        return None, None
    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError:
        return None, None
    return lat, lon


class CheckinImporter:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir)

    def load_excel(self, file_name: str) -> tuple[str, pd.DataFrame]:
        path = self.root_dir / file_name
        xls = pd.ExcelFile(path)
        sheet_name = xls.sheet_names[0]
        df = pd.read_excel(path, sheet_name=sheet_name, header=5)
        return sheet_name, df

    def import_events(self, file_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        sheet_name, df = self.load_excel(file_name)
        import_batch_id = Path(file_name).stem

        work_df = df.copy()
        work_df[GROUP_FILL_COLUMNS] = work_df[GROUP_FILL_COLUMNS].ffill()
        work_df["source_row_no"] = work_df.index + 7
        work_df["group_no"] = work_df["#"].astype("Int64").astype("string")
        gps_values = work_df["打卡地址"].apply(parse_gps_value)
        work_df["gps_lat"] = gps_values.apply(lambda value: value[0])
        work_df["gps_lon"] = gps_values.apply(lambda value: value[1])
        work_df["work_date"] = pd.to_datetime(work_df["工作日期"], errors="coerce").dt.strftime("%Y-%m-%d")
        work_df["scheduled_time"] = pd.to_datetime(work_df["應刷卡時間"], errors="coerce")
        work_df["actual_time"] = pd.to_datetime(work_df["實際打卡時間"], errors="coerce")
        work_df["created_at"] = _now_text()
        work_df["event_uid"] = work_df.apply(
            lambda row: f"{import_batch_id}_{sheet_name}_{int(row['source_row_no'])}", axis=1
        )

        raw_events = work_df.rename(
            columns={
                "員工編號": "employee_id",
                "姓名": "employee_name",
                "部門": "department",
                "卡別": "card_type",
                "打卡地址": "gps_raw",
                "比對結果": "compare_result",
                "異常處理": "exception_action",
                "來源": "source_type",
                "備註": "note",
                "超時出勤": "overtime_flag",
                "超時出勤原因": "overtime_reason",
                "超時出勤說明": "overtime_comment",
            }
        )
        raw_events["import_batch_id"] = import_batch_id
        raw_events["source_sheet"] = sheet_name
        raw_events["scheduled_time"] = raw_events["scheduled_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        raw_events["actual_time"] = raw_events["actual_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        raw_events = raw_events[
            [
                "event_uid",
                "import_batch_id",
                "source_sheet",
                "source_row_no",
                "group_no",
                "employee_id",
                "employee_name",
                "department",
                "work_date",
                "scheduled_time",
                "actual_time",
                "card_type",
                "gps_raw",
                "gps_lat",
                "gps_lon",
                "compare_result",
                "exception_action",
                "source_type",
                "note",
                "overtime_flag",
                "overtime_reason",
                "overtime_comment",
                "created_at",
            ]
        ].copy()

        attendance = self._build_attendance_groups(raw_events)
        raw_events = raw_events.merge(
            attendance[["attendance_uid", "import_batch_id", "group_no", "employee_id", "work_date", "department"]],
            on=["import_batch_id", "group_no", "employee_id", "work_date", "department"],
            how="left",
        )
        ordered_columns = ["attendance_uid", *[column for column in raw_events.columns if column != "attendance_uid"]]
        raw_events = raw_events[ordered_columns].copy()
        return raw_events, attendance

    def _build_attendance_groups(self, raw_events: pd.DataFrame) -> pd.DataFrame:
        work_df = raw_events.copy()
        work_df["actual_time_dt"] = pd.to_datetime(work_df["actual_time"], errors="coerce")
        work_df["scheduled_time_dt"] = pd.to_datetime(work_df["scheduled_time"], errors="coerce")

        def summarize_compare(values: pd.Series) -> str | None:
            unique_values = [value for value in pd.unique(values.dropna()) if str(value).strip()]
            if not unique_values:
                return None
            return ",".join(map(str, unique_values))

        grouped = (
            work_df.groupby(["import_batch_id", "group_no", "employee_id", "work_date", "department"], dropna=False)
            .agg(
                event_count=("event_uid", "count"),
                gps_event_count=("gps_lat", lambda values: int(values.notna().sum())),
                first_actual_time=("actual_time_dt", "min"),
                last_actual_time=("actual_time_dt", "max"),
                first_card_time=("scheduled_time_dt", "min"),
                last_card_time=("scheduled_time_dt", "max"),
                compare_result_summary=("compare_result", summarize_compare),
            )
            .reset_index()
        )
        grouped["attendance_uid"] = grouped.apply(
            lambda row: f"{row['employee_id']}_{row['work_date']}_{row['group_no']}_{row['import_batch_id']}",
            axis=1,
        )
        grouped["source_quality_status"] = grouped.apply(
            lambda row: self._quality_status(
                gps_event_count=row["gps_event_count"],
                has_clock=pd.notna(row["first_card_time"]) or pd.notna(row["last_card_time"]),
            ),
            axis=1,
        )
        grouped["created_at"] = _now_text()
        for column in ["first_actual_time", "last_actual_time", "first_card_time", "last_card_time"]:
            grouped[column] = pd.to_datetime(grouped[column], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        return grouped[
            [
                "attendance_uid",
                "import_batch_id",
                "group_no",
                "employee_id",
                "work_date",
                "department",
                "event_count",
                "gps_event_count",
                "first_actual_time",
                "last_actual_time",
                "first_card_time",
                "last_card_time",
                "compare_result_summary",
                "source_quality_status",
                "created_at",
            ]
        ].copy()

    @staticmethod
    def _quality_status(gps_event_count: int, has_clock: bool) -> str:
        if gps_event_count == 0 and not has_clock:
            return "manual_only"
        if gps_event_count == 0:
            return "missing_gps"
        if not has_clock:
            return "missing_clock"
        return "ok"
