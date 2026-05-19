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
