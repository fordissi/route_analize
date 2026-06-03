from __future__ import annotations

import pandas as pd

from hospital_geocode_importer import (
    HOSPITAL_COLUMNS,
    append_geocoded_rows,
    apply_address_normalization,
    build_import_preview,
    geocode_import_rows,
    normalize_address_for_geocode,
    write_hospitals_with_backup,
)


def hospital_row(code: str, name: str, address: str, response_address: str = "", lon: str = "", lat: str = "") -> dict:
    return {
        "機構代碼": code,
        "機構名稱": name,
        "電話": "",
        "縣市區名": "",
        "地址": address,
        "科別": "",
        "Response_Address": response_address,
        "Response_X": lon,
        "Response_Y": lat,
    }


def test_build_import_preview_flags_existing_duplicate_and_query_address():
    hospitals = pd.DataFrame(
        [
            hospital_row("A001", "已存在診所", "新北市三重區正義北路47號", lon="121.1", lat="25.1"),
        ],
        columns=HOSPITAL_COLUMNS,
    )
    incoming = pd.DataFrame(
        [
            hospital_row("A001", "已存在診所", "新北市三重區正義北路47、49號", "新北市三重區正義北路47號"),
            hospital_row("B001", "新診所", "桃園市楊梅區信義街一六、一八號", "桃園市楊梅區信義街16號"),
            hospital_row("B001", "新診所重複", "桃園市楊梅區信義街一六、一八號", "桃園市楊梅區信義街16號"),
            hospital_row("C001", "無地址診所", ""),
        ],
        columns=HOSPITAL_COLUMNS,
    )

    preview = build_import_preview(incoming, hospitals)

    assert preview.loc[0, "import_status"] == "already_exists"
    assert preview.loc[1, "import_status"] == "duplicate_in_import"
    assert preview.loc[2, "import_status"] == "duplicate_in_import"
    assert preview.loc[3, "import_status"] == "missing_address"
    assert preview.loc[1, "geocode_query"] == "桃園市楊梅區信義街16號"


def test_geocode_import_rows_updates_successful_rows_only():
    incoming = pd.DataFrame(
        [
            hospital_row("A001", "成功診所", "屏東縣潮州鎮四維路295.295-1號", "屏東縣潮州鎮四維路295號"),
            hospital_row("B001", "失敗診所", "不存在地址", "不存在地址"),
            hospital_row("C001", "已有座標診所", "台北市中正區常德街1號", "台北市中正區常德街1號", "121.1", "25.1"),
        ],
        columns=HOSPITAL_COLUMNS,
    )

    def fake_geocoder(query: str, api_key: str):
        if query == "屏東縣潮州鎮四維路295號":
            return {
                "status": "OK",
                "formatted_address": "屏東縣潮州鎮四維路295號",
                "lon": 120.54321,
                "lat": 22.54321,
                "location_type": "ROOFTOP",
            }
        return {"status": "ZERO_RESULTS", "formatted_address": "", "lon": None, "lat": None, "location_type": ""}

    result = geocode_import_rows(incoming, api_key="key", geocoder=fake_geocoder)

    assert result.loc[0, "Response_X"] == 120.54321
    assert result.loc[0, "Response_Y"] == 22.54321
    assert result.loc[0, "geocode_status"] == "OK"
    assert result.loc[0, "Response_Address"] == "屏東縣潮州鎮四維路295號"
    assert result.loc[0, "google_formatted_address"] == "屏東縣潮州鎮四維路295號"
    assert pd.isna(result.loc[1, "Response_X"]) or result.loc[1, "Response_X"] == ""
    assert result.loc[1, "geocode_status"] == "ZERO_RESULTS"
    assert result.loc[2, "geocode_status"] == "already_has_coordinates"


def test_normalize_address_for_geocode_handles_known_tgos_failures():
    examples = {
        "新北市三重區正義北路47、49號": "新北市三重區正義北路47號",
        "臺中市西屯區青海路一段一O一、一O三號": "臺中市西屯區青海路一段101號",
        "桃園市楊梅區信義街一六、一八號": "桃園市楊梅區信義街16號",
        "屏東縣潮州鎮四維路295.295-1號": "屏東縣潮州鎮四維路295號",
        "臺中市南屯區大墩6街48號": "臺中市南屯區大墩六街48號",
        "臺南市新營區忠政里武昌街8號": "臺南市新營區武昌街8號",
        "桃園市八德區廣褔路一八八號": "桃園市八德區廣福路188號",
    }

    for original, expected in examples.items():
        cleaned, _tags = normalize_address_for_geocode(original)
        assert cleaned == expected


def test_apply_address_normalization_uses_address_as_source_for_response_address():
    incoming = pd.DataFrame(
        [
            hospital_row("A001", "新診所", "新北市三重區正義北路47、49號"),
            hospital_row("B001", "保留診所", "屏東縣潮州鎮四維路295.295-1號", "人工確認地址"),
        ],
        columns=HOSPITAL_COLUMNS,
    )

    filled = apply_address_normalization(incoming, overwrite=False)
    overwritten = apply_address_normalization(incoming, overwrite=True)

    assert filled.loc[0, "Response_Address"] == "新北市三重區正義北路47號"
    assert filled.loc[1, "Response_Address"] == "人工確認地址"
    assert overwritten.loc[1, "Response_Address"] == "屏東縣潮州鎮四維路295號"
    assert "多門牌用點號連接" in overwritten.loc[1, "address_issue_tags"]


def test_append_geocoded_rows_skips_existing_and_rows_without_coordinates():
    hospitals = pd.DataFrame(
        [hospital_row("A001", "已存在診所", "地址", lon="121.1", lat="25.1")],
        columns=HOSPITAL_COLUMNS,
    )
    incoming = pd.DataFrame(
        [
            hospital_row("A001", "已存在診所", "地址", lon="121.2", lat="25.2"),
            hospital_row("B001", "可匯入診所", "地址", "地址", "121.3", "25.3"),
            hospital_row("C001", "無座標診所", "地址"),
        ],
        columns=HOSPITAL_COLUMNS,
    )

    combined, appended = append_geocoded_rows(hospitals, incoming)

    assert list(appended["機構代碼"]) == ["B001"]
    assert list(combined["機構代碼"]) == ["A001", "B001"]


def test_write_hospitals_with_backup_creates_backup_and_preserves_columns(tmp_path):
    hospitals_path = tmp_path / "hospitals.csv"
    original = pd.DataFrame([hospital_row("A001", "原診所", "地址")], columns=HOSPITAL_COLUMNS)
    updated = pd.DataFrame(
        [
            hospital_row("A001", "原診所", "地址"),
            hospital_row("B001", "新診所", "地址", "地址", "121.3", "25.3"),
        ],
        columns=HOSPITAL_COLUMNS,
    )
    original.to_csv(hospitals_path, index=False, encoding="utf-8-sig")

    backup_path = write_hospitals_with_backup(updated, hospitals_path, timestamp="20260521_120000")

    assert backup_path.exists()
    reloaded = pd.read_csv(hospitals_path, encoding="utf-8-sig", dtype=str).fillna("")
    backup = pd.read_csv(backup_path, encoding="utf-8-sig", dtype=str).fillna("")
    assert list(reloaded.columns) == HOSPITAL_COLUMNS
    assert list(backup["機構代碼"]) == ["A001"]
    assert list(reloaded["機構代碼"]) == ["A001", "B001"]
