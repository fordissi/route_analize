from __future__ import annotations

from typing import Any

import pandas as pd


RISK_REASON_LABELS = {
    "near_home_checkin": "可能在家附近打卡",
    "far_customer_override": "系統選到較遠的既有客戶，但附近有更近的候選院所",
    "selected_not_top5": "系統選定院所不在距離最近的前 5 名候選內",
    "selected_distance_too_far": "系統選定院所距離過遠，超過自動選取門檻",
    "nearby_candidate_conflict": "附近候選院所過於密集，單點判定信心較低",
    "no_reasonable_candidate": "GPS 點附近沒有合理候選院所",
    "impossible_travel_time": "相鄰打卡點的移動時間不合理",
    "home_area_only_trace": "當日軌跡主要停留在住家附近，缺少足夠外勤佐證",
    "home_start_end_without_field_trace": "路線從住家附近起訖，但缺少明確外勤拜訪軌跡",
    "insufficient_route_evidence": "GPS 點數、路線或候選匹配不足，無法形成可檢查的外勤路徑",
}


def _num(value: Any, default: float = 0.0) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return default if pd.isna(numeric) else float(numeric)


def _date_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    try:
        return pd.Timestamp(value).date().isoformat()
    except Exception:  # noqa: BLE001
        return str(value)


def _first_existing(row: pd.Series, names: list[str], default: Any = 0) -> Any:
    for name in names:
        if name in row:
            return row.get(name)
    return default


def translate_risk_reason_codes(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.replace("；", ",").replace(";", ",").split(",") if part.strip()]
    if not parts:
        return text
    translated = [RISK_REASON_LABELS.get(part, part) for part in dict.fromkeys(parts)]
    return "；".join(translated)


def build_monthly_risk_trend(daily_risk: pd.DataFrame, monthly_claims: pd.DataFrame | None = None) -> pd.DataFrame:
    columns = [
        "year_month",
        "employee_id",
        "employee_label",
        "department",
        "attendance_days",
        "risk_priority_score",
        "risk_priority_per_day",
        "review_event_count",
        "high_risk_event_count",
        "low_confidence_event_count",
        "home_area_only_days",
        "gps_event_count",
        "claim_diff_abs_rate",
    ]
    if daily_risk.empty or "work_date" not in daily_risk.columns:
        return pd.DataFrame(columns=columns)

    work = daily_risk.copy()
    work["work_date"] = pd.to_datetime(work["work_date"], errors="coerce")
    work = work.dropna(subset=["employee_id", "work_date"])
    if work.empty:
        return pd.DataFrame(columns=columns)

    work["year_month"] = work["work_date"].dt.strftime("%Y-%m")
    if "employee_label" not in work.columns:
        work["employee_label"] = work["employee_id"].astype(str)
    if "department" not in work.columns:
        work["department"] = ""
    numeric_columns = [
        "risk_priority_score",
        "review_event_count",
        "high_risk_event_count",
        "low_confidence_event_count",
        "home_area_only_trace",
        "gps_event_count",
    ]
    for column in numeric_columns:
        if column not in work.columns:
            work[column] = 0
        work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0)

    grouped = (
        work.groupby(["year_month", "employee_id", "employee_label", "department"], dropna=False, as_index=False)
        .agg(
            attendance_days=("work_date", "nunique"),
            risk_priority_score=("risk_priority_score", "sum"),
            review_event_count=("review_event_count", "sum"),
            high_risk_event_count=("high_risk_event_count", "sum"),
            low_confidence_event_count=("low_confidence_event_count", "sum"),
            home_area_only_days=("home_area_only_trace", lambda s: int((s.fillna(0) > 0).sum())),
            gps_event_count=("gps_event_count", "sum"),
        )
    )
    grouped["risk_priority_per_day"] = grouped["risk_priority_score"] / grouped["attendance_days"].clip(lower=1)

    if monthly_claims is not None and not monthly_claims.empty:
        claims = monthly_claims.copy()
        if {"employee_id", "year_month", "difference_rate"}.issubset(claims.columns):
            claims["claim_diff_abs_rate"] = pd.to_numeric(claims["difference_rate"], errors="coerce").abs()
            claim_summary = (
                claims.dropna(subset=["employee_id", "year_month"])
                .groupby(["employee_id", "year_month"], dropna=False, as_index=False)["claim_diff_abs_rate"]
                .max()
            )
            grouped = grouped.merge(claim_summary, on=["employee_id", "year_month"], how="left")
    if "claim_diff_abs_rate" not in grouped.columns:
        grouped["claim_diff_abs_rate"] = 0.0
    grouped["claim_diff_abs_rate"] = grouped["claim_diff_abs_rate"].fillna(0.0)

    return grouped[columns].sort_values(["year_month", "employee_label"]).reset_index(drop=True)


