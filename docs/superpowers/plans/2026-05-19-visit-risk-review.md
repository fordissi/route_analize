# Visit Risk Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared visit-risk review layer that marks low-confidence and review-worthy check-ins, then surfaces employee risk ranking consistently in daily, weekly, personal-period, all-employee overview, and Google Sheet export reports.

**Architecture:** Keep matching and reporting separated. `matcher.py` continues to produce candidate rows; a new `risk_service.py` computes event-level, day-level, and employee-period risk summaries from enriched matches, raw events, route segments, and finance data. `pipeline.py` writes canonical risk tables, and `app.py` consumes those tables without duplicating scoring rules.

**Tech Stack:** Python, pandas, scipy KDTree output, Streamlit, Plotly, pytest, CSV/SQLite persistence through the existing pipeline.

---

## File Structure

- Create `risk_service.py`: shared rule engine for event risk flags, daily risk summaries, employee period summaries, severity labels, and reason text.
- Create `tests/test_risk_service.py`: focused tests for far existing-client override, dense candidate ambiguity, impossible travel time, and employee ranking normalization.
- Modify `settings.py`: add configurable risk thresholds with conservative defaults.
- Modify `db_manager.py`: add SQLite schemas for `event_risk_review`, `daily_risk_summary`, and `employee_risk_summary`.
- Modify `pipeline.py`: build and persist risk tables after matching, route summary, finance audit, and BI metrics are available.
- Modify `app.py`: load risk tables, merge risk labels into event detail, candidate cards, weekly cards, personal report, all-employee overview, and Google Sheet export payload.
- Modify `finance_auditor.py` or add a small claim comparison helper only if implementation needs explicit claim granularity fields; monthly claims must remain month-level evidence and must not be treated as daily claimed mileage.
- Modify `METRICS_GUIDE.md`: document the new neutral terminology and explain that these flags are review prioritization, not misconduct conclusions.

## Risk Model

Use neutral status labels:

- `正常`: no rule fired and selected candidate is near enough.
- `低信心`: the system lacks enough spatial confidence to auto-pick cleanly.
- `需覆核`: the selected result conflicts with distance facts or ranking.
- `異常風險`: route/time/finance evidence is materially inconsistent.
- `高風險需覆核`: multiple medium/high severity signals appear in the same day or period.

Event-level reason codes:

- `far_customer_override`: selected existing client is far and much farther than nearest candidate.
- `selected_not_top5`: selected candidate rank is greater than 5.
- `selected_distance_too_far`: selected candidate distance exceeds the auto-selection limit.
- `nearby_candidate_conflict`: multiple close candidates make a single choice ambiguous.
- `no_reasonable_candidate`: no reasonable candidate within the configured distance.
- `impossible_travel_time`: adjacent GPS points require more travel time than elapsed time allows.
- `high_finance_variance`: finance variance is already red for the same attendance day.
- `home_area_only_trace`: the whole day stays near the employee home location and has no field-visit evidence.
- `home_start_end_without_field_trace`: first and last GPS points are near home, but no middle point supports a field visit.
- `insufficient_route_evidence`: GPS points or spatial movement are too limited to support an outside-sales route.

Default thresholds:

```python
risk_review_distance_m = 1000.0
risk_high_distance_m = 1500.0
risk_auto_select_max_distance_m = 2000.0
risk_customer_override_gap_m = 500.0
risk_ambiguity_distance_m = 150.0
risk_ambiguity_candidate_count = 3
risk_min_travel_speed_kmph = 5.0
risk_impossible_travel_buffer_min = 10.0
risk_home_radius_m = 500.0
risk_home_area_max_distance_m = 1000.0
risk_min_field_visit_distance_from_home_m = 1000.0
```

Scoring:

```python
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
```

Normalize employee ranking by GPS volume:

```python
risk_rate = total_risk_score / max(gps_event_count, 1)
review_rate = review_event_count / max(gps_event_count, 1)
```

Home-area trace rules are daily-level safeguards, not event-level accusations:

```text
Allowed: home -> hospital/customer evidence -> home
Review: home -> home with no reasonable field visit evidence
High priority: home -> home plus mileage/per diem/finance variance evidence
```

`field_visit_count` means selected or nearest candidate evidence within a reasonable distance and outside the home radius. A check-in near home can still be normal when the day contains at least one credible field visit away from home.

Claim granularity guardrails:

```text
monthly_claims.csv = employee-month evidence only
daily_claims.csv = future employee-day evidence
```

Monthly claim variance can influence employee/month review priority, but it must not be attached to a single GPS event or interpreted as "monthly claim vs one day mileage." Until daily claim import exists, risk reason `high_finance_variance` means "the employee-month is financially inconsistent," not "this individual day is financially inconsistent." When daily claim import is added, daily claim variance should use separate reason codes such as `daily_claim_variance_high` and can safely contribute to `daily_risk_summary`.

---

### Task 1: Add Risk Threshold Settings

**Files:**
- Modify: `settings.py`
- Test: `tests/test_risk_service.py`

- [ ] **Step 1: Write threshold-loading test**

Add this test skeleton after creating `tests/test_risk_service.py` in Task 2 if the file does not exist yet:

```python
from pathlib import Path

from settings import AppConfig


def test_risk_threshold_defaults_are_available() -> None:
    config = AppConfig(
        root_dir=Path("."),
        data_dir=Path("."),
        output_dir=Path("."),
        imports_dir=Path("."),
        attendance_import_dir=Path("."),
        cleaned_dir=Path("."),
        reports_dir=Path("."),
        database_dir=Path("."),
        templates_dir=Path("."),
        logs_dir=Path("."),
        sqlite_path=Path("test.sqlite"),
        settings_path=Path("settings.json"),
    )

    assert config.risk_review_distance_m == 1000.0
    assert config.risk_high_distance_m == 1500.0
    assert config.risk_customer_override_gap_m == 500.0
    assert config.risk_home_radius_m == 500.0
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `pytest tests/test_risk_service.py::test_risk_threshold_defaults_are_available -v`

Expected: FAIL with an `AttributeError` for `risk_review_distance_m`.

- [ ] **Step 3: Add settings fields**

In `settings.py`, add fields to `AppConfig` after `ambiguous_distance_m`:

```python
    risk_review_distance_m: float = 1000.0
    risk_high_distance_m: float = 1500.0
    risk_auto_select_max_distance_m: float = 2000.0
    risk_customer_override_gap_m: float = 500.0
    risk_ambiguity_distance_m: float = 150.0
    risk_ambiguity_candidate_count: int = 3
    risk_min_travel_speed_kmph: float = 5.0
    risk_impossible_travel_buffer_min: float = 10.0
    risk_home_radius_m: float = 500.0
    risk_home_area_max_distance_m: float = 1000.0
    risk_min_field_visit_distance_from_home_m: float = 1000.0
