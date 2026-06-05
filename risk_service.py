from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from distance_formatting import format_distance
from matcher import haversine_meter


REASON_WEIGHTS = {
    "near_home_checkin": 3,
    "far_customer_override": 5,
    "selected_not_top5": 3,
    "selected_distance_too_far": 4,
    "nearby_candidate_conflict": 2,
    "no_reasonable_candidate": 3,
    "impossible_travel_time": 8,
    "high_finance_variance": 5,
    "home_area_only_trace": 8,
    "home_start_end_without_field_trace": 3,
    "insufficient_route_evidence": 3,
    "insufficient_checkin_count": 5,
    "short_attendance_span": 4,
    "long_attendance_span": 3,
}

CONFIDENCE_REASON_CODES = {
    "far_customer_override",
    "selected_not_top5",
    "nearby_candidate_conflict",
    "no_reasonable_candidate",
    "insufficient_route_evidence",
    "long_attendance_span",
}

DAILY_PRIORITY_WEIGHTS = {
    "near_home_checkin": 3,
    "impossible_travel_time": 16,
    "far_customer_override": 12,
    "selected_distance_too_far": 10,
    "home_area_only_trace": 24,
    "home_start_end_without_field_trace": 6,
    "insufficient_route_evidence": 8,
    "insufficient_checkin_count": 12,
    "short_attendance_span": 10,
    "high_finance_variance": 6,
    "no_reasonable_candidate": 3,
    "selected_not_top5": 3,
    "nearby_candidate_conflict": 1,
}

DAILY_PRIORITY_CAPS = {
    "nearby_candidate_conflict": 1,
    "selected_not_top5": 2,
    "no_reasonable_candidate": 2,
}

HOME_CORE_LABEL = "極近居家點"
HOME_EDGE_LABEL = "邊緣居家點"
EXISTING_CLIENT_LABEL = "既有客戶拜訪點"
UNKNOWN_FIELD_LABEL = "未知出勤點"

NORMAL_LABEL = "正常"
LOW_CONFIDENCE_LABEL = "低信心"
REVIEW_LABEL = "需覆核"
HIGH_RISK_LABEL = "高風險需覆核"

EVENT_RISK_COLUMNS = [
    "event_uid",
    "attendance_uid",
    "risk_level",
    "risk_score",
    "review_score",
    "priority_score",
    "confidence_score",
    "risk_reason_codes",
    "risk_reason_text",
    "location_class",
    "selected_visit_name",
    "selected_visit_type",
    "selected_visit_distance_m",
    "home_distance_bucket",
    "existing_client_candidates_top3",
    "suggested_prospects_top3",
    "nearest_existing_client_name",
    "nearest_existing_client_distance_m",
    "nearest_hospital_name",
    "nearest_hospital_distance_m",
    "selected_distance_m",
    "nearest_distance_m",
    "distance_gap_m",
    "selected_rank",
    "distance_from_home_m",
]

DAILY_RISK_COLUMNS = [
    "attendance_uid",
    "employee_id",
    "employee_name",
    "department",
    "work_date",
    "gps_event_count",
    "attendance_span_minutes",
    "risk_score",
    "review_score",
    "confidence_score",
    "risk_priority_score",
    "risk_priority_rate",
    "risk_rate",
    "review_event_count",
    "high_risk_event_count",
    "low_confidence_event_count",
    "risk_level",
    "home_area_only_trace",
    "home_start_end_without_field_trace",
    "insufficient_route_evidence",
    "insufficient_checkin_count",
    "short_attendance_span",
    "long_attendance_span",
    "home_near_event_count",
    "max_distance_from_home_m",
    "field_visit_count",
    "risk_reason_summary",
]

EMPLOYEE_RISK_COLUMNS = [
    "employee_id",
    "employee_name",
    "department",
    "attendance_days",
    "gps_event_count",
    "risk_score",
    "review_score",
    "confidence_score",
    "risk_priority_score",
    "risk_priority_rate",
    "risk_rate",
    "review_rate",
    "review_event_count",
    "high_risk_event_count",
    "low_confidence_event_count",
    "home_area_only_days",
    "home_start_end_without_field_days",
    "insufficient_route_evidence_days",
    "insufficient_checkin_days",
    "short_attendance_span_days",
    "long_attendance_span_days",
    "risk_level",
]