def build_company_monthly_risk_trend(monthly_trend: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "year_month",
        "employee_count",
        "attendance_days",
        "risk_priority_score",
        "risk_priority_per_day",
        "risk_priority_per_employee",
        "review_event_count",
        "high_risk_event_count",
        "low_confidence_event_count",
        "home_area_only_days",
        "risky_employee_count",
        "risky_employee_rate",
        "claim_diff_abs_rate",
    ]
    if monthly_trend.empty or "year_month" not in monthly_trend.columns:
        return pd.DataFrame(columns=columns)

    work = monthly_trend.copy()
    work["year_month"] = work["year_month"].astype(str)
    if "employee_id" not in work.columns:
        work["employee_id"] = ""
    numeric_columns = [
        "attendance_days",
        "risk_priority_score",
        "review_event_count",
        "high_risk_event_count",
        "low_confidence_event_count",
        "home_area_only_days",
        "claim_diff_abs_rate",
    ]
    for column in numeric_columns:
        if column not in work.columns:
            work[column] = 0
        work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0)
    work["risk_priority_per_day"] = work["risk_priority_score"] / work["attendance_days"].clip(lower=1)
    work["is_priority_review_employee"] = (
        (work["high_risk_event_count"] > 0)
        | (work["home_area_only_days"] > 0)
        | (work["risk_priority_per_day"] >= 12)
    )

    grouped = (
        work.groupby("year_month", dropna=False, as_index=False)
        .agg(
            employee_count=("employee_id", "nunique"),
            attendance_days=("attendance_days", "sum"),
            risk_priority_score=("risk_priority_score", "sum"),
            review_event_count=("review_event_count", "sum"),
            high_risk_event_count=("high_risk_event_count", "sum"),
            low_confidence_event_count=("low_confidence_event_count", "sum"),
            home_area_only_days=("home_area_only_days", "sum"),
            risky_employee_count=("is_priority_review_employee", "sum"),
            claim_diff_abs_rate=("claim_diff_abs_rate", "mean"),
        )
        .sort_values("year_month")
    )
    grouped["risk_priority_per_day"] = grouped["risk_priority_score"] / grouped["attendance_days"].clip(lower=1)
    grouped["risk_priority_per_employee"] = grouped["risk_priority_score"] / grouped["employee_count"].clip(lower=1)
    grouped["risky_employee_rate"] = grouped["risky_employee_count"] / grouped["employee_count"].clip(lower=1)
    return grouped[columns].reset_index(drop=True)


