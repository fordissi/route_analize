from __future__ import annotations

from datetime import datetime

import pandas as pd


NOW_FMT = "%Y-%m-%d %H:%M:%S"


def _now_text() -> str:
    return datetime.now().strftime(NOW_FMT)


class FinanceAuditor:
    def __init__(
        self,
        fuel_rate: float,
        maintenance_rate: float,
        light_green_pct: float,
        light_yellow_pct: float,
    ):
        self.fuel_rate = fuel_rate
        self.maintenance_rate = maintenance_rate
        self.light_green_pct = light_green_pct
        self.light_yellow_pct = light_yellow_pct

    def audit(
        self,
        route_summary: pd.DataFrame,
        employees: pd.DataFrame,
        monthly_claims: pd.DataFrame | None = None,
        attendance_aux: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        work_df = route_summary.copy()
        work_df["employee_id"] = work_df["attendance_uid"].astype("string").str.split("_").str[0]
        work_df["work_date"] = work_df["attendance_uid"].astype("string").str.split("_").str[1]
        work_df["year_month"] = pd.to_datetime(work_df["work_date"], errors="coerce").dt.strftime("%Y-%m")
        employee_base = employees[
            ["employee_id", "base_commute_km", "fuel_rate_override", "maintenance_rate_override", "job_grade"]
        ].copy()
        work_df = work_df.merge(employee_base, on="employee_id", how="left")
        claim_map: dict[tuple[str, str], float] = {}
        if monthly_claims is not None and not monthly_claims.empty:
            monthly_claims = monthly_claims.copy()
            monthly_claims["year_month"] = monthly_claims["year_month"].astype("string")
            monthly_claims["employee_id"] = monthly_claims["employee_id"].astype("string")
            monthly_claims["claimed_km"] = pd.to_numeric(monthly_claims["claimed_km"], errors="coerce")
            claim_map = {
                (row["employee_id"], row["year_month"]): float(row["claimed_km"])
                for _, row in monthly_claims.dropna(subset=["claimed_km"]).iterrows()
            }
        approved_month_map = (
            work_df.groupby(["employee_id", "year_month"])["estimated_business_km"].sum().to_dict()
        )

        aux_map = {}
        if attendance_aux is not None and not attendance_aux.empty:
            aux_map = attendance_aux.set_index("attendance_uid").to_dict("index")

        rows: list[dict] = []
        for _, row in work_df.iterrows():
            employee_id = row["employee_id"]
            claim_key = (employee_id, row["year_month"])
            claim_km = claim_map.get(claim_key)
            approved_month_km = float(approved_month_map.get(claim_key, 0.0))
            base_commute = float(row["base_commute_km"]) if pd.notna(row["base_commute_km"]) else 0.0
            fuel_rate = float(row["fuel_rate_override"]) if pd.notna(row.get("fuel_rate_override")) else self.fuel_rate
            maintenance_rate = (
                float(row["maintenance_rate_override"])
                if pd.notna(row.get("maintenance_rate_override"))
                else self.maintenance_rate
            )
            base_deduction = round(base_commute * 2, 2) if base_commute else 0.0
            approved_km = float(row["estimated_business_km"])
            variance_pct = None
            if claim_km and claim_km > 0:
                variance_pct = abs(claim_km - approved_month_km) / claim_km
            audit_light = self._audit_light(variance_pct)
            attendance_status = aux_map.get(row["attendance_uid"], {}).get("attendance_status", "資料未提供")
            daily_report_submitted = aux_map.get(row["attendance_uid"], {}).get("daily_report_submitted", None)
            meals_provided_count = aux_map.get(row["attendance_uid"], {}).get("meals_provided_count", None)
            per_diem_amount = self._per_diem(attendance_status, daily_report_submitted, meals_provided_count)
            rows.append(
                {
                    "attendance_uid": row["attendance_uid"],
                    "employee_claim_km": claim_km,
                    "base_commute_deduction_km": base_deduction,
                    "approved_business_km": round(approved_km, 2),
                    "km_variance_pct": round(variance_pct, 4) if variance_pct is not None else None,
                    "audit_light": audit_light,
                    "fuel_rate": fuel_rate,
                    "fuel_subsidy": round(approved_km * fuel_rate, 2),
                    "maintenance_base": round(approved_km, 2),
                    "maintenance_rate": maintenance_rate,
                    "maintenance_subsidy": round(approved_km * maintenance_rate, 2),
                    "per_diem_amount": per_diem_amount,
                    "audit_status": "pending" if audit_light in {"yellow", "red", "gray"} else "approved",
                    "reviewer_note": None if per_diem_amount is not None else "需補 attendance_aux.csv 以計算日當費",
                    "rule_version": "finance_v1",
                    "updated_at": _now_text(),
                }
            )
        return pd.DataFrame(rows)

    def _audit_light(self, variance_pct: float | None) -> str:
        if variance_pct is None:
            return "gray"
        if variance_pct <= self.light_green_pct:
            return "green"
        if variance_pct <= self.light_yellow_pct:
            return "yellow"
        return "red"

    @staticmethod
    def _per_diem(
        attendance_status: str | None,
        daily_report_submitted: bool | None,
        meals_provided_count: float | int | None,
    ) -> float | None:
        if attendance_status is None or daily_report_submitted is None or meals_provided_count is None:
            return None
        normalized_status = str(attendance_status).strip().lower()
        meal_count = int(meals_provided_count)
        if normalized_status in {"正常出勤", "normal"}:
            if meal_count >= 2:
                return 0.0
            return 300.0 if daily_report_submitted else 0.0
        if normalized_status in {"半天出勤", "half_day"}:
            if meal_count >= 1:
                return 0.0
            return 150.0
        return 0.0