```

Add the same field names to `CONFIG_OVERRIDE_FIELDS`. Update `_coerce_override` so `risk_ambiguity_candidate_count` is coerced as `int`, and the other risk fields are coerced as `float`.

- [ ] **Step 4: Run the test and verify it passes**

Run: `pytest tests/test_risk_service.py::test_risk_threshold_defaults_are_available -v`

Expected: PASS.

---

### Task 2: Create Event-Level Risk Engine

**Files:**
- Create: `risk_service.py`
- Create/Modify: `tests/test_risk_service.py`

- [ ] **Step 1: Write far existing-client override test**

Add:

```python
import pandas as pd

from risk_service import RiskService
from settings import AppConfig
from pathlib import Path


def make_config() -> AppConfig:
    return AppConfig(
        root_dir=Path("."),
        data_dir=Path("."),
        output_dir=Path("."),
        imports_dir=Path("."),
        attendance_import_dir=Path("."),
        cleaned_dir=Path("."),
        reports_dir=Path("."),
        database_dir=Path("."),
        templates_dir=Path("."),
        logs_dir=Path("."),
        sqlite_path=Path("test.sqlite"),
        settings_path=Path("settings.json"),
    )


def test_far_existing_client_override_requires_review() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "太一堂中醫診所", "beeline_meter": 772.0, "is_existing_client": 0, "is_selected": 0, "selection_type": "潛在院所"},
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 16, "hospital_id": "c1", "hospital_label": "和平身心診所", "beeline_meter": 2434.0, "is_existing_client": 1, "is_selected": 1, "selection_type": "既有客戶"},
        ]
    )
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:08:04"}])

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame())
    row = result.iloc[0]

    assert row["risk_level"] == "需覆核"
    assert "far_customer_override" in row["risk_reason_codes"]
    assert row["risk_score"] >= 8
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `pytest tests/test_risk_service.py::test_far_existing_client_override_requires_review -v`

Expected: FAIL because `risk_service` does not exist.

- [ ] **Step 3: Implement `risk_service.py` minimal event engine**

Create `risk_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

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
        rows = []
        if raw_events.empty:
            return self._empty_event_risk()

        grouped_matches = matches.groupby("event_uid", dropna=False) if not matches.empty else {}
        for event in raw_events.itertuples(index=False):
            event_uid = getattr(event, "event_uid")
            attendance_uid = getattr(event, "attendance_uid", None)
            group = grouped_matches.get_group(event_uid).copy() if event_uid in grouped_matches.groups else pd.DataFrame()
            rows.append(self._score_event(event_uid, attendance_uid, group))
        return pd.DataFrame(rows)

    def _score_event(self, event_uid: str, attendance_uid: str | None, candidates: pd.DataFrame) -> dict:
        reason_codes: list[str] = []
        selected_name = ""
        selected_distance = None
        selected_rank = None
        nearest_distance = None
        nearest_name = ""

        if candidates.empty:
            reason_codes.append("no_reasonable_candidate")
        else:
            candidates["beeline_meter"] = pd.to_numeric(candidates["beeline_meter"], errors="coerce")
            nearest = candidates.sort_values(["beeline_meter", "candidate_rank"], na_position="last").iloc[0]
            selected = candidates.loc[candidates["is_selected"] == 1]
            selected = selected.iloc[0] if not selected.empty else nearest
            nearest_distance = float(nearest["beeline_meter"])
            nearest_name = str(nearest.get("hospital_label", nearest.get("hospital_id", "")))
            selected_distance = float(selected["beeline_meter"])
            selected_rank = int(selected["candidate_rank"])
            selected_name = str(selected.get("hospital_label", selected.get("hospital_id", "")))

            if selected_rank > 5:
                reason_codes.append("selected_not_top5")
            if selected_distance > float(self.config.risk_auto_select_max_distance_m):
                reason_codes.append("selected_distance_too_far")
            if (
                int(selected.get("is_existing_client", 0)) == 1
                and selected_distance > float(self.config.risk_high_distance_m)
                and nearest_distance <= float(self.config.risk_review_distance_m)
                and selected_distance - nearest_distance >= float(self.config.risk_customer_override_gap_m)
            ):
                reason_codes.append("far_customer_override")

            close_candidates = candidates.loc[
                candidates["beeline_meter"] <= nearest_distance + float(self.config.risk_ambiguity_distance_m)
            ]
            if len(close_candidates) >= int(self.config.risk_ambiguity_candidate_count):
                reason_codes.append("nearby_candidate_conflict")
            if nearest_distance > float(self.config.risk_auto_select_max_distance_m):
                reason_codes.append("no_reasonable_candidate")

        risk_score = sum(REASON_WEIGHTS[code] for code in dict.fromkeys(reason_codes))
        risk_level = self._risk_level(risk_score, reason_codes)
        return {
            "event_uid": event_uid,
            "attendance_uid": attendance_uid,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_reason_codes": ",".join(dict.fromkeys(reason_codes)),
            "risk_reason_text": self._reason_text(reason_codes, selected_name, selected_distance, selected_rank, nearest_name, nearest_distance),
            "selected_distance_m": selected_distance,
            "nearest_distance_m": nearest_distance,
            "distance_gap_m": None if selected_distance is None or nearest_distance is None else selected_distance - nearest_distance,
            "selected_rank": selected_rank,
        }

    def _risk_level(self, score: int, reason_codes: list[str]) -> str:
        if "impossible_travel_time" in reason_codes or score >= 10:
            return "高風險需覆核"
        if "far_customer_override" in reason_codes or "selected_distance_too_far" in reason_codes:
            return "需覆核"
        if score > 0:
            return "低信心"
        return "正常"

    def _reason_text(self, reason_codes: list[str], selected_name: str, selected_distance, selected_rank, nearest_name: str, nearest_distance) -> str:
        if not reason_codes:
            return ""
        parts = []
        if "far_customer_override" in reason_codes:
            parts.append(f"既有客戶 {selected_name} 距離 {selected_distance:.0f}m，最近候選 {nearest_name} 僅 {nearest_distance:.0f}m")
        if "selected_not_top5" in reason_codes:
            parts.append(f"系統選定候選排名為 #{selected_rank}")
        if "selected_distance_too_far" in reason_codes:
            parts.append(f"系統選定距離 {selected_distance:.0f}m 已超過自動判定上限")
        if "nearby_candidate_conflict" in reason_codes:
            parts.append("近距離候選過多，需人工確認實際拜訪點")
        if "no_reasonable_candidate" in reason_codes:
            parts.append("附近沒有合理距離內的候選院所")
        return "；".join(parts)

    def _empty_event_risk(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
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
        )
```

