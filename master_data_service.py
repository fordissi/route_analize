from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


NOW_FMT = "%Y-%m-%d %H:%M:%S"


def _now_text() -> str:
    return datetime.now().strftime(NOW_FMT)


class MasterDataService:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir)

    def load_employees(self, file_name: str = "employees.csv") -> pd.DataFrame:
        path = self.root_dir / file_name
        df = pd.read_csv(path, dtype={"員工編號": "string"}, encoding="utf-8-sig")
        alias_map = {
            "fuel_rate_override": ["fuel_rate_override", "Fuel_Rate", "油資費率", "油費單價"],
            "maintenance_rate_override": ["maintenance_rate_override", "Maintenance_Rate", "維修費率", "維修單價"],
            "job_grade": ["job_grade", "Job_Grade", "職等"],
        }
        for target, aliases in alias_map.items():
            existing = next((column for column in aliases if column in df.columns), None)
            if existing and existing != target:
                df[target] = df[existing]
            elif target not in df.columns:
                df[target] = pd.NA
        for column in ["office_lon", "office_lat", "base_commute_km", "department_default"]:
            if column not in df.columns:
                df[column] = pd.NA
        df["base_commute_rule"] = df["base_commute_km"].apply(
            lambda value: "fixed_km" if pd.notna(value) else "none"
        )
        df["is_active"] = 1
        df["updated_at"] = _now_text()
        df = df.rename(
            columns={
                "員工編號": "employee_id",
                "姓名": "employee_name",
                "Home_Lon": "home_lon",
                "Home_Lat": "home_lat",
            }
        )
        columns = [
            "employee_id",
            "employee_name",
            "home_lon",
            "home_lat",
            "office_lon",
            "office_lat",
            "base_commute_km",
            "base_commute_rule",
            "fuel_rate_override",
            "maintenance_rate_override",
            "job_grade",
            "department_default",
            "is_active",
            "updated_at",
        ]
        return df[columns].copy()

    def load_clients(self, file_name: str = "existing_clients.csv") -> pd.DataFrame:
        path = self.root_dir / file_name
        df = pd.read_csv(path, dtype={"機構代碼": "string"}, encoding="utf-8-sig")
        grouped = (
            df.groupby("機構代碼")["機構名稱"]
            .agg(lambda values: sorted({str(value).strip() for value in values if pd.notna(value)}))
            .reset_index()
        )
        grouped["client_name"] = grouped["機構名稱"].apply(lambda values: values[0] if values else pd.NA)
        grouped["source_status"] = grouped["機構名稱"].apply(
            lambda values: "conflict" if len(values) > 1 else "clean"
        )
        grouped["client_status"] = "existing"
        grouped["updated_at"] = _now_text()
        grouped = grouped.rename(columns={"機構代碼": "hospital_id"})
        return grouped[
            ["hospital_id", "client_name", "client_status", "source_status", "updated_at"]
        ].copy()

    def load_hospitals(self, file_name: str = "hospitals.csv") -> tuple[pd.DataFrame, pd.DataFrame]:
        path = self.root_dir / file_name
        df = pd.read_csv(path, dtype={"機構代碼": "string"}, encoding="utf-8-sig")
        df = df.drop(columns=[column for column in df.columns if str(column).startswith("Unnamed:")], errors="ignore")
        df["科別"] = df["科別"].astype("string").str.strip(", ").replace({"<NA>": pd.NA})
        df["source_status"] = "raw"
        df["updated_at"] = _now_text()

        raw_df = df.rename(
            columns={
                "機構代碼": "hospital_id",
                "機構名稱": "hospital_name",
                "電話": "phone",
                "縣市區名": "city_district",
                "地址": "address",
                "科別": "specialty",
                "Response_Address": "response_address",
                "Response_X": "lon",
                "Response_Y": "lat",
            }
        )[
            [
                "hospital_id",
                "hospital_name",
                "phone",
                "city_district",
                "address",
                "specialty",
                "response_address",
                "lon",
                "lat",
                "source_status",
                "updated_at",
            ]
        ].copy()

        dedup = raw_df.drop_duplicates(
            subset=["hospital_id", "hospital_name", "address", "lon", "lat"], keep="first"
        ).copy()
        name_counts = dedup.groupby("hospital_id")["hospital_name"].nunique().rename("name_count")
        dedup = dedup.merge(name_counts, on="hospital_id", how="left")
        dedup["normalized_address"] = dedup["response_address"].fillna(dedup["address"]).astype("string").str.strip()
        dedup["source_status"] = dedup["name_count"].apply(lambda count: "conflict" if count > 1 else "clean")
        clean_df = (
            dedup.sort_values(["hospital_id", "source_status", "hospital_name"])
            .drop_duplicates(subset=["hospital_id"], keep="first")
            .drop(columns=["phone", "response_address", "name_count"])
        )
        clean_df = clean_df[
            [
                "hospital_id",
                "hospital_name",
                "address",
                "normalized_address",
                "specialty",
                "lon",
                "lat",
                "city_district",
                "source_status",
                "updated_at",
            ]
        ].copy()
        return raw_df, clean_df
