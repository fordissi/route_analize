import pandas as pd

from finance_auditor import FinanceAuditor


def test_monthly_claim_duplicates_are_summed_before_audit() -> None:
    route_summary = pd.DataFrame(
        [
            {
                "attendance_uid": "E001_2026-05-08_1",
                "estimated_business_km": 80.0,
            }
        ]
    )
    employees = pd.DataFrame(
        [
            {
                "employee_id": "E001",
                "base_commute_km": 0.0,
                "fuel_rate_override": pd.NA,
                "maintenance_rate_override": pd.NA,
                "job_grade": "",
            }
        ]
    )
    monthly_claims = pd.DataFrame(
        [
            {"employee_id": "E001", "year_month": "2026-05", "claimed_km": 40.0},
            {"employee_id": "E001", "year_month": "2026-05", "claimed_km": 60.0},
        ]
    )

    result = FinanceAuditor(
        fuel_rate=1.0,
        maintenance_rate=1.0,
        light_green_pct=0.15,
        light_yellow_pct=0.30,
    ).audit(route_summary, employees, monthly_claims=monthly_claims)

    row = result.iloc[0]
    assert row["employee_claim_km"] == 100.0
    assert row["km_variance_pct"] == 0.2
    assert row["audit_light"] == "yellow"