def build_employee_monthly_warming(monthly_trend: pd.DataFrame, latest_month: str | None = None) -> pd.DataFrame:
    columns = [
        "employee_id",
        "employee_label",
        "department",
        "year_month",
        "risk_priority_per_day",
        "baseline_risk_priority_per_day",
        "warming_delta",
        "warming_ratio",
        "risk_priority_score",
        "high_risk_event_count",
        "home_area_only_days",
    ]
    if monthly_trend.empty or "year_month" not in monthly_trend.columns:
        return pd.DataFrame(columns=columns)

    work = monthly_trend.copy()
    work["year_month"] = work["year_month"].astype(str)
    for column in ["risk_priority_per_day", "risk_priority_score", "high_risk_event_count", "home_area_only_days"]:
        if column not in work.columns:
            work[column] = 0
        work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0)
    if "employee_label" not in work.columns:
        work["employee_label"] = work.get("employee_id", "").astype(str)
    if "department" not in work.columns:
        work["department"] = ""

    selected_month = latest_month or work["year_month"].max()
    current = work.loc[work["year_month"] == selected_month].copy()
    history = work.loc[work["year_month"] < selected_month].copy()
    if current.empty or history.empty:
        return pd.DataFrame(columns=columns)

    baseline = (
        history.groupby(["employee_id"], dropna=False, as_index=False)["risk_priority_per_day"]
        .mean()
        .rename(columns={"risk_priority_per_day": "baseline_risk_priority_per_day"})
    )
    result = current.merge(baseline, on="employee_id", how="left")
    result["baseline_risk_priority_per_day"] = result["baseline_risk_priority_per_day"].fillna(0.0)
    result["warming_delta"] = result["risk_priority_per_day"] - result["baseline_risk_priority_per_day"]
    denominator = result["baseline_risk_priority_per_day"].where(result["baseline_risk_priority_per_day"] > 0)
    result["warming_ratio"] = (result["risk_priority_per_day"] / denominator).replace([float("inf"), -float("inf")], pd.NA)
    result["warming_ratio"] = result["warming_ratio"].fillna(result["risk_priority_per_day"].where(result["risk_priority_per_day"] > 0, 0.0))
    return (
        result[columns]
        .sort_values(["warming_delta", "risk_priority_per_day", "risk_priority_score"], ascending=[False, False, False])
        .reset_index(drop=True)
    )


def daily_primary_risk_reason(row: pd.Series) -> str:
    if _num(row.get("home_area_only_trace")) > 0 or _num(row.get("僅居家附近軌跡天數")) > 0:
        return "僅居家附近軌跡"
    if _num(row.get("home_start_end_without_field_trace")) > 0 or _num(row.get("住家起訖但缺外勤軌跡天數")) > 0:
        return "住家起訖但缺外勤軌跡"
    if _num(row.get("high_risk_event_count", row.get("高風險點數"))) > 0:
        return "高風險打卡點"
    if _num(row.get("review_event_count", row.get("需覆核點數"))) > 0:
        return "需覆核打卡點"
    if _num(row.get("insufficient_route_evidence")) > 0:
        return "外勤佐證不足"
    reason = str(row.get("risk_reason_summary", row.get("風險原因摘要", "")) or "").strip()
    return translate_risk_reason_codes(reason) if reason else "未見明顯風險"


def overview_primary_risk_reason(row: pd.Series) -> str:
    if _num(row.get("僅居家附近軌跡天數")) > 0:
        return "僅居家附近軌跡"
    if _num(row.get("住家起訖但缺外勤軌跡天數")) > 0:
        return "住家起訖但缺外勤軌跡"
    if _num(row.get("高風險點數")) > 0:
        return "高風險打卡點"
    if _num(row.get("需覆核點數")) > 0:
        return "需覆核打卡點"
    return "未見明顯風險"


def risk_priority(row: pd.Series) -> float:
    score = _num(_first_existing(row, ["risk_priority_score", "風險優先分", "risk_score", "風險分數"]))
    high = _num(_first_existing(row, ["high_risk_event_count", "高風險點數"]))
    review = _num(_first_existing(row, ["review_event_count", "需覆核點數"]))
    home_only = _num(_first_existing(row, ["home_area_only_trace", "僅居家附近軌跡天數"]))
    home_missing = _num(_first_existing(row, ["home_start_end_without_field_trace", "住家起訖但缺外勤軌跡天數"]))
    return score + high * 20 + review * 6 + home_only * 10 + home_missing * 8


