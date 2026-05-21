from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from db_manager import DatabaseManager
from google_routes_service import (
    add_route_cache_diagnostic_flags,
    load_route_segment_exclusions,
    upsert_route_segment_exclusions,
    upsert_summary_rows,
)


class RouteSegmentExclusionTests(unittest.TestCase):
    def test_excluded_segments_reduce_summary_but_keep_raw_distance(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            db_path = Path(tmp_dir) / "routes.db"
            db = DatabaseManager(db_path)
            db.initialize()

            attendance = pd.DataFrame(
                [
                    {
                        "attendance_uid": "WS09_2026-04-10_100_latest_attendance",
                        "attendance_key": "WS09_2026-04-10_100",
                        "employee_id": "WS09",
                    }
                ]
            )
            employees = pd.DataFrame(
                [
                    {
                        "employee_id": "WS09",
                        "base_commute_km": 0,
                    }
                ]
            )
            segment_rows = [
                {
                    "cache_key": "home-to-first",
                    "attendance_uid": "WS09_2026-04-10_100_latest_attendance",
                    "attendance_key": "WS09_2026-04-10_100",
                    "segment_no": 1,
                    "segment_type": "home_to_first",
                    "distance_meters": 340_000,
                    "duration_seconds": 14_400,
                    "source": "cache",
                },
                {
                    "cache_key": "between-points",
                    "attendance_uid": "WS09_2026-04-10_100_latest_attendance",
                    "attendance_key": "WS09_2026-04-10_100",
                    "segment_no": 2,
                    "segment_type": "between_points",
                    "distance_meters": 8_000,
                    "duration_seconds": 1_200,
                    "source": "cache",
                },
                {
                    "cache_key": "last-to-home",
                    "attendance_uid": "WS09_2026-04-10_100_latest_attendance",
                    "attendance_key": "WS09_2026-04-10_100",
                    "segment_no": 3,
                    "segment_type": "last_to_home",
                    "distance_meters": 340_000,
                    "duration_seconds": 14_400,
                    "source": "cache",
                },
            ]

            upsert_route_segment_exclusions(
                db_path,
                [
                    {
                        "cache_key": "home-to-first",
                        "attendance_uid": "WS09_2026-04-10_100_latest_attendance",
                        "attendance_key": "WS09_2026-04-10_100",
                        "segment_no": 1,
                        "segment_type": "home_to_first",
                        "exclude_from_mileage": True,
                        "exclude_reason": "高鐵/公共運輸",
                        "exclude_note": "高雄到基隆總公司搭高鐵",
                        "updated_by": "unit-test",
                    }
                ],
            )

            with db.connect() as conn:
                summary = upsert_summary_rows(conn, attendance, employees, segment_rows)
                conn.commit()

            self.assertEqual(load_route_segment_exclusions(db_path).shape[0], 1)
            row = summary.iloc[0]
            self.assertEqual(row["raw_estimated_total_km"], 688.0)
            self.assertEqual(row["excluded_km"], 340.0)
            self.assertEqual(row["estimated_total_km"], 348.0)
            self.assertEqual(row["estimated_business_km"], 348.0)
            self.assertIn("manual_exclusion", row["route_notes"])

    def test_api_provider_cache_rows_count_as_api_success_for_diagnostics(self) -> None:
        cache_detail = pd.DataFrame(
            [
                {
                    "status": "ok",
                    "polyline": "encoded-route",
                    "api_provider": "google_routes_api",
                },
                {
                    "status": "ok",
                    "polyline": "legacy-route",
                    "api_provider": "legacy_cache",
                },
                {
                    "status": "ok",
                    "polyline": "",
                    "api_provider": "google_routes_api",
                },
            ]
        )

        diagnostics = add_route_cache_diagnostic_flags(cache_detail)

        self.assertEqual(int(diagnostics["is_api_success"].sum()), 1)
        self.assertEqual(int(diagnostics["is_cache_success"].sum()), 1)
        self.assertEqual(int(diagnostics["is_missing_polyline"].sum()), 1)


if __name__ == "__main__":
    unittest.main()
