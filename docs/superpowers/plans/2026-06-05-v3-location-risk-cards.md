# V3 Location Risk Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement v3 mutually exclusive GPS point classification, risk/review scoring, and daily/weekly card presentation for home risk, existing-client visits, and unknown field points.

**Architecture:** Keep `matcher.py` as the candidate generator and move final visit classification into `risk_service.py`, where employee home distance and match candidates are both available. Persist classification and candidate summary fields in `event_risk_review`, merge them into `raw_events`, then render daily and weekly cards from those enriched event rows. Preserve legacy columns where practical while adding `review_score` and formula-based `risk_priority_score`.

**Reviewer Notes:** Do not rely on `matcher.py`'s legacy `is_selected` as the final business decision; use the v3 `selected_visit_*` fields from `risk_service.py` for daily/weekly UI and exports. The 0-check-in daily rule can only apply when an `attendance_day_group` row exists with `event_count = 0`; this plan will support that case without inventing missing attendance rows.

**Tech Stack:** Python, pandas, SQLite, Streamlit, pytest.

---

### Task 1: Lock V3 Event Classification In Tests

**Files:**
- Modify: `tests/test_risk_service.py`
- Modify: `risk_service.py`

- [ ] **Step 1: Write failing tests for the mutually exclusive event classes**

Add tests that call `RiskService(make_config()).build_event_risk(...)` and assert:

```python
def test_v3_home_core_short_circuits_existing_client_match() -> None:
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.7000, "gps_lon": 121.7700}])
    employees = pd.DataFrame([{"employee_id": "A", "home_lat": 24.7001, "home_lon": 121.7701}])
    matches = pd.DataFrame([
        {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 1, "hospital_label": "近家既有客戶", "beeline_meter": 50.0, "is_existing_client": 1, "is_hospital_facility": 0},
    ])

    result = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame(), employees=employees)
    row = result.iloc[0]

    assert row["location_class"] == "home_core"
    assert row["selected_visit_type"] == "極近居家點"
    assert row["selected_visit_name"] == "極近居家點"
    assert row["risk_score"] == 3
    assert row["review_score"] == 0
```

```python
def test_v3_existing_client_visit_binds_nearest_client_within_1000m() -> None:
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.72, "gps_lon": 121.79}])
    employees = pd.DataFrame([{"employee_id": "A", "home_lat": 24.7000, "home_lon": 121.7700}])
    matches = pd.DataFrame([
        {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 1, "hospital_label": "潛在院所", "beeline_meter": 90.0, "is_existing_client": 0, "is_hospital_facility": 1},
        {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 2, "hospital_label": "既有A", "beeline_meter": 800.0, "is_existing_client": 1, "is_hospital_facility": 0},
        {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 3, "hospital_label": "既有B", "beeline_meter": 950.0, "is_existing_client": 1, "is_hospital_facility": 0},
    ])

    row = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame(), employees=employees).iloc[0]

    assert row["location_class"] == "existing_client_visit"
    assert row["selected_visit_name"] == "既有A"
    assert row["selected_visit_type"] == "既有客戶"
    assert row["risk_score"] == 0
    assert row["review_score"] == 0
    assert "既有A" in row["existing_client_candidates_top3"]
```

```python
def test_v3_home_edge_applies_after_no_existing_client_within_1000m() -> None:
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.7040, "gps_lon": 121.7700}])
    employees = pd.DataFrame([{"employee_id": "A", "home_lat": 24.7000, "home_lon": 121.7700}])
    matches = pd.DataFrame([
        {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 1, "hospital_label": "遠既有", "beeline_meter": 1300.0, "is_existing_client": 1, "is_hospital_facility": 0},
    ])

    row = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame(), employees=employees).iloc[0]

    assert row["location_class"] == "home_edge"
    assert row["selected_visit_type"] == "邊緣居家點"
    assert row["risk_score"] == 1
    assert row["review_score"] == 0
```