- [ ] **Step 4: Run the test and verify it passes**

Run: `pytest tests/test_risk_service.py::test_far_existing_client_override_requires_review -v`

Expected: PASS.

---

### Task 3: Add Ambiguity and Impossible-Travel Rules

**Files:**
- Modify: `risk_service.py`
- Modify: `tests/test_risk_service.py`

- [ ] **Step 1: Write dense candidate ambiguity test**

Add:

```python
def test_nearby_candidate_conflict_is_low_confidence() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "A診所", "beeline_meter": 120.0, "is_existing_client": 0, "is_selected": 1, "selection_type": "潛在院所"},
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 2, "hospital_id": "h2", "hospital_label": "B診所", "beeline_meter": 180.0, "is_existing_client": 0, "is_selected": 0, "selection_type": "潛在院所"},
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 3, "hospital_id": "h3", "hospital_label": "C診所", "beeline_meter": 220.0, "is_existing_client": 0, "is_selected": 0, "selection_type": "潛在院所"},
        ]
    )
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:00:00"}])

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame())

    assert result.iloc[0]["risk_level"] == "低信心"
    assert "nearby_candidate_conflict" in result.iloc[0]["risk_reason_codes"]
```

- [ ] **Step 2: Write impossible travel test**

Add:

```python
def test_impossible_travel_time_is_high_risk() -> None:
    matches = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "seq_no": 1, "candidate_rank": 1, "hospital_id": "h1", "hospital_label": "A診所", "beeline_meter": 50.0, "is_existing_client": 0, "is_selected": 1, "selection_type": "潛在院所"},
            {"event_uid": "e2", "attendance_uid": "a1", "seq_no": 2, "candidate_rank": 1, "hospital_id": "h2", "hospital_label": "B診所", "beeline_meter": 60.0, "is_existing_client": 0, "is_selected": 1, "selection_type": "潛在院所"},
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "e2", "attendance_uid": "a1", "actual_time": "2026-05-08 08:10:00"},
        ]
    )
    route_segments = pd.DataFrame(
        [
            {"attendance_uid": "a1", "segment_no": 1, "segment_type": "field", "duration_seconds": 3600, "distance_meters": 20000, "status": "OK"}
        ]
    )

    result = RiskService(make_config()).build_event_risk(raw_events, matches, route_segments, pd.DataFrame())

    assert "impossible_travel_time" in result.loc[result["event_uid"] == "e2", "risk_reason_codes"].iloc[0]
    assert result.loc[result["event_uid"] == "e2", "risk_level"].iloc[0] == "高風險需覆核"
```

- [ ] **Step 3: Run tests and verify impossible-travel fails**

Run: `pytest tests/test_risk_service.py -v`

Expected: the ambiguity test passes if Task 2 logic is present; impossible-travel fails until route segment logic is added.

- [ ] **Step 4: Add route segment risk injection**

In `risk_service.py`, before scoring individual events, compute impossible event ids:

```python
        impossible_event_ids = self._impossible_travel_event_ids(raw_events, route_segments)
```

Pass the set into `_score_event`, and append this inside `_score_event`:

```python
        if event_uid in impossible_event_ids:
            reason_codes.append("impossible_travel_time")
```

Add this helper:

