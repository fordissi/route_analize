from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


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
            return "高風險需覆核"
        if score >= 10:
            return "高風險需覆核"
        if "far_customer_override" in reasons or "selected_distance_too_far" in reasons:
            return "需覆核"
        if score > 0:
            return "低信心"
        return "正常"

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
