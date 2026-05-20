from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from matcher import haversine_meter


REASON_WEIGHTS = {
    "far_customer_override": 5,
    "selected_not_top5": 3,
    "selected_distance_too_far": 4,
    "nearby_candidate_conflict": 2,
    "no_reasonable_candidate": 3,
    "impossible_travel_time": 8,
    "high_finance_variance": 5,
    "home_area_only_trace": 6,
    "home_start_end_without_field_trace": 4,
    "insufficient_route_evidence": 3,
}

NORMAL_LABEL = "正常"
LOW_CONFIDENCE_LABEL = "低信心"
REVIEW_LABEL = "需覆核"
HIGH_RISK_LABEL = "高風險需覆核"

EVENT_RISK_COLUMNS = [
    "event_uid",
    "attendance_uid",
    "risk_level",
    "risk_score",
    "risk_reason_codes",
    "risk_reason_text",
    "selected_distance_m",
    "nearest_distance_m",
    "distance_gap_m",
    "selected_rank",
]

DAILY_RISK_COLUMNS = [
    "attendance_uid",
    "employee_id",
    "employee_name",
    "department",
    "work_date",
    "gps_event_count",
    "risk_score",
    "risk_rate",
    "review_event_count",
    "high_risk_event_count",
    "risk_level",
    "home_area_only_trace",
    "home_start_end_without_field_trace",
    "insufficient_route_evidence",
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
    "risk_rate",
    "review_rate",
    "review_event_count",
    "high_risk_event_count",
    "home_area_only_days",
    "home_start_end_without_field_days",
    "insufficient_route_evidence_days",
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
    ) -> pd.DataFrame:
        if raw_events.empty:
            return pd.DataFrame(columns=EVENT_RISK_COLUMNS)

        impossible_event_ids = self._impossible_travel_event_ids(raw_events, route_segments)
        rows = []
        for _, event in raw_events.iterrows():
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

        risk = event_risk.copy()
        if risk.empty or "attendance_uid" not in risk.columns:
            grouped = pd.DataFrame(columns=["attendance_uid", "risk_score", "review_event_count", "high_risk_event_count", "risk_reason_summary"])
        else:
            if "risk_score" not in risk.columns:
                risk["risk_score"] = 0
            if "risk_level" not in risk.columns:
                risk["risk_level"] = ""
            if "risk_reason_codes" not in risk.columns:
                risk["risk_reason_codes"] = ""
            risk["risk_score"] = pd.to_numeric(risk["risk_score"], errors="coerce").fillna(0)
            risk["review_event"] = risk["risk_level"].isin(self._review_levels())
            risk["high_risk_event"] = risk["risk_level"].isin(self._high_risk_levels())
            grouped = (
                risk.groupby("attendance_uid", dropna=False)
                .agg(
                    risk_score=("risk_score", "sum"),
                    review_event_count=("review_event", "sum"),
                    high_risk_event_count=("high_risk_event", "sum"),
                    risk_reason_summary=("risk_reason_codes", self._join_reason_codes),
                )
                .reset_index()
            )

        result = result.merge(grouped, on="attendance_uid", how="left")
        for column in ["risk_score", "review_event_count", "high_risk_event_count"]:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)
        result["review_event_count"] = result["review_event_count"].astype(int)
        result["high_risk_event_count"] = result["high_risk_event_count"].astype(int)
        result["risk_reason_summary"] = result["risk_reason_summary"].fillna("")

        home_trace = self._build_home_trace_risk(result, raw_events, employees, matches)
        result = result.merge(home_trace, on="attendance_uid", how="left")
        for column in [
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
            "home_near_event_count",
            "field_visit_count",
        ]:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
        result["max_distance_from_home_m"] = pd.to_numeric(result["max_distance_from_home_m"], errors="coerce").fillna(0.0)

        result["risk_score"] = result["risk_score"] + (
            result["home_area_only_trace"] * REASON_WEIGHTS["home_area_only_trace"]
            + result["home_start_end_without_field_trace"] * REASON_WEIGHTS["home_start_end_without_field_trace"]
            + result["insufficient_route_evidence"] * REASON_WEIGHTS["insufficient_route_evidence"]
        )
        result["risk_reason_summary"] = result.apply(self._merge_daily_reason_summary, axis=1)
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
            "review_event_count",
            "high_risk_event_count",
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
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
                review_event_count=("review_event_count", "sum"),
                high_risk_event_count=("high_risk_event_count", "sum"),
                home_area_only_days=("home_area_only_trace", "sum"),
                home_start_end_without_field_days=("home_start_end_without_field_trace", "sum"),
                insufficient_route_evidence_days=("insufficient_route_evidence", "sum"),
            )
            .reset_index()
        )
        grouped["risk_rate"] = grouped["risk_score"] / grouped["gps_event_count"].clip(lower=1)
        grouped["review_rate"] = grouped["review_event_count"] / grouped["gps_event_count"].clip(lower=1)
        grouped["risk_level"] = grouped.apply(self._employee_level, axis=1)
        return grouped.reindex(columns=EMPLOYEE_RISK_COLUMNS).sort_values(
            ["risk_rate", "risk_score"], ascending=[False, False]
        )

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
            & (grouped["gps_points"] >= 2)
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

    def _merge_daily_reason_summary(self, row: pd.Series) -> str:
        reasons = set(str(row.get("risk_reason_summary", "") or "").split(",")) - {""}
        if row.get("home_area_only_trace", 0):
            reasons.add("home_area_only_trace")
        if row.get("home_start_end_without_field_trace", 0):
            reasons.add("home_start_end_without_field_trace")
        if row.get("insufficient_route_evidence", 0):
            reasons.add("insufficient_route_evidence")
        return ",".join(sorted(reasons))

    def _daily_level(self, row: pd.Series) -> str:
        if row["high_risk_event_count"] > 0 or row["risk_score"] >= 10:
            return HIGH_RISK_LABEL
        if row["review_event_count"] > 0 or row.get("home_area_only_trace", 0) or row.get("home_start_end_without_field_trace", 0):
            return REVIEW_LABEL
        if row["risk_score"] > 0:
            return LOW_CONFIDENCE_LABEL
        return NORMAL_LABEL

    def _employee_level(self, row: pd.Series) -> str:
        if row["high_risk_event_count"] > 0 or row["home_area_only_days"] > 0 or row["risk_rate"] >= 4:
            return HIGH_RISK_LABEL
        if row["review_event_count"] > 0 or row["home_start_end_without_field_days"] > 0 or row["risk_rate"] >= 2:
            return REVIEW_LABEL
        if row["risk_score"] > 0:
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

        selected_distance = None
        nearest_distance = None
        distance_gap = None
        selected_rank = None
        selected_name = None
        nearest_name = None

        if candidates.empty:
            reason_codes.append("no_reasonable_candidate")
        else:
            candidates = candidates.copy()
            candidates["beeline_meter"] = pd.to_numeric(candidates.get("beeline_meter"), errors="coerce")
            candidates["candidate_rank"] = pd.to_numeric(candidates.get("candidate_rank"), errors="coerce")
            candidates = candidates.dropna(subset=["beeline_meter"])

            if candidates.empty:
                reason_codes.append("no_reasonable_candidate")
            else:
                nearest = candidates.sort_values(["beeline_meter", "candidate_rank"], na_position="last").iloc[0]
                nearest_distance = float(nearest["beeline_meter"])
                nearest_name = nearest.get("hospital_label")
                if nearest_distance > float(self.config.risk_auto_select_max_distance_m):
                    reason_codes.append("no_reasonable_candidate")

                if "is_selected" in candidates.columns:
                    selected_rows = candidates[self._as_bool_series(candidates["is_selected"])]
                else:
                    selected_rows = candidates.iloc[0:0]
                if not selected_rows.empty:
                    selected = selected_rows.sort_values(["candidate_rank", "beeline_meter"], na_position="last").iloc[0]
                    selected_distance = float(selected["beeline_meter"])
                    selected_rank = self._optional_int(selected.get("candidate_rank"))
                    selected_name = selected.get("hospital_label")
                    distance_gap = selected_distance - nearest_distance

                    if selected_rank is not None and selected_rank > 5:
                        reason_codes.append("selected_not_top5")
                    if selected_distance > float(self.config.risk_auto_select_max_distance_m):
                        reason_codes.append("selected_distance_too_far")
                    if (
                        self._as_bool(selected.get("is_existing_client"))
                        and selected_distance > float(self.config.risk_high_distance_m)
                        and nearest_distance <= float(self.config.risk_review_distance_m)
                        and distance_gap >= float(self.config.risk_customer_override_gap_m)
                    ):
                        reason_codes.append("far_customer_override")

                close_candidates = candidates[
                    candidates["beeline_meter"] <= nearest_distance + float(self.config.risk_ambiguity_distance_m)
                ]
                if len(close_candidates) >= int(self.config.risk_ambiguity_candidate_count):
                    reason_codes.append("nearby_candidate_conflict")

        if event_uid in impossible_event_ids:
            reason_codes.append("impossible_travel_time")

        reason_codes = list(dict.fromkeys(reason_codes))
        risk_score = sum(REASON_WEIGHTS[code] for code in reason_codes)

        return {
            "event_uid": event_uid,
            "attendance_uid": attendance_uid,
            "risk_level": self._risk_level(risk_score, reason_codes),
            "risk_score": risk_score,
            "risk_reason_codes": ",".join(reason_codes),
            "risk_reason_text": self._reason_text(
                reason_codes,
                selected_name,
                selected_distance,
                selected_rank,
                nearest_name,
                nearest_distance,
            ),
            "selected_distance_m": selected_distance,
            "nearest_distance_m": nearest_distance,
            "distance_gap_m": distance_gap,
            "selected_rank": selected_rank,
        }

    def _risk_level(self, score: int, reason_codes: list[str]) -> str:
        reasons = set(reason_codes)
        if "impossible_travel_time" in reasons:
            return HIGH_RISK_LABEL
        if score >= 10:
            return HIGH_RISK_LABEL
        if "far_customer_override" in reasons or "selected_distance_too_far" in reasons:
            return REVIEW_LABEL
        if score > 0:
            return LOW_CONFIDENCE_LABEL
        return NORMAL_LABEL

    def _reason_text(
        self,
        reason_codes: list[str],
        selected_name: Any,
        selected_distance: float | None,
        selected_rank: int | None,
        nearest_name: Any,
        nearest_distance: float | None,
    ) -> str:
        text: list[str] = []
        if "far_customer_override" in reason_codes:
            text.append(
                "既有客戶距離偏遠且附近有更近候選："
                f"選取 {selected_name or '未知院所'} {self._format_distance(selected_distance)}，"
                f"最近 {nearest_name or '未知院所'} {self._format_distance(nearest_distance)}"
            )
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
    def _format_distance(value: float | None) -> str:
        if value is None:
            return "未知距離"
        return f"{value:.0f}m"
