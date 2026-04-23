from __future__ import annotations

import pandas as pd


class BIService:
    def __init__(self, break_minutes: int):
        self.break_minutes = break_minutes

    def build_daily_metrics(
        self,
        attendance: pd.DataFrame,
        routes: pd.DataFrame,
        stop_matches: pd.DataFrame,
    ) -> pd.DataFrame:
        work_df = attendance.copy()
        work_df["first_actual_dt"] = pd.to_datetime(work_df["first_actual_time"], errors="coerce")
        work_df["last_actual_dt"] = pd.to_datetime(work_df["last_actual_time"], errors="coerce")
        span_minutes = (
            (work_df["last_actual_dt"] - work_df["first_actual_dt"]).dt.total_seconds().div(60).fillna(0)
        )
        work_df["raw_span_minutes"] = span_minutes.clip(lower=0)
        work_df["statutory_break_minutes"] = self.break_minutes
        work_df = work_df.merge(
            routes[
                [
                    "attendance_uid",
                    "estimated_travel_min",
                    "estimated_total_km",
                    "matched_stop_count",
                    "total_stop_count",
                ]
            ],
            on="attendance_uid",
            how="left",
        )
        work_df["effective_field_minutes"] = (
            work_df["raw_span_minutes"] - work_df["estimated_travel_min"].fillna(0) - work_df["statutory_break_minutes"]
        ).clip(lower=0)
        work_df["anomaly_flag"] = work_df["compare_result_summary"].fillna("").str.contains(
            "遲到|早退|未打卡|忘刷", regex=True
        )
        work_df["coverage_type"] = work_df["matched_stop_count"].fillna(0).apply(
            lambda count: "no_match" if count == 0 else "matched"
        )
        return work_df[
            [
                "attendance_uid",
                "employee_id",
                "work_date",
                "department",
                "event_count",
                "gps_event_count",
                "raw_span_minutes",
                "statutory_break_minutes",
                "estimated_travel_min",
                "effective_field_minutes",
                "estimated_total_km",
                "matched_stop_count",
                "total_stop_count",
                "anomaly_flag",
                "coverage_type",
                "source_quality_status",
            ]
        ].copy()

    def build_summary(self, daily_metrics: pd.DataFrame, finance: pd.DataFrame) -> dict[str, pd.DataFrame]:
        anomaly_rate = (
            daily_metrics.groupby("employee_id")
            .agg(
                workday_count=("attendance_uid", "count"),
                anomaly_days=("anomaly_flag", "sum"),
                avg_effective_field_minutes=("effective_field_minutes", "mean"),
                avg_total_km=("estimated_total_km", "mean"),
            )
            .reset_index()
        )
        anomaly_rate["anomaly_rate"] = anomaly_rate["anomaly_days"] / anomaly_rate["workday_count"]

        daily_trend = (
            daily_metrics.groupby("work_date")
            .agg(
                gps_points=("gps_event_count", "sum"),
                estimated_total_km=("estimated_total_km", "sum"),
                effective_field_minutes=("effective_field_minutes", "sum"),
                attendance_days=("attendance_uid", "count"),
            )
            .reset_index()
        )

        finance_summary = (
            finance.groupby("audit_light")
            .agg(
                attendance_days=("attendance_uid", "count"),
                total_approved_km=("approved_business_km", "sum"),
                total_fuel_subsidy=("fuel_subsidy", "sum"),
                total_maintenance_subsidy=("maintenance_subsidy", "sum"),
            )
            .reset_index()
        )
        return {
            "employee_summary": anomaly_rate,
            "daily_trend": daily_trend,
            "finance_summary": finance_summary,
        }
