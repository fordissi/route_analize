from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(slots=True)
class AppConfig:
    root_dir: Path
    data_dir: Path
    output_dir: Path
    imports_dir: Path
    attendance_import_dir: Path
    cleaned_dir: Path
    reports_dir: Path
    database_dir: Path
    templates_dir: Path
    logs_dir: Path
    sqlite_path: Path
    settings_path: Path
    route_mode: str = "hybrid_rule_based"
    detour_index: float = 1.35
    average_speed_kmph: float = 32.0
    candidate_top_n: int = 5
    confidence_distance_m: float = 300.0
    ambiguous_distance_m: float = 500.0
    hospital_priority_distance_m: float = 1000.0
    existing_client_priority_distance_m: float = 1000.0
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
    risk_home_core_event_score: int = 0
    risk_home_edge_event_score: int = 0
    risk_min_field_visit_distance_from_home_m: float = 1000.0
    risk_min_checkin_count: int = 2
    risk_min_attendance_span_hours: float = 6.0
    risk_max_attendance_span_hours: float = 14.0
    v3_existing_client_radius_m: float = 1000.0
    v3_unknown_prospect_radius_m: float = 500.0
    fuel_rate: float = 3.0
    maintenance_rate: float = 1.5
    break_minutes: int = 30
    light_green_pct: float = 0.15
    light_yellow_pct: float = 0.30
    google_maps_enabled: bool = False
    hospital_keywords: tuple[str, ...] = ("醫院", "衛生所", "療養院")
    hospital_exclude_keywords: tuple[str, ...] = ("診所", "藥局")


CONFIG_OVERRIDE_FIELDS = {
    "route_mode",
    "detour_index",
    "average_speed_kmph",
    "candidate_top_n",
    "confidence_distance_m",
    "ambiguous_distance_m",
    "hospital_priority_distance_m",
    "existing_client_priority_distance_m",
    "risk_review_distance_m",
    "risk_high_distance_m",
    "risk_auto_select_max_distance_m",
    "risk_customer_override_gap_m",
    "risk_ambiguity_distance_m",
    "risk_ambiguity_candidate_count",
    "risk_min_travel_speed_kmph",
    "risk_impossible_travel_buffer_min",
    "risk_home_radius_m",
    "risk_home_area_max_distance_m",
    "risk_home_core_event_score",
    "risk_home_edge_event_score",
    "risk_min_field_visit_distance_from_home_m",
    "risk_min_checkin_count",
    "risk_min_attendance_span_hours",
    "risk_max_attendance_span_hours",
    "v3_existing_client_radius_m",
    "v3_unknown_prospect_radius_m",
    "fuel_rate",
    "maintenance_rate",
    "break_minutes",
    "light_green_pct",
    "light_yellow_pct",
    "google_maps_enabled",
    "hospital_keywords",
    "hospital_exclude_keywords",
}


def _coerce_override(field_name: str, value):
    if field_name in {
        "candidate_top_n",
        "break_minutes",
        "risk_ambiguity_candidate_count",
        "risk_min_checkin_count",
        "risk_home_core_event_score",
        "risk_home_edge_event_score",
    }:
        return int(value)
    if field_name in {
        "detour_index",
        "average_speed_kmph",
        "confidence_distance_m",
        "ambiguous_distance_m",
        "hospital_priority_distance_m",
        "existing_client_priority_distance_m",
        "risk_review_distance_m",
        "risk_high_distance_m",
        "risk_auto_select_max_distance_m",
        "risk_customer_override_gap_m",
        "risk_ambiguity_distance_m",
        "risk_min_travel_speed_kmph",
        "risk_impossible_travel_buffer_min",
        "risk_home_radius_m",
        "risk_home_area_max_distance_m",
        "risk_min_field_visit_distance_from_home_m",
        "risk_min_attendance_span_hours",
        "risk_max_attendance_span_hours",
        "v3_existing_client_radius_m",
        "v3_unknown_prospect_radius_m",
        "fuel_rate",
        "maintenance_rate",
        "light_green_pct",
        "light_yellow_pct",
    }:
        return float(value)
    if field_name == "google_maps_enabled":
        return bool(value)
    if field_name in {"hospital_keywords", "hospital_exclude_keywords"}:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        if isinstance(value, (list, tuple)):
            return tuple(str(part).strip() for part in value if str(part).strip())
    return value


def load_user_settings(settings_path: str | Path) -> dict:
    path = Path(settings_path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return {key: payload[key] for key in CONFIG_OVERRIDE_FIELDS if key in payload}


def save_user_settings(settings_path: str | Path, values: dict) -> None:
    path = Path(settings_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: values[key] for key in CONFIG_OVERRIDE_FIELDS if key in values}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def config_to_editable_dict(config: AppConfig) -> dict:
    payload = {}
    for field in fields(AppConfig):
        if field.name in CONFIG_OVERRIDE_FIELDS:
            value = getattr(config, field.name)
            if isinstance(value, tuple):
                payload[field.name] = list(value)
            else:
                payload[field.name] = value
    return payload


def build_config(root_dir: str | Path | None = None) -> AppConfig:
    root = Path(root_dir or Path(__file__).resolve().parent)
    output_dir = root / "outputs"
    imports_dir = output_dir / "imports"
    attendance_import_dir = imports_dir / "attendance"
    config = AppConfig(
        root_dir=root,
        data_dir=root,
        output_dir=output_dir,
        imports_dir=imports_dir,
        attendance_import_dir=attendance_import_dir,
        cleaned_dir=output_dir / "cleaned",
        reports_dir=output_dir / "reports",
        database_dir=output_dir / "database",
        templates_dir=output_dir / "templates",
        logs_dir=output_dir / "logs",
        sqlite_path=output_dir / "database" / "route_audit.db",
        settings_path=output_dir / "config" / "app_settings.json",
    )
    overrides = load_user_settings(config.settings_path)
    for key, value in overrides.items():
        setattr(config, key, _coerce_override(key, value))
    return config
 

def ensure_directories(config: AppConfig) -> None:
    for path in [
        config.output_dir,
        config.settings_path.parent,
        config.imports_dir,
        config.attendance_import_dir,
        config.cleaned_dir,
        config.reports_dir,
        config.database_dir,
        config.templates_dir,
        config.logs_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)