```python
def test_v3_unknown_field_does_not_hard_select_customer_and_suggests_prospects() -> None:
    raw_events = pd.DataFrame([{"event_uid": "e1", "attendance_uid": "a1", "employee_id": "A", "gps_lat": 24.90, "gps_lon": 121.20}])
    employees = pd.DataFrame([{"employee_id": "A", "home_lat": 24.7000, "home_lon": 121.7700}])
    matches = pd.DataFrame([
        {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 1, "hospital_label": "潛在A", "beeline_meter": 120.0, "is_existing_client": 0, "is_hospital_facility": 1},
        {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 2, "hospital_label": "潛在B", "beeline_meter": 260.0, "is_existing_client": 0, "is_hospital_facility": 1},
        {"event_uid": "e1", "attendance_uid": "a1", "candidate_rank": 3, "hospital_label": "遠既有", "beeline_meter": 1600.0, "is_existing_client": 1, "is_hospital_facility": 0},
    ])

    row = RiskService(make_config()).build_event_risk(raw_events, matches, pd.DataFrame(), pd.DataFrame(), employees=employees).iloc[0]

    assert row["location_class"] == "unknown_field"
    assert row["selected_visit_name"] == "未知外勤點"
    assert row["selected_visit_type"] == "未知外勤點"
    assert row["risk_score"] == 0
    assert row["review_score"] == 4
    assert "潛在A" in row["suggested_prospects_top3"]
    assert row["nearest_existing_client_name"] == "遠既有"
```

- [ ] **Step 2: Run tests to verify red**

Run: `py -3 -m pytest tests/test_risk_service.py -q`

Expected: FAIL because `location_class`, `review_score`, and the candidate summary fields do not exist.

### Task 2: Implement V3 Event Classification And Scores

**Files:**
- Modify: `risk_service.py`
- Modify: `settings.py`

- [ ] **Step 1: Add settings**

Add defaults to `AppConfig`:

```python
v3_existing_client_radius_m: float = 1000.0
v3_unknown_prospect_radius_m: float = 500.0
```

Add both to `CONFIG_OVERRIDE_FIELDS` and `_coerce_override` float fields.

- [ ] **Step 2: Extend event output columns**

Add to `EVENT_RISK_COLUMNS` after `risk_score`:

```python
"review_score",
"priority_score",
```

Add to the end:

```python
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
```

- [ ] **Step 3: Add helper functions**

Implement helpers in `RiskService`:

```python
@staticmethod
def _format_candidate_summary(rows: pd.DataFrame, name_col: str = "hospital_label") -> str:
    if rows.empty:
        return ""
    return "; ".join(
        f"{str(row.get(name_col) or '未知院所')} {float(row['beeline_meter']):.0f}m"
        for _, row in rows.iterrows()
    )

@staticmethod
def _home_distance_bucket(distance_from_home: float | None) -> str:
    if distance_from_home is None:
        return ""
    if distance_from_home <= 100:
        return "100公尺內"
    if distance_from_home <= 500:
        return "101~500公尺"
    if distance_from_home <= 1000:
        return "501~1000公尺"
    return f"{distance_from_home:.0f}m"
```

Add a classifier helper that receives `distance_from_home` and cleaned `candidates`, and returns a dict containing the fields in Step 2.

- [ ] **Step 4: Replace `_score_event` selection logic**

Use this exact order:

1. `distance_from_home <= 100`: `location_class = "home_core"`, `risk_score = 3`, `review_score = 0`.
2. Else nearest existing client with `beeline_meter <= v3_existing_client_radius_m`: `location_class = "existing_client_visit"`, `risk_score = 0`, `review_score = 0`.
3. Else `100 < distance_from_home <= 1000`: `location_class = "home_edge"`, `risk_score = 1`, `review_score = 0`.
4. Else `location_class = "unknown_field"`, `risk_score = 0`, `review_score = 4`.

Compute `priority_score = risk_score * 3 + review_score`.

Keep `impossible_travel_time` as an additive high-risk reason for now: add its existing risk score and include it in `risk_reason_codes`.

- [ ] **Step 5: Run tests to verify green**

Run: `py -3 -m pytest tests/test_risk_service.py -q`

Expected: PASS after updating old expectations that referenced `confidence_score` for customer override or `selected_distance_too_far`.

