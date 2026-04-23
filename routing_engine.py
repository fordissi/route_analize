from __future__ import annotations

from datetime import datetime

import pandas as pd

from matcher import haversine_meter


NOW_FMT = "%Y-%m-%d %H:%M:%S"


def _now_text() -> str:
    return datetime.now().strftime(NOW_FMT)


class RoutingEngine:
    def __init__(self, detour_index: float, average_speed_kmph: float, route_mode: str):
        self.detour_index = detour_index
        self.average_speed_kmph = average_speed_kmph
        self.route_mode = route_mode

    def summarize_routes(
        self,
        raw_events: pd.DataFrame,
        attendance: pd.DataFrame,
        employees: pd.DataFrame,
        stop_matches: pd.DataFrame,
    ) -> pd.DataFrame:
        gps_events = raw_events.dropna(subset=["gps_lat", "gps_lon"]).copy()
        if gps_events.empty:
            return self._empty_routes(attendance)

        if "attendance_uid" not in gps_events.columns:
            attendance_key = attendance[["attendance_uid", "employee_id", "work_date", "group_no"]]
            gps_events = gps_events.merge(attendance_key, on=["employee_id", "work_date", "group_no"], how="left")
        gps_events["actual_time"] = pd.to_datetime(gps_events["actual_time"], errors="coerce")
        gps_events = gps_events.sort_values(["attendance_uid", "actual_time", "source_row_no"]).copy()
        selected_matches = stop_matches.loc[stop_matches["is_selected"] == 1, ["event_uid", "hospital_id"]].copy()
        gps_events = gps_events.merge(selected_matches, on="event_uid", how="left")
        employee_lookup = employees.set_index("employee_id")
        match_counts = (
            selected_matches.merge(gps_events[["attendance_uid", "event_uid"]], on="event_uid", how="left")
            .groupby("attendance_uid")["hospital_id"]
            .nunique()
            .rename("matched_stop_count")
        )

        rows: list[dict] = []
        gps_group_map = {uid: group.copy() for uid, group in gps_events.groupby("attendance_uid", dropna=False)}
        for _, attendance_row in attendance.iterrows():
            attendance_uid = attendance_row["attendance_uid"]
            if attendance_uid not in gps_group_map:
                rows.append(
                    {
                        "attendance_uid": attendance_uid,
                        "route_mode": self.route_mode,
                        "route_start_type": "unknown",
                        "route_end_type": "unknown",
                        "total_stop_count": 0,
                        "matched_stop_count": 0,
                        "estimated_total_km": 0.0,
                        "estimated_business_km": 0.0,
                        "estimated_travel_min": 0.0,
                        "route_confidence": 0.0,
                        "route_notes": "no gps events",
                        "rule_version": "v1_offline",
                        "calculated_at": _now_text(),
                    }
                )
                continue
            group = gps_group_map[attendance_uid]
            employee_id = attendance_row["employee_id"]
            employee = employee_lookup.loc[employee_id] if employee_id in employee_lookup.index else None
            total_km, route_start_type, route_end_type, route_notes = self._estimate_total_km(group, employee)
            matched_stop_count = int(match_counts.get(attendance_uid, 0))
            total_stop_count = int(group["event_uid"].nunique())
            base_commute = float(employee["base_commute_km"]) if employee is not None and pd.notna(employee["base_commute_km"]) else 0.0
            deduction_km = base_commute * 2 if base_commute else 0.0
            business_km = max(total_km - deduction_km, 0.0)
            travel_min = (total_km / self.average_speed_kmph) * 60 if self.average_speed_kmph else 0.0
            confidence = self._confidence(total_stop_count, matched_stop_count)
            rows.append(
                {
                    "attendance_uid": attendance_uid,
                    "route_mode": self.route_mode,
                    "route_start_type": route_start_type,
                    "route_end_type": route_end_type,
                    "total_stop_count": total_stop_count,
                    "matched_stop_count": matched_stop_count,
                    "estimated_total_km": round(total_km, 2),
                    "estimated_business_km": round(business_km, 2),
                    "estimated_travel_min": round(travel_min, 2),
                    "route_confidence": round(confidence, 3),
                    "route_notes": route_notes,
                    "rule_version": "v1_offline",
                    "calculated_at": _now_text(),
                }
            )
        return pd.DataFrame(rows)

    def _empty_routes(self, attendance: pd.DataFrame) -> pd.DataFrame:
        return attendance.assign(
            route_mode=self.route_mode,
            route_start_type="unknown",
            route_end_type="unknown",
            total_stop_count=0,
            matched_stop_count=0,
            estimated_total_km=0.0,
            estimated_business_km=0.0,
            estimated_travel_min=0.0,
            route_confidence=0.0,
            route_notes="no gps events",
            rule_version="v1_offline",
            calculated_at=_now_text(),
        )[
            [
                "attendance_uid",
                "route_mode",
                "route_start_type",
                "route_end_type",
                "total_stop_count",
                "matched_stop_count",
                "estimated_total_km",
                "estimated_business_km",
                "estimated_travel_min",
                "route_confidence",
                "route_notes",
                "rule_version",
                "calculated_at",
            ]
        ]

    def _estimate_total_km(self, group: pd.DataFrame, employee: pd.Series | None) -> tuple[float, str, str, str]:
        points = list(group[["gps_lat", "gps_lon"]].itertuples(index=False, name=None))
        total_meter = 0.0
        for first, second in zip(points, points[1:]):
            total_meter += haversine_meter(first[0], first[1], second[0], second[1]) * self.detour_index

        route_start_type = "first_last_gps_only"
        route_end_type = "first_last_gps_only"
        route_notes = "gps_sequence_only"

        if employee is not None and pd.notna(employee.get("home_lat")) and pd.notna(employee.get("home_lon")):
            first_lat, first_lon = points[0]
            last_lat, last_lon = points[-1]
            home_lat = float(employee["home_lat"])
            home_lon = float(employee["home_lon"])
            if self.route_mode in {"home_based", "hybrid_rule_based"}:
                total_meter += haversine_meter(home_lat, home_lon, first_lat, first_lon) * self.detour_index
                total_meter += haversine_meter(last_lat, last_lon, home_lat, home_lon) * self.detour_index
                route_start_type = "home"
                route_end_type = "home"
                route_notes = "home_anchor"
        return total_meter / 1000.0, route_start_type, route_end_type, route_notes

    @staticmethod
    def _confidence(total_stop_count: int, matched_stop_count: int) -> float:
        if total_stop_count <= 0:
            return 0.0
        return min(1.0, 0.45 + (matched_stop_count / total_stop_count) * 0.55)
