from map_presentation import build_padded_map_view


def test_weekly_map_view_can_use_more_padding_and_lower_zoom_than_daily_view():
    latitudes = [23.45, 24.25, 23.90]
    longitudes = [120.10, 121.35, 120.70]

    daily_view = build_padded_map_view(
        latitudes,
        longitudes,
        padding_ratio=0.45,
        min_padding=0.008,
        zoom_out=1.25,
        min_zoom=2.4,
    )
    weekly_view = build_padded_map_view(
        latitudes,
        longitudes,
        padding_ratio=0.75,
        min_padding=0.02,
        zoom_out=1.85,
        min_zoom=2.0,
    )

    assert weekly_view["zoom"] < daily_view["zoom"]
    assert weekly_view["bounds"]["south"] < daily_view["bounds"]["south"]
    assert weekly_view["bounds"]["north"] > daily_view["bounds"]["north"]
    assert weekly_view["bounds"]["west"] < daily_view["bounds"]["west"]
    assert weekly_view["bounds"]["east"] > daily_view["bounds"]["east"]


def test_empty_map_view_returns_stable_defaults():
    view = build_padded_map_view([], [])

    assert view["zoom"] == 6.0
    assert view["center"] == {"lat": 0.0, "lon": 0.0}


def test_map_view_can_cap_zoom_for_printed_weekly_maps():
    view = build_padded_map_view(
        [23.95, 23.96],
        [120.45, 120.46],
        zoom_out=0.5,
        max_zoom=6.2,
    )

    assert view["zoom"] == 6.2