```python
    def _impossible_travel_event_ids(self, raw_events: pd.DataFrame, route_segments: pd.DataFrame) -> set[str]:
        if raw_events.empty or route_segments.empty:
            return set()
        events = raw_events.copy()
        events["actual_dt"] = pd.to_datetime(events["actual_time"], errors="coerce")
        events = events.dropna(subset=["attendance_uid", "actual_dt"]).sort_values(
            ["attendance_uid", "actual_dt", "source_row_no"],
            na_position="last",
        )
        events["next_event_uid"] = events.groupby("attendance_uid")["event_uid"].shift(-1)
        events["pair_no"] = events.groupby("attendance_uid").cumcount() + 1
        events["elapsed_seconds"] = (
            events.groupby("attendance_uid")["actual_dt"].shift(-1) - events["actual_dt"]
        ).dt.total_seconds()
        pairs = events.dropna(subset=["next_event_uid", "elapsed_seconds"])[
            ["attendance_uid", "pair_no", "next_event_uid", "elapsed_seconds"]
        ]

        segments = route_segments.loc[route_segments["segment_type"].eq("between_points")].copy()
        if segments.empty:
            return set()
        segments = segments.sort_values(["attendance_uid", "segment_no"]).copy()
        segments["pair_no"] = segments.groupby("attendance_uid").cumcount() + 1
        segments["duration_seconds"] = pd.to_numeric(segments["duration_seconds"], errors="coerce")
        paired = pairs.merge(
            segments[["attendance_uid", "pair_no", "duration_seconds"]],
            on=["attendance_uid", "pair_no"],
            how="left",
        )
        risky = paired.loc[
            paired["duration_seconds"].fillna(0)
            > paired["elapsed_seconds"].fillna(float("inf")) + float(self.config.risk_impossible_travel_buffer_min) * 60
        ]
        return set(risky["next_event_uid"].dropna().astype(str))
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `pytest tests/test_risk_service.py -v`

Expected: PASS.

---

### Task 4: Build Daily and Employee Risk Summaries

**Files:**
- Modify: `risk_service.py`
- Modify: `tests/test_risk_service.py`

- [ ] **Step 1: Write home-area-only daily trace test**

Add:

```python
def test_home_area_only_trace_requires_review() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e2", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "員工A",
                "department": "業務",
                "work_date": "2026-05-08",
                "gps_event_count": 2,
            }
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "gps_lat": 24.70000, "gps_lon": 121.77000, "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "e2", "attendance_uid": "a1", "gps_lat": 24.70050, "gps_lon": 121.77050, "actual_time": "2026-05-08 18:00:00"},
        ]
    )
    employees = pd.DataFrame(
        [{"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010}]
    )

    service = RiskService(make_config())
    daily = service.build_daily_risk_summary(event_risk, attendance, raw_events=raw_events, employees=employees, matches=pd.DataFrame())
    row = daily.iloc[0]

    assert row["risk_level"] == "需覆核"
    assert row["home_area_only_trace"] == 1
    assert "home_area_only_trace" in row["risk_reason_summary"]
    assert row["risk_score"] >= 6
```

- [ ] **Step 2: Write home-start/home-end with field evidence test**

Add:

```python
def test_home_start_end_with_field_visit_is_not_penalized() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e2", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
            {"event_uid": "e3", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0, "risk_reason_codes": ""},
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "employee_name": "員工A",
                "department": "業務",
                "work_date": "2026-05-08",
                "gps_event_count": 3,
            }
        ]
    )
    raw_events = pd.DataFrame(
        [
            {"event_uid": "e1", "attendance_uid": "a1", "gps_lat": 24.70000, "gps_lon": 121.77000, "actual_time": "2026-05-08 08:00:00"},
            {"event_uid": "e2", "attendance_uid": "a1", "gps_lat": 24.73000, "gps_lon": 121.80000, "actual_time": "2026-05-08 10:00:00"},
            {"event_uid": "e3", "attendance_uid": "a1", "gps_lat": 24.70040, "gps_lon": 121.77040, "actual_time": "2026-05-08 18:00:00"},
        ]
    )
    employees = pd.DataFrame(
        [{"employee_id": "A", "home_lat": 24.70010, "home_lon": 121.77010}]
    )
    matches = pd.DataFrame(
        [
            {"event_uid": "e2", "attendance_uid": "a1", "is_selected": 1, "beeline_meter": 120.0, "selection_type": "既有客戶"}
        ]
    )

    service = RiskService(make_config())
    daily = service.build_daily_risk_summary(event_risk, attendance, raw_events=raw_events, employees=employees, matches=matches)

    assert daily.iloc[0]["home_area_only_trace"] == 0
    assert "home_area_only_trace" not in daily.iloc[0]["risk_reason_summary"]
```

- [ ] **Step 3: Write daily and employee ranking test**

Add:

```python
def test_employee_summary_normalizes_by_gps_count() -> None:
    event_risk = pd.DataFrame(
        [
            {"event_uid": "a1e1", "attendance_uid": "a1", "risk_level": "需覆核", "risk_score": 8},
            {"event_uid": "a1e2", "attendance_uid": "a1", "risk_level": "正常", "risk_score": 0},
            {"event_uid": "b1e1", "attendance_uid": "b1", "risk_level": "需覆核", "risk_score": 8},
        ]
    )
    attendance = pd.DataFrame(
        [
            {"attendance_uid": "a1", "employee_id": "A", "employee_name": "員工A", "department": "業務", "work_date": "2026-05-08", "gps_event_count": 10},
            {"attendance_uid": "b1", "employee_id": "B", "employee_name": "員工B", "department": "業務", "work_date": "2026-05-08", "gps_event_count": 2},
        ]
    )

    service = RiskService(make_config())
    daily = service.build_daily_risk_summary(event_risk, attendance)
    employee = service.build_employee_risk_summary(daily)

    assert set(daily["attendance_uid"]) == {"a1", "b1"}
    assert employee.sort_values("risk_rate", ascending=False).iloc[0]["employee_id"] == "B"
