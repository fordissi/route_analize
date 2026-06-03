from __future__ import annotations

import pandas as pd

from matcher import Matcher


def test_near_hospital_beats_far_existing_client_for_system_selection() -> None:
    raw_events = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "employee_id": "A",
                "work_date": "2026-03-11",
                "group_no": 1,
                "actual_time": "2026-03-11 09:29:03",
                "source_row_no": 1,
                "gps_lat": 22.781080,
                "gps_lon": 120.416758,
            }
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "work_date": "2026-03-11",
                "group_no": 1,
            }
        ]
    )
    hospitals = pd.DataFrame(
        [
            {
                "hospital_id": "near_hospital",
                "hospital_name": "燕巢靜和醫療社團法人燕巢靜和醫院",
                "lat": 22.781650,
                "lon": 120.416758,
            },
            {
                "hospital_id": "far_existing",
                "hospital_name": "義大醫療財團法人義大癌治療醫院",
                "lat": 22.831080,
                "lon": 120.416758,
            },
        ]
    )
    clients = pd.DataFrame([{"hospital_id": "far_existing"}])

    result = Matcher(top_n=2).build_matches(raw_events, attendance, hospitals, clients)
    selected = result.loc[result["is_selected"] == 1].iloc[0]

    assert selected["hospital_id"] == "near_hospital"
    assert selected["selection_type"] == "醫院"


def test_near_existing_client_keeps_priority_over_hospital() -> None:
    raw_events = pd.DataFrame(
        [
            {
                "event_uid": "e1",
                "attendance_uid": "a1",
                "employee_id": "A",
                "work_date": "2026-03-11",
                "group_no": 1,
                "actual_time": "2026-03-11 09:29:03",
                "source_row_no": 1,
                "gps_lat": 22.781080,
                "gps_lon": 120.416758,
            }
        ]
    )
    attendance = pd.DataFrame(
        [
            {
                "attendance_uid": "a1",
                "employee_id": "A",
                "work_date": "2026-03-11",
                "group_no": 1,
            }
        ]
    )
    hospitals = pd.DataFrame(
        [
            {
                "hospital_id": "near_hospital",
                "hospital_name": "燕巢靜和醫療社團法人燕巢靜和醫院",
                "lat": 22.781650,
                "lon": 120.416758,
            },
            {
                "hospital_id": "near_existing",
                "hospital_name": "既有客戶院所",
                "lat": 22.781900,
                "lon": 120.416758,
            },
        ]
    )
    clients = pd.DataFrame([{"hospital_id": "near_existing"}])

    result = Matcher(top_n=2).build_matches(raw_events, attendance, hospitals, clients)
    selected = result.loc[result["is_selected"] == 1].iloc[0]

    assert selected["hospital_id"] == "near_existing"
    assert selected["selection_type"] == "既有客戶"
