from __future__ import annotations

import shutil
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests


HOSPITAL_COLUMNS = [
    "機構代碼",
    "機構名稱",
    "電話",
    "縣市區名",
    "地址",
    "科別",
    "Response_Address",
    "Response_X",
    "Response_Y",
]

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

Geocoder = Callable[[str, str], dict[str, Any]]

CHINESE_DIGITS = {
    "零": "0",
    "〇": "0",
    "○": "0",
    "O": "0",
    "Ｏ": "0",
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
}
ARABIC_TO_CHINESE = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
SMALL_CHINESE_VALUES = {key: int(value) for key, value in CHINESE_DIGITS.items() if value != "0" and key not in {"O", "Ｏ"}}


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def number_to_chinese(value: int) -> str:
    if value < 10:
        return ARABIC_TO_CHINESE[value]
    if value == 10:
        return "十"
    if value < 20:
        return "十" + ARABIC_TO_CHINESE[value % 10]
    if value % 10 == 0:
        return ARABIC_TO_CHINESE[value // 10] + "十"
    return ARABIC_TO_CHINESE[value // 10] + "十" + ARABIC_TO_CHINESE[value % 10]


def convert_chinese_digit_sequence(value: str) -> str:
    return "".join(CHINESE_DIGITS.get(char, char) for char in value)


def convert_small_chinese_numeral(value: str) -> str:
    if any(char in value for char in "零〇○OＯ"):
        return convert_chinese_digit_sequence(value)
    if len(value) > 1 and all(char in CHINESE_DIGITS for char in value):
        return convert_chinese_digit_sequence(value)
    if value == "十":
        return "10"
    match = re.fullmatch(r"十([一二三四五六七八九])", value)
    if match:
        return str(10 + SMALL_CHINESE_VALUES[match.group(1)])
    match = re.fullmatch(r"([一二三四五六七八九])十", value)
    if match:
        return str(SMALL_CHINESE_VALUES[match.group(1)] * 10)
    match = re.fullmatch(r"([一二三四五六七八九])十([一二三四五六七八九])", value)
    if match:
        return str(SMALL_CHINESE_VALUES[match.group(1)] * 10 + SMALL_CHINESE_VALUES[match.group(2)])
    return convert_chinese_digit_sequence(value)


def normalize_address_for_geocode(address: Any) -> tuple[str, list[str]]:
    text = normalize_text(address)
    tags: list[str] = []
    if not text:
        return "", tags

    if re.search(r"\d+\.\d+", text):
        tags.append("多門牌用點號連接")
    if re.search(r"[0-9一二三四五六七八九十〇○OＯ零]+[、,，][0-9一二三四五六七八九十〇○OＯ零]+", text):
        tags.append("多門牌用頓號/逗號連接")
    if re.search(r"(?<![0-9])[0-9]{1,2}(?=(路|街|段|弄))", text):
        tags.append("路街段弄使用阿拉伯數字")
    if re.search(r"[一二三四五六七八九十〇○OＯ零]+(號|[、,，])", text):
        tags.append("門牌使用中文數字")
    if re.search(r"(里|鄰)", text):
        tags.append("包含里鄰")
    if re.search(r"\d+[-–－]\d+號|\d+\.\d+-\d+號|\d+[、,，]\d+-\d+號", text):
        tags.append("含之號/連字號門牌")
    if "褔" in text:
        tags.append("福字異體/錯字")

    cleaned = text.replace("褔", "福")
    cleaned = re.sub(r"[–－—]", "-", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = re.sub(
        r"(?<![0-9])([0-9]{1,2})(?=(路|街|段|弄))",
        lambda match: number_to_chinese(int(match.group(1))),
        cleaned,
    )
    cleaned = re.sub(r"(?<=[區鄉鎮])[\u4e00-\u9fff]{1,4}里(?=.*[路街大道])", "", cleaned)
    cleaned = re.sub(r"[0-9]+鄰", "", cleaned)
    cleaned = cleaned.replace("里路", "路")
    cleaned = re.sub(
        r"([一二三四五六七八九十〇○OＯ零]+)(號|之|[、,，])",
        lambda match: convert_small_chinese_numeral(match.group(1)) + match.group(2),
        cleaned,
    )
    cleaned = re.sub(
        r"之([一二三四五六七八九十〇○OＯ零]+)(號)?",
        lambda match: "之" + convert_small_chinese_numeral(match.group(1)) + (match.group(2) or ""),
        cleaned,
    )
    cleaned = re.sub(r"(\d+)(?:\.[^號]+)+(號)", r"\1\2", cleaned)
    cleaned = re.sub(r"(\d+)(?:[、,，][^號]+)+(號)", r"\1\2", cleaned)
    return cleaned, tags


def apply_address_normalization(dataframe: pd.DataFrame, overwrite: bool = False) -> pd.DataFrame:
    result = ensure_hospital_columns(dataframe).copy()
    cleaned_values: list[str] = []
    issue_values: list[str] = []
    for _, row in result.iterrows():
        cleaned, tags = normalize_address_for_geocode(row.get("地址"))
        cleaned_values.append(cleaned)
        issue_values.append(";".join(tags))
    result["address_cleaned"] = cleaned_values
    result["address_issue_tags"] = issue_values
    should_fill = result["Response_Address"].map(normalize_text).eq("") | bool(overwrite)
    result.loc[should_fill, "Response_Address"] = result.loc[should_fill, "address_cleaned"]
    return result


def validate_hospital_columns(dataframe: pd.DataFrame) -> list[str]:
    return [column for column in HOSPITAL_COLUMNS if column not in dataframe.columns]


def ensure_hospital_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    missing = validate_hospital_columns(dataframe)
    if missing:
        raise ValueError(f"缺少必要欄位: {', '.join(missing)}")
    return dataframe[HOSPITAL_COLUMNS].copy()


def read_hospital_csv(path_or_buffer: Any) -> pd.DataFrame:
    dataframe = pd.read_csv(path_or_buffer, encoding="utf-8-sig", dtype=str).fillna("")
    return ensure_hospital_columns(dataframe)


def build_geocode_query(row: pd.Series) -> str:
    response_address = normalize_text(row.get("Response_Address"))
    if response_address:
        return response_address
    return normalize_text(row.get("地址"))


def has_coordinates(row: pd.Series) -> bool:
    return bool(normalize_text(row.get("Response_X")) and normalize_text(row.get("Response_Y")))


def build_import_preview(import_df: pd.DataFrame, hospitals_df: pd.DataFrame) -> pd.DataFrame:
    incoming = ensure_hospital_columns(import_df).copy()
    hospitals = ensure_hospital_columns(hospitals_df).copy()

    incoming["機構代碼"] = incoming["機構代碼"].map(normalize_text)
    hospitals["機構代碼"] = hospitals["機構代碼"].map(normalize_text)
    existing_codes = set(hospitals["機構代碼"])
    duplicate_codes = set(incoming.loc[incoming["機構代碼"].duplicated(keep=False), "機構代碼"])

    incoming["geocode_query"] = incoming.apply(build_geocode_query, axis=1)
    incoming["has_coordinates"] = incoming.apply(has_coordinates, axis=1)

    def status(row: pd.Series) -> str:
        code = normalize_text(row.get("機構代碼"))
        if not code:
            return "missing_code"
        if code in duplicate_codes:
            return "duplicate_in_import"
        if code in existing_codes:
            return "already_exists"
        if not normalize_text(row.get("geocode_query")):
            return "missing_address"
        if row.get("has_coordinates"):
            return "ready_to_import"
        return "needs_geocode"

    incoming["import_status"] = incoming.apply(status, axis=1)
    return incoming


def google_geocode(query: str, api_key: str, timeout: int = 20) -> dict[str, Any]:
    response = requests.get(
        GOOGLE_GEOCODE_URL,
        params={
            "address": query,
            "key": api_key,
            "language": "zh-TW",
            "region": "tw",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    status = payload.get("status", "UNKNOWN")
    if status != "OK" or not payload.get("results"):
        return {
            "status": status,
            "formatted_address": "",
            "lon": None,
            "lat": None,
            "location_type": "",
            "raw": payload,
        }

    result = payload["results"][0]
    location = result.get("geometry", {}).get("location", {})
    return {
        "status": status,
        "formatted_address": result.get("formatted_address", ""),
        "lon": location.get("lng"),
        "lat": location.get("lat"),
        "location_type": result.get("geometry", {}).get("location_type", ""),
        "raw": payload,
    }


def geocode_import_rows(
    import_df: pd.DataFrame,
    api_key: str,
    geocoder: Geocoder = google_geocode,
    limit: int | None = None,
) -> pd.DataFrame:
    result = ensure_hospital_columns(import_df).copy()
    result["geocode_query"] = result.apply(build_geocode_query, axis=1)
    for column in ["geocode_status", "google_formatted_address", "google_location_type", "geocode_error"]:
        if column not in result.columns:
            result[column] = ""

    processed = 0
    for index, row in result.iterrows():
        if has_coordinates(row):
            result.at[index, "geocode_status"] = "already_has_coordinates"
            continue
        query = normalize_text(row.get("geocode_query"))
        if not query:
            result.at[index, "geocode_status"] = "missing_address"
            continue
        if limit is not None and processed >= limit:
            result.at[index, "geocode_status"] = "not_processed"
            continue

        processed += 1
        try:
            geocoded = geocoder(query, api_key)
        except Exception as exc:  # noqa: BLE001 - surface provider errors in the review grid.
            result.at[index, "geocode_status"] = "ERROR"
            result.at[index, "geocode_error"] = str(exc)
            continue

        result.at[index, "geocode_status"] = normalize_text(geocoded.get("status"))
        result.at[index, "google_formatted_address"] = normalize_text(geocoded.get("formatted_address"))
        result.at[index, "google_location_type"] = normalize_text(geocoded.get("location_type"))
        lon = geocoded.get("lon")
        lat = geocoded.get("lat")
        if lon is not None and lat is not None:
            result.at[index, "Response_X"] = lon
            result.at[index, "Response_Y"] = lat

    return result


def append_geocoded_rows(hospitals_df: pd.DataFrame, import_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    hospitals = ensure_hospital_columns(hospitals_df).copy()
    incoming = ensure_hospital_columns(import_df).copy()

    hospitals["機構代碼"] = hospitals["機構代碼"].map(normalize_text)
    incoming["機構代碼"] = incoming["機構代碼"].map(normalize_text)

    existing_codes = set(hospitals["機構代碼"])
    appendable = incoming.loc[
        incoming["機構代碼"].ne("")
        & ~incoming["機構代碼"].isin(existing_codes)
        & incoming.apply(has_coordinates, axis=1)
    ].copy()
    appendable = appendable.drop_duplicates(subset=["機構代碼"], keep="first")
    appendable = appendable[HOSPITAL_COLUMNS]

    combined = pd.concat([hospitals[HOSPITAL_COLUMNS], appendable], ignore_index=True)
    combined = combined.drop_duplicates(subset=["機構代碼"], keep="first")
    return combined[HOSPITAL_COLUMNS], appendable


def write_hospitals_with_backup(
    dataframe: pd.DataFrame,
    hospitals_path: str | Path,
    timestamp: str | None = None,
) -> Path:
    path = Path(hospitals_path)
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.stem}.backup_{stamp}{path.suffix}")
    if path.exists():
        shutil.copy2(path, backup_path)
    ensure_hospital_columns(dataframe).to_csv(path, index=False, encoding="utf-8-sig")
    return backup_path
