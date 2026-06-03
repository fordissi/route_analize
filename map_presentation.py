from __future__ import annotations

from math import cos, log, radians


def compute_zoom(latitudes: list[float], longitudes: list[float]) -> float:
    if not latitudes or not longitudes:
        return 6.0
    lat_span = max(latitudes) - min(latitudes)
    lon_span = max(longitudes) - min(longitudes)
    center_lat = sum(latitudes) / len(latitudes)
    lon_span_adjusted = lon_span * max(abs(cos(radians(center_lat))), 0.2)
    max_span = max(lat_span, lon_span_adjusted)
    if max_span <= 0.001:
        return 14.2
    if max_span <= 0.005:
        return 13.0
    if max_span <= 0.01:
        return 12.0
    if max_span <= 0.03:
        return 10.8
    if max_span <= 0.08:
        return 9.8
    if max_span <= 0.2:
        return 8.6
    if max_span <= 0.5:
        return 7.4
    zoom = 7.2 - log(max(max_span, 1e-6) * 70, 2)
    return float(min(max(zoom, 3.2), 14.2))


def build_padded_map_view(
    latitudes: list[float],
    longitudes: list[float],
    *,
    padding_ratio: float = 0.45,
    min_padding: float = 0.008,
    zoom_out: float = 1.25,
    min_zoom: float = 2.4,
    max_zoom: float | None = None,
) -> dict[str, object]:
    if not latitudes or not longitudes:
        return {
            "center": {"lat": 0.0, "lon": 0.0},
            "zoom": 6.0,
            "bounds": {"west": 0.0, "east": 0.0, "south": 0.0, "north": 0.0},
            "padded_latitudes": [],
            "padded_longitudes": [],
        }

    lat_span = max(latitudes) - min(latitudes)
    lon_span = max(longitudes) - min(longitudes)
    lat_padding = max(lat_span * padding_ratio, min_padding)
    lon_padding = max(lon_span * padding_ratio, min_padding)
    padded_lats = [min(latitudes) - lat_padding, max(latitudes) + lat_padding]
    padded_lons = [min(longitudes) - lon_padding, max(longitudes) + lon_padding]
    zoom = max(compute_zoom(padded_lats, padded_lons) - zoom_out, min_zoom)
    if max_zoom is not None:
        zoom = min(zoom, max_zoom)
    return {
        "center": {"lat": sum(padded_lats) / len(padded_lats), "lon": sum(padded_lons) / len(padded_lons)},
        "zoom": zoom,
        "bounds": {
            "west": min(padded_lons),
            "east": max(padded_lons),
            "south": min(padded_lats),
            "north": max(padded_lats),
        },
        "padded_latitudes": padded_lats,
        "padded_longitudes": padded_lons,
    }
