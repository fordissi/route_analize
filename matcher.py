from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


NOW_FMT = "%Y-%m-%d %H:%M:%S"
EARTH_RADIUS_M = 6_371_000


def _now_text() -> str:
    return datetime.now().strftime(NOW_FMT)


def haversine_meter(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return float(2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a)))


class Matcher:
    def __init__(
        self,
        top_n: int = 5,
        hospital_keywords: tuple[str, ...] | list[str] | None = None,
        hospital_exclude_keywords: tuple[str, ...] | list[str] | None = None,
        hospital_priority_distance_m: float = 1000.0,
    ):
        self.top_n = top_n
        self.hospital_keywords = tuple(hospital_keywords or ("醫院", "衛生所", "療養院"))
        self.hospital_exclude_keywords = tuple(hospital_exclude_keywords or ("診所", "藥局"))
        self.hospital_priority_distance_m = float(hospital_priority_distance_m)

    def _is_hospital_facility(self, name: str) -> bool:
        text = str(name or "").strip()
        if not text:
            return False
        return any(keyword in text for keyword in self.hospital_keywords) and not any(
            keyword in text for keyword in self.hospital_exclude_keywords
        )

    def build_matches(
        self,
        raw_events: pd.DataFrame,
        attendance: pd.DataFrame,
        hospital_clean: pd.DataFrame,
        client_master: pd.DataFrame,
    ) -> pd.DataFrame:
        gps_events = raw_events.dropna(subset=["gps_lat", "gps_lon"]).copy()
        if gps_events.empty or hospital_clean.empty:
            return pd.DataFrame(
                columns=[
                    "stop_match_uid",
                    "event_uid",
                    "attendance_uid",
                    "seq_no",
                    "candidate_rank",
                    "hospital_id",
                    "beeline_meter",
                    "match_score",
                    "is_existing_client",
                    "is_selected",
                    "selected_by",
                    "created_at",
                ]
            )

        if "attendance_uid" not in gps_events.columns:
            attendance_key = attendance[["attendance_uid", "employee_id", "work_date", "group_no"]].copy()
            gps_events = gps_events.merge(
                attendance_key,
                on=["employee_id", "work_date", "group_no"],
                how="left",
            )
        gps_events = gps_events.sort_values(["attendance_uid", "actual_time", "source_row_no"]).copy()
        gps_events["seq_no"] = gps_events.groupby("attendance_uid").cumcount() + 1

        hospital_points = hospital_clean.dropna(subset=["lat", "lon"]).reset_index(drop=True).copy()
        tree = cKDTree(hospital_points[["lat", "lon"]].to_numpy())
        client_ids = set(client_master["hospital_id"].dropna().astype(str))

        rows: list[dict] = []
        for _, event in gps_events.iterrows():
            selection_k = min(max(self.top_n, 50), len(hospital_points))
            _, indices = tree.query(
                [event["gps_lat"], event["gps_lon"]],
                k=selection_k,
            )
            indices = np.atleast_1d(indices)
            candidates = hospital_points.iloc[indices].copy().reset_index(drop=True)
            candidates["candidate_rank"] = candidates.index + 1
            candidates["beeline_meter"] = candidates.apply(
                lambda row: haversine_meter(
                    event["gps_lat"], event["gps_lon"], row["lat"], row["lon"]
                ),
                axis=1,
            )
            candidates["is_existing_client"] = candidates["hospital_id"].astype(str).isin(client_ids).astype(int)
            candidates["is_hospital_facility"] = candidates["hospital_name"].apply(self._is_hospital_facility).astype(int)
            candidates["match_score"] = candidates.apply(
                lambda row: (1000.0 / (1000.0 + row["beeline_meter"])) + (0.15 if row["is_existing_client"] else 0.0),
                axis=1,
            )
            candidates["selection_priority"] = candidates.apply(
                lambda row: 0
                if row["is_existing_client"]
                else 1
                if row["is_hospital_facility"] and row["beeline_meter"] <= self.hospital_priority_distance_m
                else 2,
                axis=1,
            )
            candidates["selection_type"] = candidates["selection_priority"].map(
                {0: "既有客戶", 1: "醫院", 2: "潛在院所"}
            )
            best_rank = int(
                candidates.sort_values(
                    ["selection_priority", "beeline_meter", "match_score", "candidate_rank"],
                    ascending=[True, True, False, True],
                ).iloc[0]["candidate_rank"]
            )
            for _, candidate in candidates.iterrows():
                rows.append(
                    {
                        "stop_match_uid": f"{event['event_uid']}_{int(candidate['candidate_rank'])}",
                        "event_uid": event["event_uid"],
                        "attendance_uid": event["attendance_uid"],
                        "seq_no": int(event["seq_no"]),
                        "candidate_rank": int(candidate["candidate_rank"]),
                        "hospital_id": candidate["hospital_id"],
                        "beeline_meter": round(float(candidate["beeline_meter"]), 2),
                        "match_score": round(float(candidate["match_score"]), 4),
                        "is_existing_client": int(candidate["is_existing_client"]),
                        "is_hospital_facility": int(candidate["is_hospital_facility"]),
                        "selection_type": candidate["selection_type"],
                        "is_selected": 1 if int(candidate["candidate_rank"]) == best_rank else 0,
                        "selected_by": "system",
                        "created_at": _now_text(),
                    }
                )
        return pd.DataFrame(rows)