### Task 3: Persist And Load New Event Fields

**Files:**
- Modify: `db_manager.py`
- Modify: `tests/test_db_manager_schema.py`
- Modify: `app.py`

- [ ] **Step 1: Update schema tests**

Add new `event_risk_review` columns in `tests/test_db_manager_schema.py` matching `EVENT_RISK_COLUMNS`.

- [ ] **Step 2: Update SQLite schema and migration**

Add columns to `event_risk_review`:

```sql
review_score REAL,
priority_score REAL,
location_class TEXT,
selected_visit_name TEXT,
selected_visit_type TEXT,
selected_visit_distance_m REAL,
home_distance_bucket TEXT,
existing_client_candidates_top3 TEXT,
suggested_prospects_top3 TEXT,
nearest_existing_client_name TEXT,
nearest_existing_client_distance_m REAL,
nearest_hospital_name TEXT,
nearest_hospital_distance_m REAL
```

Add `_ensure_column` calls for each.

- [ ] **Step 3: Update app loaders and raw event merge**

In `app.py`, add these fields to:

- `event_risk_columns` in `load_results()`
- `event_risk_numeric_columns` for numeric fields
- `event_risk_merge_columns`
- PDF/context `event_risk_columns`

After merging event risk into `raw_events`, set display-facing columns from v3 fields when present:

```python
raw_events["selected_hospital_name"] = raw_events["selected_visit_name"].combine_first(raw_events.get("selected_hospital_name"))
raw_events["selected_client_tag"] = raw_events["selected_visit_type"].combine_first(raw_events.get("selected_client_tag"))
```

For unknown field rows this makes the system-selected record display as `未知外勤點`, even though raw match candidates remain available for evidence panels.

- [ ] **Step 4: Run schema and loader-adjacent tests**

Run: `py -3 -m pytest tests/test_db_manager_schema.py tests/test_risk_service.py -q`

Expected: PASS.

### Task 4: Update Daily Card Presentation

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add daily card data builder helpers**

Add helper functions near `build_candidate_panel`:

```python
def split_semicolon_summary(value: object) -> list[str]:
    text = str(value or "").strip()
    return [part.strip() for part in text.split(";") if part.strip()]

def home_risk_text(panel: dict) -> str:
    bucket = panel.get("home_distance_bucket") or "無住家距離"
    home_only = "是" if panel.get("home_area_only_trace") else "否"
    return f"距家：{bucket}；當天只有在家附近打卡：{home_only}"
```

Thread `home_area_only_trace` from day-level `daily_risk` into event panels by merging on `attendance_uid`.

- [ ] **Step 2: Change `build_candidate_panel` output**

Panel dict should include:

```python
"location_class",
"selected_visit_name",
"selected_visit_type",
"selected_visit_distance_m",
"home_distance_bucket",
"existing_client_candidates": split_semicolon_summary(first_row["existing_client_candidates_top3"]),
"suggested_prospects": split_semicolon_summary(first_row["suggested_prospects_top3"]),
"nearest_existing_client_name",
"nearest_existing_client_distance_m",
"nearest_hospital_name",
"nearest_hospital_distance_m",
```

- [ ] **Step 3: Change `render_candidate_cards` layout**

Render three labelled blocks per card:

```text
居家風險
- 距家：100公尺內 / 101~500公尺 / 501~1000公尺 / actual distance
- 當天只有在家附近打卡：是/否

既有客戶拜訪
- 系統綁定：既有客戶名 + distance, or 無
- 既有客戶候選 Top3：...

未知外勤點判定
- 系統選定：未知外勤點 or 不適用
- 潛在院所 Top3：...
- 最近既有客戶：...
- 最近醫院：...
```

Keep existing candidate expander for raw candidate details.

- [ ] **Step 4: Run app syntax/import tests**

Run: `py -3 -m pytest tests/test_demo_data_generator.py tests/test_risk_presentation.py -q`

Expected: PASS.

### Task 5: Update Weekly Summary Presentation

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add weekly aggregation helpers**

Near weekly helpers add:

```python
def count_home_near_events(events: pd.DataFrame) -> int:
    return int(events["location_class"].isin(["home_core", "home_edge"]).sum()) if "location_class" in events.columns else 0

def count_home_only_days(daily_risk: pd.DataFrame) -> int:
    return int(pd.to_numeric(daily_risk.get("home_area_only_trace", pd.Series(dtype=float)), errors="coerce").fillna(0).gt(0).sum())
```

Add helpers to aggregate selected existing clients and unknown field prospects from `selected_visit_*` and `suggested_prospects_top3`.

- [ ] **Step 2: Update `build_weekly_summary_cards`**

Each day card should carry:

```python
"home_near_event_count"
"home_only_day"
"existing_client_visits"
"unknown_field_count"
"unknown_prospect_mentions"
```

Also compute week-level totals before rendering top band:

```python
weekly_home_1000m_count = sum(card["home_near_event_count"] for card in weekly_cards)
weekly_home_only_days = sum(1 for card in weekly_cards if card["home_only_day"])
weekly_unknown_field_count = sum(card["unknown_field_count"] for card in weekly_cards)
```

- [ ] **Step 3: Update `render_weekly_summary_cards`**

Render each card with three sections:

1. 居家風險: 1000m 內打卡次數, 是否只有在家附近打卡.
2. 既有客戶拜訪: client name and count.
3. 未知外勤點: count and potential prospect mentions.

- [ ] **Step 4: Update weekly top metrics**

Replace the current low-confidence-oriented weekly metric with:

```text
住家1000m內打卡
只有在家附近天數
未知外勤點
風險/覆核優先分
```

- [ ] **Step 5: Run focused tests**

Run: `py -3 -m pytest tests/test_map_presentation.py tests/test_risk_presentation.py -q`

Expected: PASS.

### Task 6: Convert Daily Scores To V3 Risk/Review/Priority Model

**Files:**
- Modify: `risk_service.py`
- Modify: `tests/test_risk_service.py`
- Modify: `risk_presentation.py`
- Modify: `app.py`
- Modify: `db_manager.py`

- [ ] **Step 1: Write failing daily score tests**

Add tests that assert:

```python
assert row["risk_score"] == expected_risk
assert row["review_score"] == expected_review
assert row["risk_priority_score"] == row["risk_score"] * 3 + row["review_score"] + row["priority_bonus"]
```

Cover:

- 0 check-ins: Risk 10, Review 10
- 1 check-in: Risk 5, Review 12
- short span: Risk 4, Review 5
- long span: Risk 0, Review 5
- home only day: priority bonus 24
- home start/end masking: priority bonus 6

- [ ] **Step 2: Implement daily `review_score` and `priority_bonus`**

Add daily columns:

```python
"review_score",
"priority_bonus",
```

Set daily totals:

```python
result["review_score"] = event_review_sum + attendance_review + long_span_review
result["priority_bonus"] = home_only * 24 + home_start_end * 6
result["risk_priority_score"] = result["risk_score"] * 3 + result["review_score"] + result["priority_bonus"]
```

- [ ] **Step 3: Preserve compatibility**

Keep `confidence_score` populated as an alias for review-ish/uncertainty data during transition:

```python
result["confidence_score"] = result["review_score"]
```

Do not remove existing `risk_priority_rate`, `risk_rate`, or `review_event_count`.

- [ ] **Step 4: Update schema/app columns**

Add `review_score` and `priority_bonus` to daily and employee tables and app loaders.

- [ ] **Step 5: Run risk and schema tests**

Run: `py -3 -m pytest tests/test_risk_service.py tests/test_db_manager_schema.py -q`

Expected: PASS.

### Task 7: Full Verification

**Files:**
- No code changes unless tests reveal gaps.

- [ ] **Step 1: Run full test suite**

Run: `py -3 -m pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run static diff checks**

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 3: Review final diff manually**

Run:

```powershell
git diff --stat
git diff -- risk_service.py matcher.py app.py db_manager.py settings.py risk_presentation.py
```

Expected: changes are limited to v3 matching/scoring/presentation, with no unrelated refactors.