```

- [ ] **Step 4: Run the tests and verify home-area methods fail**

Run: `pytest tests/test_risk_service.py::test_home_area_only_trace_requires_review tests/test_risk_service.py::test_home_start_end_with_field_visit_is_not_penalized tests/test_risk_service.py::test_employee_summary_normalizes_by_gps_count -v`

Expected: FAIL because daily home-area trace logic and/or summary methods do not exist.

- [ ] **Step 5: Implement summary methods and home-area trace logic**

Add to `RiskService`:

```python
    def build_daily_risk_summary(
        self,
        event_risk: pd.DataFrame,
        attendance: pd.DataFrame,
        raw_events: pd.DataFrame | None = None,
        employees: pd.DataFrame | None = None,
        matches: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if attendance.empty:
            return pd.DataFrame(columns=["attendance_uid", "risk_score", "review_event_count", "high_risk_event_count", "risk_level", "home_area_only_trace", "home_start_end_without_field_trace", "insufficient_route_evidence"])
        risk = event_risk.copy()
        risk["risk_score"] = pd.to_numeric(risk["risk_score"], errors="coerce").fillna(0)
        risk["review_event"] = risk["risk_level"].isin(["需覆核", "高風險需覆核"])
        risk["high_risk_event"] = risk["risk_level"].eq("高風險需覆核")
        grouped = (
            risk.groupby("attendance_uid", dropna=False)
            .agg(
                risk_score=("risk_score", "sum"),
                review_event_count=("review_event", "sum"),
                high_risk_event_count=("high_risk_event", "sum"),
                risk_reason_summary=("risk_reason_codes", lambda s: ",".join(sorted(set(",".join(s.dropna().astype(str)).split(",")) - {""}))),
            )
            .reset_index()
        )
        result = attendance.merge(grouped, on="attendance_uid", how="left")
        for column in ["risk_score", "review_event_count", "high_risk_event_count"]:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)
        home_trace = self._build_home_trace_risk(attendance, raw_events, employees, matches)
        if not home_trace.empty:
            result = result.merge(home_trace, on="attendance_uid", how="left")
        for column in ["home_area_only_trace", "home_start_end_without_field_trace", "insufficient_route_evidence"]:
            if column not in result.columns:
                result[column] = 0
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
        result["home_trace_score"] = (
            result["home_area_only_trace"] * REASON_WEIGHTS["home_area_only_trace"]
            + result["home_start_end_without_field_trace"] * REASON_WEIGHTS["home_start_end_without_field_trace"]
            + result["insufficient_route_evidence"] * REASON_WEIGHTS["insufficient_route_evidence"]
        )
        result["risk_score"] = result["risk_score"] + result["home_trace_score"]
        result["risk_reason_summary"] = result.apply(self._merge_daily_reason_summary, axis=1)
        result["risk_rate"] = result["risk_score"] / result["gps_event_count"].clip(lower=1)
        result["risk_level"] = result.apply(self._daily_level, axis=1)
        return result

    def build_employee_risk_summary(self, daily_risk: pd.DataFrame) -> pd.DataFrame:
        if daily_risk.empty:
            return pd.DataFrame(columns=["employee_id", "risk_score", "risk_rate", "review_event_count", "high_risk_event_count"])
        grouped = (
            daily_risk.groupby(["employee_id", "employee_name", "department"], dropna=False)
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
        return grouped.sort_values(["risk_rate", "risk_score"], ascending=[False, False])

    def _build_home_trace_risk(
        self,
        attendance: pd.DataFrame,
        raw_events: pd.DataFrame | None,
        employees: pd.DataFrame | None,
        matches: pd.DataFrame | None,
    ) -> pd.DataFrame:
        columns = [
            "attendance_uid",
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
            "home_near_event_count",
            "max_distance_from_home_m",
            "field_visit_count",
        ]
        if raw_events is None or employees is None or raw_events.empty or employees.empty:
            return pd.DataFrame(columns=columns)
        employee_home = employees.dropna(subset=["home_lat", "home_lon"])[["employee_id", "home_lat", "home_lon"]]
        if employee_home.empty:
            return pd.DataFrame(columns=columns)
        events = raw_events.dropna(subset=["gps_lat", "gps_lon"]).merge(
            attendance[["attendance_uid", "employee_id"]],
            on="attendance_uid",
            how="left",
        )
        events = events.merge(employee_home, on="employee_id", how="left").dropna(subset=["home_lat", "home_lon"])
        if events.empty:
            return pd.DataFrame(columns=columns)
        events["distance_from_home_m"] = events.apply(
            lambda row: haversine_meter(row["gps_lat"], row["gps_lon"], row["home_lat"], row["home_lon"]),
            axis=1,
        )
        events["near_home"] = events["distance_from_home_m"] <= float(self.config.risk_home_radius_m)
        selected_matches = pd.DataFrame(columns=["event_uid", "field_visit_evidence"])
        if matches is not None and not matches.empty:
            selected = matches.loc[matches["is_selected"] == 1].copy()
            selected["beeline_meter"] = pd.to_numeric(selected["beeline_meter"], errors="coerce")
            selected_matches = selected.loc[
                selected["beeline_meter"].le(float(self.config.risk_review_distance_m))
            ][["event_uid"]].drop_duplicates()
            selected_matches["field_visit_evidence"] = 1
        events = events.merge(selected_matches, on="event_uid", how="left")
        events["field_visit_evidence"] = events["field_visit_evidence"].fillna(0).astype(int)
        grouped = (
            events.sort_values(["attendance_uid", "actual_time"])
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
            (grouped["gps_points"] >= 2)
            & grouped["first_near_home"]
            & grouped["last_near_home"]
            & (grouped["field_visit_count"] == 0)
            & (grouped["max_distance_from_home_m"] < float(self.config.risk_home_area_max_distance_m))
        ).astype(int)
        grouped["insufficient_route_evidence"] = (
            (grouped["gps_points"] < 2)
            | ((grouped["max_distance_from_home_m"] < float(self.config.risk_min_field_visit_distance_from_home_m)) & (grouped["field_visit_count"] == 0))
        ).astype(int)
        return grouped[columns]

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
            return "高風險需覆核"
        if row["review_event_count"] > 0 or row.get("home_area_only_trace", 0) or row.get("home_start_end_without_field_trace", 0):
            return "需覆核"
        if row["risk_score"] > 0:
            return "低信心"
        return "正常"

    def _employee_level(self, row: pd.Series) -> str:
        if row["high_risk_event_count"] > 0 or row["home_area_only_days"] > 0 or row["risk_rate"] >= 4:
            return "高風險需覆核"
        if row["review_event_count"] > 0 or row["home_start_end_without_field_days"] > 0 or row["risk_rate"] >= 2:
            return "需覆核"
        if row["risk_score"] > 0:
            return "低信心"
        return "正常"
```

- [ ] **Step 6: Run tests and verify they pass**

Run: `pytest tests/test_risk_service.py -v`

Expected: PASS.

---

### Task 5: Persist Risk Tables in Pipeline and SQLite

**Files:**
- Modify: `db_manager.py`
- Modify: `pipeline.py`

- [ ] **Step 1: Add schema columns/tables**

In `db_manager.py`, add after `route_stop_match`:

```sql
CREATE TABLE IF NOT EXISTS event_risk_review (
    event_uid TEXT PRIMARY KEY,
    attendance_uid TEXT,
    risk_level TEXT,
    risk_score REAL,
    risk_reason_codes TEXT,
    risk_reason_text TEXT,
    selected_distance_m REAL,
    nearest_distance_m REAL,
    distance_gap_m REAL,
    selected_rank INTEGER
);

CREATE TABLE IF NOT EXISTS daily_risk_summary (
    attendance_uid TEXT PRIMARY KEY,
    employee_id TEXT,
    employee_name TEXT,
    department TEXT,
    work_date TEXT,
    gps_event_count INTEGER,
    risk_score REAL,
    risk_rate REAL,
    review_event_count INTEGER,
    high_risk_event_count INTEGER,
    home_area_only_trace INTEGER,
    home_start_end_without_field_trace INTEGER,
    insufficient_route_evidence INTEGER,
    home_near_event_count INTEGER,
    max_distance_from_home_m REAL,
    field_visit_count INTEGER,
    risk_level TEXT,
    risk_reason_summary TEXT
);

CREATE TABLE IF NOT EXISTS employee_risk_summary (
    employee_id TEXT PRIMARY KEY,
    employee_name TEXT,
    department TEXT,
    attendance_days INTEGER,
    gps_event_count INTEGER,
    risk_score REAL,
    risk_rate REAL,
    review_rate REAL,
    review_event_count INTEGER,
    high_risk_event_count INTEGER,
    home_area_only_days INTEGER,
    home_start_end_without_field_days INTEGER,
    insufficient_route_evidence_days INTEGER,
    risk_level TEXT
);
```

- [ ] **Step 2: Wire risk service into pipeline**

In `pipeline.py`, import:

```python
from google_routes_service import load_google_route_cache_detail
from risk_service import RiskService
```

After `daily_metrics = bi_service.build_daily_metrics(...)`, add:

```python
    risk_service = RiskService(config)
    google_route_detail = load_google_route_cache_detail(config.sqlite_path)
    event_risk = risk_service.build_event_risk(raw_events, stop_matches, google_route_detail, finance_result)
    daily_risk = risk_service.build_daily_risk_summary(
        event_risk,
        attendance,
        raw_events=raw_events,
        employees=employees,
        matches=stop_matches,
    )
    employee_risk = risk_service.build_employee_risk_summary(daily_risk)
```

Add these to `result_tables`:

```python
        "event_risk_review": event_risk,
        "daily_risk_summary": daily_risk,
        "employee_risk_summary": employee_risk,
```

Add these to the SQLite replace list:

```python
            "event_risk_review",
            "daily_risk_summary",
            "employee_risk_summary",
```

- [ ] **Step 3: Run pipeline smoke test**

Run: `python pipeline.py`

Expected: completes and writes:

- `outputs/cleaned/event_risk_review.csv`
- `outputs/cleaned/daily_risk_summary.csv`
- `outputs/cleaned/employee_risk_summary.csv`

---

### Task 6: Load Risk Tables in App Data Context

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add safe CSV loading**

Where cleaned CSVs are loaded in `app.py`, add:

```python
    event_risk = read_cleaned_csv("event_risk_review.csv")
    daily_risk = read_cleaned_csv("daily_risk_summary.csv")
    employee_risk = read_cleaned_csv("employee_risk_summary.csv")
```

If the app uses direct `pd.read_csv` calls instead of `read_cleaned_csv`, use the existing local loading helper and return empty DataFrames with the expected columns when files are missing.

- [ ] **Step 2: Merge event risk onto `raw_events`**

After nearest/selected match fields are merged onto `raw_events`, add:

```python
    if not event_risk.empty:
        raw_events = raw_events.merge(
            event_risk[
                [
                    "event_uid",
                    "risk_level",
                    "risk_score",
                    "risk_reason_codes",
                    "risk_reason_text",
                    "selected_distance_m",
                    "nearest_distance_m",
                    "distance_gap_m",
                    "selected_rank",
                ]
            ],
            on="event_uid",
            how="left",
        )
```

- [ ] **Step 3: Return risk tables in the loaded data dict**

Add:

```python
        "event_risk": event_risk,
        "daily_risk": daily_risk,
        "employee_risk": employee_risk,
```

- [ ] **Step 4: Run app import smoke test**

Run: `python -m py_compile app.py`

Expected: no syntax errors.

---

### Task 7: Apply Risk to Daily Report

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Candidate card risk badge**

In `build_candidate_panel`, include from `day_events`:

```python
                "risk_level",
                "risk_score",
                "risk_reason_text",
```

Add these keys to each panel:

```python
                "risk_level": first_row.get("risk_level", "正常"),
                "risk_score": float(first_row["risk_score"]) if pd.notna(first_row.get("risk_score")) else 0.0,
                "risk_reason_text": first_row.get("risk_reason_text", ""),
```

In `render_candidate_cards`, render:

```python
            risk_text = panel.get("risk_level") or "正常"
            risk_reason = panel.get("risk_reason_text") or ""
            risk_html = f'<div class="candidate-sub">覆核狀態：{risk_text}</div>'
            if risk_reason:
                risk_html += f'<div class="candidate-sub">原因：{risk_reason}</div>'
```

Insert `risk_html` below system selected text.

- [ ] **Step 2: Daily event detail columns**

In the daily event detail DataFrame, add:

```python
            "risk_level",
            "risk_reason_text",
```

Rename to:

```python
            "risk_level": "覆核狀態",
            "risk_reason_text": "覆核原因",
```

Include `"覆核狀態"` and `"覆核原因"` in the printed table.

- [ ] **Step 3: Run compile check**

Run: `python -m py_compile app.py`

Expected: no syntax errors.

---

### Task 8: Apply Risk to Weekly Report

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add risk summary to weekly cards**

In `build_weekly_summary_cards`, aggregate `day_events` risk fields by date:

```python
        risk_counts = selected["risk_level"].fillna("正常").value_counts().to_dict() if "risk_level" in selected.columns else {}
        review_count = int(sum(risk_counts.get(level, 0) for level in ["需覆核", "高風險需覆核"]))
```

Add to each card:

```python
                "review_count": review_count,
                "risk_counts": risk_counts,
```

- [ ] **Step 2: Render weekly risk summary**

In `render_weekly_summary_cards`, add:

```python
            <div class="candidate-sub">覆核點數：{card.get('review_count', 0)}</div>
```

Keep the weekly map unchanged in this implementation pass; color-by-risk map styling belongs in a separate UI polish change after the shared data model is stable.

- [ ] **Step 3: Run compile check**

Run: `python -m py_compile app.py`

Expected: no syntax errors.

---

### Task 9: Apply Risk to Personal Period Report

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Merge daily risk into personal detail builder**

In `build_period_report`, merge `daily_risk` by `attendance_uid`, or if the function only receives a merged frame, ensure callers merge these columns before calling:

```python
        "risk_score",
        "risk_rate",
        "review_event_count",
        "high_risk_event_count",
        "home_area_only_trace",
        "home_start_end_without_field_trace",
        "insufficient_route_evidence",
        "home_near_event_count",
        "max_distance_from_home_m",
        "field_visit_count",
        "risk_level",
        "risk_reason_summary",
```

- [ ] **Step 2: Add period summary metrics**

Add to the one-row summary:

```python
                "覆核點數": int(merged["review_event_count"].fillna(0).sum()),
                "高風險點數": int(merged["high_risk_event_count"].fillna(0).sum()),
                "僅住家附近軌跡天數": int(merged["home_area_only_trace"].fillna(0).sum()),
                "住家起訖但缺外勤軌跡天數": int(merged["home_start_end_without_field_trace"].fillna(0).sum()),
                "風險分數": round(float(merged["risk_score"].fillna(0).sum()), 2),
                "平均風險率": round(float(merged["risk_rate"].fillna(0).mean()), 4),
```

- [ ] **Step 3: Add daily detail columns**

Add to the detail table:

```python
            "review_event_count",
            "high_risk_event_count",
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
            "home_near_event_count",
            "max_distance_from_home_m",
            "field_visit_count",
            "risk_score",
            "risk_level",
            "risk_reason_summary",
```

Rename to:

```python
            "review_event_count": "需覆核點數",
            "high_risk_event_count": "高風險點數",
            "home_area_only_trace": "僅住家附近軌跡",
            "home_start_end_without_field_trace": "住家起訖但缺外勤軌跡",
            "insufficient_route_evidence": "軌跡證據不足",
            "home_near_event_count": "住家附近打卡點數",
            "max_distance_from_home_m": "距住家最遠距離(m)",
            "field_visit_count": "外勤軌跡佐證點數",
            "risk_score": "風險分數",
            "risk_level": "覆核狀態",
            "risk_reason_summary": "覆核原因代碼",
```

- [ ] **Step 4: Run compile check**

Run: `python -m py_compile app.py`

Expected: no syntax errors.

---

### Task 10: Apply Risk to All-Employee Overview

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Pass daily risk into overview summary**

Change signature:

```python
def build_overview_summary(
    attendance: pd.DataFrame,
    daily_metrics: pd.DataFrame,
    routes: pd.DataFrame,
    finance: pd.DataFrame,
    event_flags: pd.DataFrame,
    daily_risk: pd.DataFrame,
    start_date,
    end_date,
) -> pd.DataFrame:
```

At the call site, pass `daily_risk`.

- [ ] **Step 2: Aggregate risk by employee**

Inside `build_overview_summary`, after the base merged daily frame is prepared:

```python
    if not daily_risk.empty:
        merged = merged.merge(
            daily_risk[
                [
                    "attendance_uid",
                    "risk_score",
                    "risk_rate",
                    "review_event_count",
                    "high_risk_event_count",
                    "home_area_only_trace",
                    "home_start_end_without_field_trace",
                    "insufficient_route_evidence",
                    "risk_level",
                    "risk_reason_summary",
                ]
            ],
            on="attendance_uid",
            how="left",
        )
```

In the employee aggregation, add:

```python
                風險分數=("risk_score", lambda s: round(pd.to_numeric(s, errors="coerce").fillna(0).sum(), 2)),
                需覆核點數=("review_event_count", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
                高風險點數=("high_risk_event_count", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
                僅住家附近軌跡天數=("home_area_only_trace", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
                住家起訖但缺外勤軌跡天數=("home_start_end_without_field_trace", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
                軌跡證據不足天數=("insufficient_route_evidence", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
```

After aggregation:

```python
    summary["風險率"] = summary["風險分數"] / summary["總GPS點數"].clip(lower=1)
    summary = summary.sort_values(["風險率", "風險分數"], ascending=[False, False])
```

- [ ] **Step 3: Update overview charts and detail table**

Add a new chart block before finance subsidy:

```python
        st.markdown("**覆核優先排序**")
        fig_risk = px.bar(
            overview_summary.sort_values("風險率", ascending=False),
            x="employee_label",
            y="風險率",
            color="department",
            text_auto=".2f",
            labels={"employee_label": "員工", "風險率": "風險率", "department": "部門"},
        )
        st.plotly_chart(fig_risk, width="stretch")
```

Add to `render_print_table` and dataframe columns:

```python
            "風險分數",
            "風險率",
            "需覆核點數",
            "高風險點數",
            "僅住家附近軌跡天數",
            "住家起訖但缺外勤軌跡天數",
            "軌跡證據不足天數",
```

- [ ] **Step 4: Run compile check**

Run: `python -m py_compile app.py`

Expected: no syntax errors.

---

### Task 11: Apply Risk to Google Sheet Export

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Include risk fields in daily export**

In `build_google_sheet_reference_payload`, merge `daily_risk` into `daily_export` by `attendance_uid` and include:

```python
            "risk_level",
            "risk_score",
            "review_event_count",
            "high_risk_event_count",
            "home_area_only_trace",
            "home_start_end_without_field_trace",
            "insufficient_route_evidence",
            "home_near_event_count",
            "max_distance_from_home_m",
            "field_visit_count",
            "risk_reason_summary",
```

Rename to:

```python
            "risk_level": "覆核狀態",
            "risk_score": "風險分數",
            "review_event_count": "需覆核點數",
            "high_risk_event_count": "高風險點數",
            "home_area_only_trace": "僅住家附近軌跡",
            "home_start_end_without_field_trace": "住家起訖但缺外勤軌跡",
            "insufficient_route_evidence": "軌跡證據不足",
            "home_near_event_count": "住家附近打卡點數",
            "max_distance_from_home_m": "距住家最遠距離(m)",
            "field_visit_count": "外勤軌跡佐證點數",
            "risk_reason_summary": "覆核原因代碼",
```

- [ ] **Step 2: Include event-level risk fields in detail sheet**

In `detail_sheet`, include:

```python
            "risk_level",
            "risk_reason_text",
            "selected_rank",
            "distance_gap_m",
```

Rename to:

```python
            "risk_level": "覆核狀態",
            "risk_reason_text": "覆核原因",
            "selected_rank": "系統選定候選排名",
            "distance_gap_m": "選定與最近距離差(m)",
```

- [ ] **Step 3: Update instruction rows**

Add:

```python
        ["覆核狀態", "標示低信心、需覆核或高風險需覆核的打卡點與每日彙總。", "此欄為人工覆核優先順序，不代表員工違規。"],
        ["住家附近軌跡", "標示整天是否缺少離家外勤軌跡佐證。", "上下班在家附近可接受；僅在缺少中間外勤佐證時列入覆核。"],
```

- [ ] **Step 4: Run compile check**

Run: `python -m py_compile app.py`

Expected: no syntax errors.

---

### Task 12: Documentation and Final Verification

**Files:**
- Modify: `METRICS_GUIDE.md`
- Test: full local verification

- [ ] **Step 1: Document terminology**

Add a section:

```markdown
### 覆核狀態與風險分數

覆核狀態用於排序人工檢查優先順序，不等同於員工違規判定。

- `正常`：系統選定結果與距離資訊一致。
- `低信心`：候選過近、過密或資訊不足。
- `需覆核`：系統選定結果與距離或候選排名明顯衝突。
- `異常風險`：時間、路線或申報資料有明顯不合理訊號。
- `高風險需覆核`：同一天或同員工期間累積多個高權重訊號。

住家附近軌跡規則：

- 允許：第一點或最後一點在住家附近，且中間有合理醫院/客戶拜訪軌跡。
- 需覆核：整天 GPS 點都在住家半徑內，且沒有合理外勤候選點。
- 需覆核：上下班都在住家附近，但中間沒有離家外勤軌跡佐證。
- 高風險需覆核：住家附近軌跡不足同時伴隨明顯申報里程、日當或財務紅燈。
```

- [ ] **Step 2: Run unit tests**

Run: `pytest -v`

Expected: all tests pass.

- [ ] **Step 3: Run pipeline**

Run: `python pipeline.py`

Expected: no exception and cleaned risk CSVs are generated.

- [ ] **Step 4: Run app syntax checks**

Run: `python -m py_compile app.py pipeline.py risk_service.py settings.py db_manager.py`

Expected: no syntax errors.

- [ ] **Step 5: Start Streamlit and manually verify report touchpoints**

Run: `streamlit run app.py`

Expected:

- Daily report candidate card shows `覆核狀態` and reason for the 2.4km existing-client case.
- Weekly report daily cards show review counts.
- Personal period report shows risk score, risk rate, review counts, and daily risk detail.
- All-employee overview ranks employees by normalized risk rate.
- Google Sheet export includes daily and event-level review fields.

---

### Task 13: Claim Granularity Safeguards

**Files:**
- Modify: `app.py`
- Modify: `METRICS_GUIDE.md`
- Optional Modify: `finance_auditor.py`

- [ ] **Step 1: Keep monthly claim comparison month-level**

Verify `build_monthly_claim_comparison` still aggregates:

```python
route_monthly = (
    route_monthly.dropna(subset=["employee_id", "year_month"])
    .groupby(["employee_id", "employee_label", "department", "year_month"], dropna=False, as_index=False)["estimated_business_km"]
    .sum()
)
```

Expected: monthly claim comparison remains `claimed_km` vs monthly sum of `estimated_business_km`.

- [ ] **Step 2: Rename daily finance display columns to avoid daily/month confusion**

In the daily finance tab and personal period finance detail, replace the display name:

```python
"employee_claim_km": "月申請里程"
```

with:

```python
"employee_claim_km": "所屬月份申請總里程"
```

Keep:

```python
"approved_business_km": "當日公務里程"
```

Add a caption near those tables:

```python
st.caption("申請里程目前為整月匯入值；此表逐日顯示時會重複呈現同一月份申請總里程，不代表該日申請里程。")
```

- [ ] **Step 3: Keep risk scoring from using monthly claim as event evidence**

In `risk_service.py`, do not add `high_finance_variance` inside `_score_event` from monthly data. If using monthly finance data, add it only during employee/month or employee-period aggregation, or include it in daily summaries with reason text explicitly saying `所屬月份財務差異`.

- [ ] **Step 4: Reserve future daily claim import contract**

Document future `daily_claims.csv` columns in `METRICS_GUIDE.md`:

```markdown
### `daily_claims.csv`（預留）
- `work_date`
- `employee_id`
- `claimed_km`
- `claim_source`
- `submitted_at`
- `remark`

每日申報里程匯入後，才能進行 `日申報里程 vs 當日公務里程` 的日層級比對。月申報里程仍維持月層級比對。
```

- [ ] **Step 5: Future daily-claim risk reason codes**

Reserve these reason codes for a later implementation, but do not activate them until daily claim import exists:

```python
"daily_claim_variance_high": 5
"daily_claim_without_route_evidence": 6
"home_trace_with_daily_claim": 7
```

Expected behavior after future daily claim import:

- `daily_claim_variance_high`: daily claimed km differs materially from daily estimated business km.
- `daily_claim_without_route_evidence`: daily claim exists but GPS/route evidence is insufficient.
- `home_trace_with_daily_claim`: day is home-area-only but has non-trivial daily claimed mileage.

---

## Self-Review

- Spec coverage: The plan covers shared rules, event flags, daily home-area trace safeguards, claim granularity safeguards, daily summaries, employee ranking, daily report, weekly report, personal report, all-employee overview, and export.
- Placeholder scan: No `TBD`, `TODO`, or unresolved implementation placeholders remain.
- Type consistency: Risk fields use stable names across pipeline, app, and export: `risk_level`, `risk_score`, `risk_reason_codes`, `risk_reason_text`, `review_event_count`, `high_risk_event_count`, `risk_rate`, `home_area_only_trace`, `home_start_end_without_field_trace`, and `insufficient_route_evidence`.
- Scope check: First version intentionally does not alter the selected hospital algorithm. It adds review detection around the current output so report behavior changes are auditable before selection behavior changes.
