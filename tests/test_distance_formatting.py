from distance_formatting import format_distance


def test_format_distance_uses_meters_below_one_kilometer() -> None:
    assert format_distance(30) == "30公尺"
    assert format_distance(999) == "999公尺"


def test_format_distance_uses_compact_kilometers_at_one_kilometer_or_more() -> None:
    assert format_distance(1000) == "1公里"
    assert format_distance(1224) == "1.2公里"
    assert format_distance(10644) == "10.6公里"