@dataclass(slots=True)
class RiskService:
    config: object

    def build_event_risk(
        self,
        raw_events: pd.DataFrame,
        matches: pd.DataFrame,
        route_segments: pd.DataFrame,
        finance: pd.DataFrame,
        employees: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if raw_events.empty:
            return pd.DataFrame(columns=EVENT_RISK_COLUMNS)

        events = raw_events.copy()
        if {"gps_lat", "gps_lon"}.issubset(events.columns):
            events = events.dropna(subset=["gps_lat", "gps_lon"])
        if events.empty:
            return pd.DataFrame(columns=EVENT_RISK_COLUMNS)

        events = self._attach_home_distance(events, employees)
        impossible_event_ids = self._impossible_travel_event_ids(raw_events, route_segments)
        rows = []
        for _, event in events.iterrows():
            event_uid = event.get("event_uid")
            if matches.empty or "event_uid" not in matches.columns:
                candidates = pd.DataFrame()
            else:
                candidates = matches[matches["event_uid"] == event_uid].copy()
            rows.append(self._score_event(event, candidates, impossible_event_ids))

        return pd.DataFrame(rows, columns=EVENT_RISK_COLUMNS)

    def build_daily_risk_summary(
        self,
        event_risk: pd.DataFrame,
        attendance: pd.DataFrame,
        raw_events: pd.DataFrame | None = None,
        employees: pd.DataFrame | None = None,
        matches: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if attendance.empty:
            return pd.DataFrame(columns=DAILY_RISK_COLUMNS)

        result = attendance.copy()
        if "gps_event_count" not in result.columns:
            result["gps_event_count"] = 0
        result["gps_event_count"] = pd.to_numeric(result["gps_event_count"], errors="coerce").fillna(0)
        result = self._attach_attendance_rule_risk(result)

        risk = event_risk.copy()
        if risk.empty or "attendance_uid" not in risk.columns:
            grouped = pd.DataFrame(
                columns=[
                    "attendance_uid",
                    "risk_score",
                    "review_score",
                    "confidence_score",
                    "risk_priority_score",
                    "review_event_count",
                    "high_risk_event_count",
                    "low_confidence_event_count",
                    "risk_reason_summary",
                ]
            )
        else:
            if "risk_score" not in risk.columns:
                risk["risk_score"] = 0
            if "review_score" not in risk.columns:
                risk["review_score"] = 0
            if "priority_score" not in risk.columns:
                risk["priority_score"] = pd.to_numeric(risk["risk_score"], errors="coerce").fillna(0) * 3 + pd.to_numeric(
                    risk["review_score"], errors="coerce"
                ).fillna(0)
            if "confidence_score" not in risk.columns:
                risk["confidence_score"] = risk.get("risk_reason_codes", pd.Series("", index=risk.index)).apply(
                    self._confidence_score_from_codes
                )
            if "risk_level" not in risk.columns:
                risk["risk_level"] = ""
            if "risk_reason_codes" not in risk.columns:
                risk["risk_reason_codes"] = ""
            risk["risk_score"] = pd.to_numeric(risk["risk_score"], errors="coerce").fillna(0)
            risk["review_score"] = pd.to_numeric(risk["review_score"], errors="coerce").fillna(0)
            risk["priority_score"] = pd.to_numeric(risk["priority_score"], errors="coerce").fillna(0)
            risk["confidence_score"] = pd.to_numeric(risk["confidence_score"], errors="coerce").fillna(0)
            risk["review_event"] = risk["risk_level"].isin(self._review_levels())
            risk["high_risk_event"] = risk["risk_level"].isin(self._high_risk_levels())
            risk["low_confidence_event"] = risk["risk_level"].eq(LOW_CONFIDENCE_LABEL)
            grouped = (
                risk.groupby("attendance_uid", dropna=False)
                .agg(
                    risk_score=("risk_score", "sum"),
                    review_score=("review_score", "sum"),
                    confidence_score=("confidence_score", "sum"),
                    risk_priority_score=("priority_score", "sum"),
                    review_event_count=("review_event", "sum"),
                    high_risk_event_count=("high_risk_event", "sum"),
                    low_confidence_event_count=("low_confidence_event", "sum"),
                    risk_reason_summary=("risk_reason_codes", self._join_reason_codes),
                )
                .reset_index()
            )

        result = result.merge(grouped, on="attendance_uid", how="left")
        for column in [
            "risk_score",
            "review_score",
            "confidence_score",
            "risk_priority_score",
            "review_event_count",
            "high_risk_event_count",
            "low_confidence_event_count",
        ]:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)
        result["review_event_count"] = result["review_event_count"].astype(int)
        result["high_risk_event_count"] = result["high_risk_event_count"].astype(int)
        result["low_confidence_event_count"] = result["low_confidence_event_count"].astype(int)
        result["risk_reason_summary"] = result["risk_reason_summary"].fillna("")

        home_trace = self._build_home_trace_risk(result, raw_events, employees, matches)
        result = result.merge(home_trace, on="attendance_uid", how="left")
        for column in [
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
            "insufficient_checkin_count",
            "short_attendance_span",
            "long_attendance_span",
            "home_near_event_count",
            "field_visit_count",
        ]:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
        result["max_distance_from_home_m"] = pd.to_numeric(result["max_distance_from_home_m"], errors="coerce").fillna(0.0)

        result["risk_score"] = result["risk_score"] + (
            result["home_area_only_trace"] * REASON_WEIGHTS["home_area_only_trace"]
            + result["home_start_end_without_field_trace"] * REASON_WEIGHTS["home_start_end_without_field_trace"]
            + pd.to_numeric(result.get("insufficient_checkin_risk_score", 0), errors="coerce").fillna(0)
            + result["short_attendance_span"] * REASON_WEIGHTS["short_attendance_span"]
        )
        result["review_score"] = result["review_score"] + (
            pd.to_numeric(result.get("insufficient_checkin_review_score", 0), errors="coerce").fillna(0)
            + result["short_attendance_span"] * 5
            + result["long_attendance_span"] * 5
        )
        result["confidence_score"] = result["confidence_score"] + (
            result["insufficient_route_evidence"] * REASON_WEIGHTS["insufficient_route_evidence"]
            + result["long_attendance_span"] * REASON_WEIGHTS["long_attendance_span"]
        )
        result["risk_priority_score"] = (result["risk_score"] * 3) + result["review_score"]
        result["risk_reason_summary"] = result.apply(self._merge_daily_reason_summary, axis=1)
        result["risk_priority_rate"] = result["risk_priority_score"] / result["gps_event_count"].clip(lower=1)
        result["risk_rate"] = result["risk_score"] / result["gps_event_count"].clip(lower=1)
        result["risk_level"] = result.apply(self._daily_level, axis=1)
        return result.reindex(columns=DAILY_RISK_COLUMNS)

    def build_employee_risk_summary(self, daily_risk: pd.DataFrame) -> pd.DataFrame:
        if daily_risk.empty:
            return pd.DataFrame(columns=EMPLOYEE_RISK_COLUMNS)

        daily = daily_risk.copy()
        for column in [
            "gps_event_count",
            "risk_score",
            "review_score",
            "confidence_score",
            "risk_priority_score",
            "review_event_count",
            "high_risk_event_count",
            "low_confidence_event_count",
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
            "insufficient_checkin_count",
            "short_attendance_span",
            "long_attendance_span",
        ]:
            if column not in daily.columns:
                daily[column] = 0
            daily[column] = pd.to_numeric(daily[column], errors="coerce").fillna(0)
        for column in ["employee_id", "employee_name", "department"]:
            if column not in daily.columns:
                daily[column] = ""

        grouped = (
            daily.groupby(["employee_id", "employee_name", "department"], dropna=False)
            .agg(
                attendance_days=("attendance_uid", "count"),
                gps_event_count=("gps_event_count", "sum"),
                risk_score=("risk_score", "sum"),
                review_score=("review_score", "sum"),
                confidence_score=("confidence_score", "sum"),
                risk_priority_score=("risk_priority_score", "sum"),
                review_event_count=("review_event_count", "sum"),
                high_risk_event_count=("high_risk_event_count", "sum"),
                low_confidence_event_count=("low_confidence_event_count", "sum"),
                home_area_only_days=("home_area_only_trace", "sum"),
                home_start_end_without_field_days=("home_start_end_without_field_trace", "sum"),
                insufficient_route_evidence_days=("insufficient_route_evidence", "sum"),
                insufficient_checkin_days=("insufficient_checkin_count", "sum"),
                short_attendance_span_days=("short_attendance_span", "sum"),
                long_attendance_span_days=("long_attendance_span", "sum"),
            )
            .reset_index()
        )
        grouped["risk_rate"] = grouped["risk_score"] / grouped["gps_event_count"].clip(lower=1)
        grouped["risk_priority_rate"] = grouped["risk_priority_score"] / grouped["attendance_days"].clip(lower=1)
        grouped["review_rate"] = grouped["review_event_count"] / grouped["gps_event_count"].clip(lower=1)
        grouped["risk_level"] = grouped.apply(self._employee_level, axis=1)
        return grouped.reindex(columns=EMPLOYEE_RISK_COLUMNS).sort_values(
            ["risk_priority_rate", "risk_priority_score", "risk_rate"], ascending=[False, False, False]
        )

    def _attach_attendance_rule_risk(self, attendance: pd.DataFrame) -> pd.DataFrame:
        result = attendance.copy()
        index = result.index
        event_count = (
            pd.to_numeric(result["event_count"], errors="coerce")
            if "event_count" in result.columns
            else pd.Series(pd.NA, index=index, dtype="Float64")
        )
        first_actual = (
            pd.to_datetime(result["first_actual_time"], errors="coerce")
            if "first_actual_time" in result.columns
            else pd.Series(pd.NaT, index=index)
        )
        last_actual = (
            pd.to_datetime(result["last_actual_time"], errors="coerce")
            if "last_actual_time" in result.columns
            else pd.Series(pd.NaT, index=index)
        )
        span_minutes = (last_actual - first_actual).dt.total_seconds().div(60)
        valid_span = span_minutes.notna() & span_minutes.ge(0)
        min_count = int(getattr(self.config, "risk_min_checkin_count", 2))
        min_span_minutes = float(getattr(self.config, "risk_min_attendance_span_hours", 6.0)) * 60
        max_span_minutes = float(getattr(self.config, "risk_max_attendance_span_hours", 14.0)) * 60
        sufficient_count = event_count.ge(min_count).fillna(False)

        result["attendance_span_minutes"] = span_minutes.where(valid_span, 0).fillna(0).round(0)
        missing_count = event_count.notna() & event_count.lt(min_count)
        zero_count = missing_count & event_count.eq(0)
        one_count = missing_count & event_count.eq(1)
        result["insufficient_checkin_count"] = missing_count.astype(int)
        result["insufficient_checkin_risk_score"] = (zero_count.astype(int) * 10) + (one_count.astype(int) * 5)
        result["insufficient_checkin_review_score"] = (zero_count.astype(int) * 10) + (one_count.astype(int) * 12)
        result["short_attendance_span"] = (valid_span & sufficient_count & span_minutes.lt(min_span_minutes)).astype(int)
        result["long_attendance_span"] = (valid_span & sufficient_count & span_minutes.gt(max_span_minutes)).astype(int)
        return result

    def _build_home_trace_risk(
        self,
        attendance: pd.DataFrame,
        raw_events: pd.DataFrame | None,
        employees: pd.DataFrame | None,
        matches: pd.DataFrame | None,
    ) -> pd.DataFrame:
        columns = [
            "attendance_uid",
            "home_near_event_count",
            "max_distance_from_home_m",
            "field_visit_count",
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
        ]
        if raw_events is None or employees is None or raw_events.empty or employees.empty:
            return pd.DataFrame(columns=columns)
        if not {"attendance_uid", "employee_id"}.issubset(attendance.columns):
            return pd.DataFrame(columns=columns)
        if not {"event_uid", "attendance_uid", "gps_lat", "gps_lon"}.issubset(raw_events.columns):
            return pd.DataFrame(columns=columns)
        if not {"employee_id", "home_lat", "home_lon"}.issubset(employees.columns):
            return pd.DataFrame(columns=columns)

        employee_home = (
            employees.dropna(subset=["home_lat", "home_lon"])[["employee_id", "home_lat", "home_lon"]]
            .drop_duplicates(subset=["employee_id"], keep="first")
            .copy()
        )
        if employee_home.empty:
            return pd.DataFrame(columns=columns)

        events = raw_events.dropna(subset=["gps_lat", "gps_lon"]).copy()
        if "employee_id" not in events.columns:
            events = events.merge(attendance[["attendance_uid", "employee_id"]], on="attendance_uid", how="left")
        events = events.merge(employee_home, on="employee_id", how="left").dropna(subset=["home_lat", "home_lon"])
        if events.empty:
            return pd.DataFrame(columns=columns)

        events["distance_from_home_m"] = events.apply(
            lambda row: haversine_meter(row["gps_lat"], row["gps_lon"], row["home_lat"], row["home_lon"]),
            axis=1,
        )
        events["near_home"] = events["distance_from_home_m"] <= float(self.config.risk_home_radius_m)

        match_evidence = pd.DataFrame(columns=["event_uid", "field_visit_evidence"])
        if matches is not None and not matches.empty and {"event_uid", "beeline_meter"}.issubset(matches.columns):
            evidence = matches.copy()
            evidence["beeline_meter"] = pd.to_numeric(evidence["beeline_meter"], errors="coerce")
            selected_evidence = (
                self._as_bool_series(evidence["is_selected"])
                if "is_selected" in evidence.columns
                else pd.Series(False, index=evidence.index)
            )
            rank_evidence = (
                pd.to_numeric(evidence["candidate_rank"], errors="coerce").eq(1)
                if "candidate_rank" in evidence.columns
                else pd.Series(False, index=evidence.index)
            )
            match_evidence = evidence.loc[
                evidence["beeline_meter"].le(float(self.config.risk_review_distance_m))
                & (selected_evidence | rank_evidence),
                ["event_uid"],
            ].drop_duplicates()
            match_evidence["field_visit_evidence"] = 1
        events = events.merge(match_evidence, on="event_uid", how="left")
        events["field_visit_evidence"] = pd.to_numeric(events["field_visit_evidence"], errors="coerce").fillna(0).astype(int)
        events.loc[events["near_home"], "field_visit_evidence"] = 0

        sort_columns = ["attendance_uid"]
        if "actual_time" in events.columns:
            events["actual_dt"] = pd.to_datetime(events["actual_time"], errors="coerce")
            sort_columns.append("actual_dt")
        grouped = (
            events.sort_values(sort_columns, na_position="last")
            .groupby("attendance_uid", dropna=False)
            .agg(
                gps_points=("event_uid", "count"),
                home_near_event_count=("near_home", "sum"),
                max_distance_from_home_m=("distance_from_home_m", "max"),
                first_near_home=("near_home", "first"),
                last_near_home=("near_home", "last"),
                field_visit_count=("field_visit_evidence", "sum"),
            )
            .reset_index()
        )
        grouped["home_area_only_trace"] = (
            (grouped["gps_points"] >= 2)
            & (grouped["home_near_event_count"] == grouped["gps_points"])
            & (grouped["field_visit_count"] == 0)
        ).astype(int)
        grouped["home_start_end_without_field_trace"] = (
            (grouped["home_area_only_trace"] == 0)
            & (grouped["gps_points"] > 2)
            & grouped["first_near_home"]
            & grouped["last_near_home"]
            & (grouped["field_visit_count"] == 0)
        ).astype(int)
        grouped["insufficient_route_evidence"] = (
            (grouped["gps_points"] < 2)
            | (
                (grouped["max_distance_from_home_m"] < float(self.config.risk_min_field_visit_distance_from_home_m))
                & (grouped["field_visit_count"] == 0)
                & (grouped["home_area_only_trace"] == 0)
            )
        ).astype(int)
        return grouped[columns]

    @staticmethod
    def _join_reason_codes(values: pd.Series) -> str:
        reasons: set[str] = set()
        for value in values.dropna().astype(str):
            reasons.update(code for code in value.split(",") if code)
        return ",".join(sorted(reasons))

    @staticmethod
    def _daily_event_priority_score(values: pd.Series) -> float:
        reason_counts: dict[str, int] = {}
        for value in values.dropna().astype(str):
            for code in [code for code in value.split(",") if code]:
                reason_counts[code] = reason_counts.get(code, 0) + 1
        score = 0.0
        for code, count in reason_counts.items():
            if code in CONFIDENCE_REASON_CODES:
                continue
            capped_count = min(count, DAILY_PRIORITY_CAPS.get(code, count))
            score += DAILY_PRIORITY_WEIGHTS.get(code, REASON_WEIGHTS.get(code, 0)) * capped_count
        return score

    @staticmethod
    def _confidence_score_from_codes(value: Any) -> float:
        return float(
            sum(
                REASON_WEIGHTS.get(code, 0)
                for code in str(value or "").split(",")
                if code in CONFIDENCE_REASON_CODES
            )
        )

    def _merge_daily_reason_summary(self, row: pd.Series) -> str:
        reasons = set(str(row.get("risk_reason_summary", "") or "").split(",")) - {""}
        if row.get("home_area_only_trace", 0):
            reasons.add("home_area_only_trace")
        if row.get("home_start_end_without_field_trace", 0):
            reasons.add("home_start_end_without_field_trace")
        if row.get("insufficient_route_evidence", 0):
            reasons.add("insufficient_route_evidence")
        if row.get("insufficient_checkin_count", 0):
            reasons.add("insufficient_checkin_count")
        if row.get("short_attendance_span", 0):
            reasons.add("short_attendance_span")
        if row.get("long_attendance_span", 0):
            reasons.add("long_attendance_span")
        return ",".join(sorted(reasons))

    def _attach_home_distance(self, events: pd.DataFrame, employees: pd.DataFrame | None) -> pd.DataFrame:
        events = events.copy()
        events["distance_from_home_m"] = None
        if employees is None or employees.empty:
            return events
        if not {"employee_id", "home_lat", "home_lon"}.issubset(employees.columns):
            return events
        if not {"employee_id", "gps_lat", "gps_lon"}.issubset(events.columns):
            return events

        employee_home = (
            employees.dropna(subset=["home_lat", "home_lon"])[["employee_id", "home_lat", "home_lon"]]
            .drop_duplicates(subset=["employee_id"], keep="first")
            .copy()
        )
        if employee_home.empty:
            return events

        with_home = events.merge(employee_home, on="employee_id", how="left")
        with_home["distance_from_home_m"] = with_home.apply(
            lambda row: (
                haversine_meter(row["gps_lat"], row["gps_lon"], row["home_lat"], row["home_lon"])
                if pd.notna(row.get("gps_lat"))
                and pd.notna(row.get("gps_lon"))
                and pd.notna(row.get("home_lat"))
                and pd.notna(row.get("home_lon"))
                else None
            ),
            axis=1,
        )
        return with_home.drop(columns=["home_lat", "home_lon"], errors="ignore")

    def _daily_level(self, row: pd.Series) -> str:
        priority = float(row.get("risk_priority_score", 0) or 0)
        if row["high_risk_event_count"] > 0 or row.get("home_area_only_trace", 0) or priority >= 20:
            return HIGH_RISK_LABEL
        if row["review_event_count"] > 0 or row.get("home_start_end_without_field_trace", 0) or priority >= 8:
            return REVIEW_LABEL
        if row["risk_score"] > 0 or priority > 0:
            return REVIEW_LABEL
        if row.get("confidence_score", 0) > 0 or row["low_confidence_event_count"] > 0:
            return LOW_CONFIDENCE_LABEL
        return NORMAL_LABEL

    def _employee_level(self, row: pd.Series) -> str:
        priority_rate = float(row.get("risk_priority_rate", 0) or 0)
        if row["high_risk_event_count"] > 0 or row["home_area_only_days"] > 0 or priority_rate >= 12:
            return HIGH_RISK_LABEL
        if row["review_event_count"] > 0 or row["home_start_end_without_field_days"] > 0 or priority_rate >= 6:
            return REVIEW_LABEL
        if row["risk_score"] > 0 or row.get("risk_priority_score", 0) > 0:
            return REVIEW_LABEL
        if row.get("confidence_score", 0) > 0 or row.get("low_confidence_event_count", 0) > 0:
            return LOW_CONFIDENCE_LABEL
        return NORMAL_LABEL

    @staticmethod
    def _review_levels() -> set[str]:
        return {REVIEW_LABEL, HIGH_RISK_LABEL}

    @staticmethod
    def _high_risk_levels() -> set[str]:
        return {HIGH_RISK_LABEL}

    def _score_event(
        self,
        event: pd.Series,
        candidates: pd.DataFrame,
        impossible_event_ids: set[Any] | None = None,
    ) -> dict[str, Any]:
        reason_codes: list[str] = []
        event_uid = event.get("event_uid")
        attendance_uid = event.get("attendance_uid")
        impossible_event_ids = impossible_event_ids or set()
        distance_from_home = self._optional_float(event.get("distance_from_home_m"))

        candidates = self._prepare_candidates(candidates)
        nearest = candidates.iloc[0] if not candidates.empty else None
        nearest_distance = float(nearest["beeline_meter"]) if nearest is not None else None
        nearest_name = self._candidate_name(nearest) if nearest is not None else None

        existing_clients = self._existing_client_candidates(candidates)
        nearest_existing = existing_clients.iloc[0] if not existing_clients.empty else None
        nearest_existing_distance = float(nearest_existing["beeline_meter"]) if nearest_existing is not None else None
        nearest_existing_name = self._candidate_name(nearest_existing) if nearest_existing is not None else None
        existing_top3 = self._format_candidate_summary(existing_clients.head(3))

        hospitals = self._hospital_candidates(candidates)
        nearest_hospital = hospitals.iloc[0] if not hospitals.empty else None
        nearest_hospital_distance = float(nearest_hospital["beeline_meter"]) if nearest_hospital is not None else None
        nearest_hospital_name = self._candidate_name(nearest_hospital) if nearest_hospital is not None else None

        suggested_prospects = self._prospect_candidates(candidates)
        suggested_top3 = self._format_candidate_summary(suggested_prospects.head(3))

        home_bucket = self._home_distance_bucket(distance_from_home)
        selected_rank = None
        selected_name: str | None = None
        selected_type: str | None = None
        selected_distance: float | None = None
        location_class: str
        risk_score = 0
        review_score = 0

        if distance_from_home is not None and distance_from_home <= 100:
            location_class = "home_core"
            selected_name = HOME_CORE_LABEL
            selected_type = HOME_CORE_LABEL
            selected_distance = distance_from_home
            risk_score = int(getattr(self.config, "risk_home_core_event_score", 0))
            reason_codes.append("near_home_checkin")
        elif (
            nearest_existing is not None
            and nearest_existing_distance is not None
            and nearest_existing_distance <= float(getattr(self.config, "v3_existing_client_radius_m", 1000.0))
        ):
            location_class = "existing_client_visit"
            selected_name = nearest_existing_name
            selected_type = EXISTING_CLIENT_LABEL
            selected_distance = nearest_existing_distance
            selected_rank = self._optional_int(nearest_existing.get("candidate_rank"))
        elif distance_from_home is not None and distance_from_home <= 1000:
            location_class = "home_edge"
            selected_name = HOME_EDGE_LABEL
            selected_type = HOME_EDGE_LABEL
            selected_distance = distance_from_home
            risk_score = int(getattr(self.config, "risk_home_edge_event_score", 0))
            reason_codes.append("near_home_checkin")
        else:
            location_class = "unknown_field"
            selected_name = UNKNOWN_FIELD_LABEL
            selected_type = UNKNOWN_FIELD_LABEL
            review_score = 4
            reason_codes.append("unknown_field")

        if event_uid in impossible_event_ids:
            reason_codes.append("impossible_travel_time")
            risk_score += REASON_WEIGHTS["impossible_travel_time"]

        reason_codes = list(dict.fromkeys(reason_codes))
        confidence_score = review_score + sum(REASON_WEIGHTS.get(code, 0) for code in reason_codes if code in CONFIDENCE_REASON_CODES)
        priority_score = risk_score * 3 + review_score
        distance_gap = (
            selected_distance - nearest_distance
            if selected_distance is not None and nearest_distance is not None
            else None
        )

        return {
            "event_uid": event_uid,
            "attendance_uid": attendance_uid,
            "risk_level": self._risk_level(risk_score, review_score, reason_codes),
            "risk_score": risk_score,
            "review_score": review_score,
            "priority_score": priority_score,
            "confidence_score": confidence_score,
            "risk_reason_codes": ",".join(reason_codes),
            "risk_reason_text": self._reason_text(
                reason_codes,
                selected_name,
                selected_distance,
                selected_rank,
                nearest_name,
                nearest_distance,
                distance_from_home,
            ),
            "location_class": location_class,
            "selected_visit_name": selected_name,
            "selected_visit_type": selected_type,
            "selected_visit_distance_m": selected_distance,
            "home_distance_bucket": home_bucket,
            "existing_client_candidates_top3": existing_top3,
            "suggested_prospects_top3": suggested_top3,
            "nearest_existing_client_name": nearest_existing_name,
            "nearest_existing_client_distance_m": nearest_existing_distance,
            "nearest_hospital_name": nearest_hospital_name,
            "nearest_hospital_distance_m": nearest_hospital_distance,
            "selected_distance_m": selected_distance,
            "nearest_distance_m": nearest_distance,
            "distance_gap_m": distance_gap,
            "selected_rank": selected_rank,
            "distance_from_home_m": distance_from_home,
        }

    def _prepare_candidates(self, candidates: pd.DataFrame) -> pd.DataFrame:
        if candidates.empty:
            return pd.DataFrame()
        result = candidates.copy()
        result["beeline_meter"] = pd.to_numeric(result.get("beeline_meter"), errors="coerce")
        result["candidate_rank"] = pd.to_numeric(result.get("candidate_rank"), errors="coerce")
        return result.dropna(subset=["beeline_meter"]).sort_values(
            ["beeline_meter", "candidate_rank"], na_position="last"
        )

    def _existing_client_candidates(self, candidates: pd.DataFrame) -> pd.DataFrame:
        if candidates.empty or "is_existing_client" not in candidates.columns:
            return candidates.iloc[0:0]
        return candidates.loc[self._as_bool_series(candidates["is_existing_client"])].sort_values(
            ["beeline_meter", "candidate_rank"], na_position="last"
        )

    def _hospital_candidates(self, candidates: pd.DataFrame) -> pd.DataFrame:
        if candidates.empty:
            return candidates
        if "is_hospital_facility" not in candidates.columns:
            return candidates.sort_values(["beeline_meter", "candidate_rank"], na_position="last")
        return candidates.loc[self._as_bool_series(candidates["is_hospital_facility"])].sort_values(
            ["beeline_meter", "candidate_rank"], na_position="last"
        )

    def _prospect_candidates(self, candidates: pd.DataFrame) -> pd.DataFrame:
        if candidates.empty:
            return candidates
        prospects = candidates
        if "is_existing_client" in prospects.columns:
            prospects = prospects.loc[~self._as_bool_series(prospects["is_existing_client"])]
        prospects = prospects.loc[
            prospects["beeline_meter"] <= float(getattr(self.config, "v3_unknown_prospect_radius_m", 500.0))
        ]
        return prospects.sort_values(["beeline_meter", "candidate_rank"], na_position="last")

    @staticmethod
    def _candidate_name(candidate: pd.Series | None) -> str | None:
        if candidate is None:
            return None
        for column in ["hospital_label", "hospital_name", "client_name", "hospital_id"]:
            value = candidate.get(column)
            if pd.notna(value) and str(value).strip():
                return str(value).strip()
        return None

    @classmethod
    def _format_candidate_summary(cls, candidates: pd.DataFrame) -> str:
        if candidates.empty:
            return ""
        parts = []
        for _, candidate in candidates.iterrows():
            name = cls._candidate_name(candidate) or "未知院所"
            distance = pd.to_numeric(pd.Series([candidate.get("beeline_meter")]), errors="coerce").iloc[0]
            if pd.isna(distance):
                parts.append(name)
            else:
                parts.append(f"{name} {format_distance(distance)}")
        return "；".join(parts)

    @staticmethod
    def _home_distance_bucket(distance_from_home: float | None) -> str:
        if distance_from_home is None:
            return ""
        if distance_from_home <= 100:
            return "100公尺內"
        if distance_from_home <= 500:
            return "101~500公尺內"
        if distance_from_home <= 1000:
            return "501~1000公尺內"
        return format_distance(distance_from_home)

    def _risk_level(self, score: int, confidence_score: int, reason_codes: list[str]) -> str:
        reasons = set(reason_codes)
        if "impossible_travel_time" in reasons:
            return HIGH_RISK_LABEL
        if score >= 10:
            return HIGH_RISK_LABEL
        if "selected_distance_too_far" in reasons:
            return REVIEW_LABEL
        if score > 0:
            return REVIEW_LABEL
        if confidence_score > 0:
            return REVIEW_LABEL
        return NORMAL_LABEL

    def _risk_score_from_codes(self, reason_codes: list[str], distance_from_home: float | None) -> int:
        score = 0
        for code in reason_codes:
            if code in CONFIDENCE_REASON_CODES:
                continue
            if code == "near_home_checkin":
                score += self._near_home_risk_score(distance_from_home)
            else:
                score += REASON_WEIGHTS[code]
        return score

    @staticmethod
    def _near_home_risk_score(distance_from_home: float | None) -> int:
        if distance_from_home is None:
            return 0
        if distance_from_home <= 100:
            return 3
        if distance_from_home <= 500:
            return 2
        if distance_from_home <= 1000:
            return 1
        return 0

    def _reason_text(
        self,
        reason_codes: list[str],
        selected_name: Any,
        selected_distance: float | None,
        selected_rank: int | None,
        nearest_name: Any,
        nearest_distance: float | None,
        distance_from_home: float | None,
    ) -> str:
        translated: list[str] = []
        if "far_customer_override" in reason_codes:
            translated.append(
                "系統為既有客戶選到較遠點，旁邊有更近候選；"
                f"選定 {selected_name or '未知既有客戶'} {self._format_distance(selected_distance)}，"
                f"最近候選 {nearest_name or '未知候選'} {self._format_distance(nearest_distance)}"
            )
        if "near_home_checkin" in reason_codes:
            translated.append(f"打卡點距離住家 {self._format_distance(distance_from_home)}，可能是在家附近打卡")
        if "selected_not_top5" in reason_codes:
            translated.append(f"選定候選排名第 {selected_rank}，不在最近前 5 名")
        if "selected_distance_too_far" in reason_codes:
            translated.append(f"選定點距離 {self._format_distance(selected_distance)}，超過自動選取門檻")
        if "nearby_candidate_conflict" in reason_codes:
            translated.append("附近候選院所過於密集，單點判定信心較低")
        if "no_reasonable_candidate" in reason_codes:
            translated.append("GPS 點附近沒有合理候選院所")
        if "unknown_field" in reason_codes:
            translated.append("1000公尺內沒有既有客戶，判定為未知出勤點，需主管依日報或備註覆核")
        if "impossible_travel_time" in reason_codes:
            translated.append("相鄰打卡點移動時間不合理")
        return "；".join(translated)

        text: list[str] = []
        if "far_customer_override" in reason_codes:
            text.append(
                "既有客戶距離偏遠且附近有更近候選："
                f"選取 {selected_name or '未知院所'} {self._format_distance(selected_distance)}，"
                f"最近 {nearest_name or '未知院所'} {self._format_distance(nearest_distance)}"
            )
        if "near_home_checkin" in reason_codes:
            text.append(f"打卡點距住家 {self._format_distance(distance_from_home)}，可能在住家附近打卡")
        if "selected_not_top5" in reason_codes:
            text.append(f"選取候選排名第 {selected_rank}，超出前 5 名")
        if "selected_distance_too_far" in reason_codes:
            text.append(f"選取院所距離 {self._format_distance(selected_distance)}，超出自動選取門檻")
        if "nearby_candidate_conflict" in reason_codes:
            text.append("最近距離附近存在多個候選院所")
        if "no_reasonable_candidate" in reason_codes:
            text.append("此 GPS 事件沒有可評估候選院所")
        if "impossible_travel_time" in reason_codes:
            text.append("相鄰行程移動時間不合理")
        return "；".join(text)

    def _impossible_travel_event_ids(self, raw_events: pd.DataFrame, route_segments: pd.DataFrame) -> set[Any]:
        if raw_events.empty or route_segments.empty:
            return set()

        event_required_columns = {"attendance_uid", "event_uid", "actual_time"}
        segment_required_columns = {"attendance_uid", "segment_no", "segment_type", "duration_seconds"}
        if not event_required_columns.issubset(raw_events.columns):
            return set()
        if not segment_required_columns.issubset(route_segments.columns):
            return set()

        events = raw_events.copy()
        if {"gps_lat", "gps_lon"}.issubset(events.columns):
            events = events[events["gps_lat"].notna() & events["gps_lon"].notna()].copy()
        events["actual_dt"] = pd.to_datetime(events["actual_time"], errors="coerce")
        if "source_row_no" not in events.columns:
            events["source_row_no"] = range(1, len(events) + 1)
        events["source_row_no"] = pd.to_numeric(events["source_row_no"], errors="coerce")
        events = events.dropna(subset=["attendance_uid", "event_uid", "actual_dt"]).sort_values(
            ["attendance_uid", "actual_dt", "source_row_no"],
            na_position="last",
        )
        if events.empty:
            return set()

        grouped_events = events.groupby("attendance_uid", sort=False)
        events["next_event_uid"] = grouped_events["event_uid"].shift(-1)
        events["next_actual_dt"] = grouped_events["actual_dt"].shift(-1)
        events["pair_no"] = grouped_events.cumcount() + 1
        events["elapsed_seconds"] = (events["next_actual_dt"] - events["actual_dt"]).dt.total_seconds()
        event_pairs = events.dropna(subset=["next_event_uid", "elapsed_seconds"])[
            ["attendance_uid", "pair_no", "next_event_uid", "elapsed_seconds"]
        ]
        if event_pairs.empty:
            return set()

        segments = route_segments[route_segments["segment_type"] == "between_points"].copy()
        if segments.empty:
            return set()

        segments["duration_seconds"] = pd.to_numeric(segments["duration_seconds"], errors="coerce")
        segments = segments.dropna(subset=["attendance_uid", "segment_no", "duration_seconds"]).sort_values(
            ["attendance_uid", "segment_no"],
            na_position="last",
        )
        if segments.empty:
            return set()

        segments["pair_no"] = segments.groupby("attendance_uid", sort=False).cumcount() + 1
        paired = event_pairs.merge(
            segments[["attendance_uid", "pair_no", "duration_seconds"]],
            on=["attendance_uid", "pair_no"],
            how="inner",
        )
        if paired.empty:
            return set()

        buffer_seconds = float(self.config.risk_impossible_travel_buffer_min) * 60
        impossible = paired["duration_seconds"] > paired["elapsed_seconds"].fillna(float("inf")) + buffer_seconds
        return set(paired.loc[impossible, "next_event_uid"])

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if pd.isna(value):
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    @classmethod
    def _as_bool_series(cls, values: pd.Series) -> pd.Series:
        return values.apply(cls._as_bool)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if pd.isna(value):
            return None
        return int(value)

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(numeric):
            return None
        return float(numeric)

    @staticmethod
    def _format_distance(value: float | None) -> str:
        if value is None:
            return "未知距離"
        return format_distance(value)