def add_daily_risk_drilldown_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    if result.empty:
        for column in ["primary_risk_reason", "risk_priority", "risk_drilldown_hint"]:
            result[column] = []
        return result
    result["primary_risk_reason"] = result.apply(daily_primary_risk_reason, axis=1)
    result["risk_priority"] = result.apply(risk_priority, axis=1)
    result["risk_drilldown_hint"] = result.apply(
        lambda row: f"優先查看 {_date_text(row.get('work_date', row.get('日期')))}" if risk_priority(row) > 0 else "未見明顯風險",
        axis=1,
    )
    return result


def add_overview_risk_drilldown_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    if result.empty:
        for column in ["主要風險原因", "追查提示", "risk_priority"]:
            result[column] = []
        return result
    result["主要風險原因"] = result.apply(overview_primary_risk_reason, axis=1)
    result["risk_priority"] = result.apply(risk_priority, axis=1)
    result["追查提示"] = result.apply(
        lambda row: f"優先查看 {str(row.get('employee_label', row.get('業務', '該業務')))}的個人報表"
        if risk_priority(row) > 0
        else "可先略過",
        axis=1,
    )
    return result


def event_risk_focus(row: pd.Series) -> str:
    selected_distance = _num(row.get("selected_distance_m"), default=float("nan"))
    distance_gap = _num(row.get("distance_gap_m"), default=0)
    rank = _num(row.get("selected_rank"), default=0)
    reason_codes = str(row.get("risk_reason_codes", "") or "")
    reason = str(row.get("risk_reason_text", "") or "")
    if "near_home_checkin" in reason_codes or "住家" in reason:
        return "可能在家附近打卡"
    if pd.notna(selected_distance) and selected_distance >= 1500:
        return "選定院所距離過遠"
    if distance_gap >= 500:
        return "選定與最近候選差距大"
    if rank > 5:
        return "系統選定候選排名偏後"
    if "無合理" in reason or "no_reasonable_candidate" in reason:
        return "無合理院所候選"
    if reason:
        return reason.split("；")[0].split(";")[0]
    return "未見明顯風險"


def event_evidence_summary(row: pd.Series) -> str:
    parts: list[str] = []
    distance_from_home = _num(row.get("distance_from_home_m"), default=float("nan"))
    selected_distance = _num(row.get("selected_distance_m"), default=float("nan"))
    nearest_distance = _num(row.get("nearest_distance_m"), default=float("nan"))
    distance_gap = _num(row.get("distance_gap_m"), default=float("nan"))
    rank = _num(row.get("selected_rank"), default=float("nan"))
    if pd.notna(distance_from_home):
        parts.append(f"距住家 {distance_from_home:.0f}m")
    if pd.notna(selected_distance):
        parts.append(f"選定距離 {selected_distance:.0f}m")
    if pd.notna(nearest_distance):
        parts.append(f"最近候選 {nearest_distance:.0f}m")
    if pd.notna(distance_gap):
        parts.append(f"距離差 {distance_gap:.0f}m")
    if pd.notna(rank) and rank > 0:
        parts.append(f"排名 {rank:.0f}")
    reason = str(row.get("risk_reason_text", "") or "").strip()
    if reason:
        parts.append(reason)
    return " / ".join(parts) if parts else "無額外風險證據"


def add_event_risk_drilldown_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    if result.empty:
        result["event_risk_focus"] = []
        result["event_evidence_summary"] = []
        result["risk_priority"] = []
        return result
    result["event_risk_focus"] = result.apply(event_risk_focus, axis=1)
    result["event_evidence_summary"] = result.apply(event_evidence_summary, axis=1)
    result["risk_priority"] = result.apply(risk_priority, axis=1)
    return result


def _risk_bucket(row: pd.Series) -> str:
    level = str(row.get("risk_level", row.get("覆核狀態", "")) or "")
    score = _num(row.get("risk_score", row.get("風險分數", 0)))
    if "高風險" in level:
        return "高風險"
    if "需覆核" in level:
        return "需覆核"
    if "低信心" in level:
        return "低信心"
    return "需覆核" if score > 0 else "正常"


def _place_risk_summary(row: pd.Series) -> str:
    parts = [
        f"{label} {int(row.get(label, 0))}"
        for label in ["高風險", "需覆核", "低信心", "正常"]
        if int(row.get(label, 0)) > 0
    ]
    return " / ".join(parts) if parts else "無拜訪紀錄"


def summarize_place_risk_visits(
    dataframe: pd.DataFrame,
    name_col: str = "selected_hospital_name",
    tag_col: str = "selected_client_tag",
) -> pd.DataFrame:
    columns = [
        "地點名稱",
        "客戶類型",
        "拜訪次數",
        "高風險",
        "需覆核",
        "低信心",
        "正常",
        "風險拜訪次數",
        "主要風險等級",
        "主要風險原因",
        "地點風險摘要",
    ]
    if dataframe.empty or name_col not in dataframe.columns:
        return pd.DataFrame(columns=columns)

    selected = dataframe.loc[dataframe[name_col].notna()].copy()
    if selected.empty:
        return pd.DataFrame(columns=columns)

    selected[tag_col] = selected[tag_col].fillna("未標示") if tag_col in selected.columns else "未標示"
    selected = add_event_risk_drilldown_columns(selected)
    selected["risk_bucket"] = selected.apply(_risk_bucket, axis=1)

    grouped = (
        selected.groupby([name_col, tag_col, "risk_bucket"], dropna=False)
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for bucket in ["高風險", "需覆核", "低信心", "正常"]:
        if bucket not in grouped.columns:
            grouped[bucket] = 0

    top_rows = (
        selected.sort_values(["risk_priority", "risk_score"], ascending=[False, False])
        .groupby([name_col, tag_col], dropna=False)
        .head(1)
        [[name_col, tag_col, "risk_bucket", "event_risk_focus"]]
        .rename(columns={"risk_bucket": "主要風險等級", "event_risk_focus": "主要風險原因"})
    )

    summary = grouped.merge(top_rows, on=[name_col, tag_col], how="left")
    summary["拜訪次數"] = summary[["高風險", "需覆核", "低信心", "正常"]].sum(axis=1).astype(int)
    summary["風險拜訪次數"] = summary[["高風險", "需覆核", "低信心"]].sum(axis=1).astype(int)
    summary["主要風險等級"] = summary["主要風險等級"].fillna("正常")
    summary["主要風險原因"] = summary["主要風險原因"].fillna("未見明顯風險")
    summary["地點風險摘要"] = summary.apply(_place_risk_summary, axis=1)
    summary = summary.rename(columns={name_col: "地點名稱", tag_col: "客戶類型"})
    return (
        summary[columns]
        .sort_values(["風險拜訪次數", "高風險", "需覆核", "拜訪次數", "地點名稱"], ascending=[False, False, False, False, True])
        .reset_index(drop=True)
    )


def summarize_top_risk_day(dataframe: pd.DataFrame) -> dict[str, Any]:
    daily = add_daily_risk_drilldown_columns(dataframe)
    if daily.empty or daily["risk_priority"].max() <= 0:
        return {"date": "", "hint": "未見明顯風險日期", "risk_score": 0, "primary_risk_reason": "未見明顯風險"}
    top = daily.sort_values(["risk_priority", "risk_score"], ascending=[False, False]).iloc[0]
    date = _date_text(top.get("work_date", top.get("日期")))
    return {
        "date": date,
        "hint": f"優先查看 {date} 日報表",
        "risk_score": _num(top.get("risk_score", top.get("風險分數"))),
        "primary_risk_reason": top.get("primary_risk_reason", ""),
    }
