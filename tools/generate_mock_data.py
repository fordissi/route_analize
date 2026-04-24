import os
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

# 加入專案根目錄到 sys.path 以便 import 本地模組
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from settings import build_config
from pipeline import run_pipeline

def generate_mock_data():
    demo_dir = project_root / "demo_data"
    demo_dir.mkdir(parents=True, exist_ok=True)
    
    print("Generating hospitals.csv...")
    hospitals = pd.DataFrame([
        {"機構代碼": "H001", "機構名稱": "台北醫學大學附設醫院", "Response_Y": 25.025, "Response_X": 121.561, "電話": "", "縣市區名": "信義區", "地址": "", "科別": "", "Response_Address": ""},
        {"機構代碼": "H002", "機構名稱": "台大醫院", "Response_Y": 25.041, "Response_X": 121.525, "電話": "", "縣市區名": "中正區", "地址": "", "科別": "", "Response_Address": ""},
        {"機構代碼": "H003", "機構名稱": "馬偕紀念醫院", "Response_Y": 25.050, "Response_X": 121.516, "電話": "", "縣市區名": "中山區", "地址": "", "科別": "", "Response_Address": ""},
        {"機構代碼": "H004", "機構名稱": "台北市立聯合醫院和平院區", "Response_Y": 25.036, "Response_X": 121.506, "電話": "", "縣市區名": "中正區", "地址": "", "科別": "", "Response_Address": ""},
        {"機構代碼": "H005", "機構名稱": "三軍總醫院", "Response_Y": 25.070, "Response_X": 121.593, "電話": "", "縣市區名": "內湖區", "地址": "", "科別": "", "Response_Address": ""},
    ])
    hospitals.to_csv(demo_dir / "hospitals.csv", index=False, encoding="utf-8-sig")

    print("Generating existing_clients.csv...")
    clients = pd.DataFrame([
        {"機構代碼": "H001", "機構名稱": "台北醫學大學附設醫院"},
        {"機構代碼": "H002", "機構名稱": "台大醫院"},
        {"機構代碼": "H003", "機構名稱": "馬偕紀念醫院"},
    ])
    clients.to_csv(demo_dir / "existing_clients.csv", index=False, encoding="utf-8-sig")

    print("Generating employees.csv...")
    employees = pd.DataFrame([
        {
            "員工編號": "E001",
            "姓名": "王專員",
            "department": "業務一部",
            "Home_Lat": 25.030,
            "Home_Lon": 121.550,
            "fuel_rate_override": "",
            "maintenance_rate_override": ""
        },
        {
            "員工編號": "E002",
            "姓名": "李專員",
            "department": "業務二部",
            "Home_Lat": 25.060,
            "Home_Lon": 121.600,
            "fuel_rate_override": "",
            "maintenance_rate_override": ""
        }
    ])
    employees.to_csv(demo_dir / "employees.csv", index=False, encoding="utf-8-sig")

    print("Generating monthly_claims.csv...")
    monthly_claims = pd.DataFrame([
        {
            "year_month": "2026-04",
            "employee_id": "E001",
            "claimed_km": 15.0,
            "claim_source": "manual",
            "submitted_at": "2026-05-01 10:00:00",
            "remark": "常規申報"
        },
        {
            "year_month": "2026-04",
            "employee_id": "E002",
            "claimed_km": 85.0,
            "claim_source": "manual",
            "submitted_at": "2026-05-01 10:00:00",
            "remark": "跨區異常里程申報"
        }
    ])
    monthly_claims.to_csv(demo_dir / "monthly_claims.csv", index=False, encoding="utf-8-sig")

    print("Generating mock_attendance.xlsx...")
    # 建立 104 打卡匯出格式
    # 第一列到第五列為 header (1-5), index 0-4
    # 真實資料欄位在 index 5
    work_date = "2026-04-15"
    
        # ✅ 常規員工 E001 (王專員)
        ["1", "E001", "王專員", "業務一部", work_date, "25.025,121.561", "09:00", "09:10:00", "上班", "符合", "已處理", "GPS", "", "否", "", ""],
        ["1", "E001", "王專員", "業務一部", work_date, "25.041,121.525", "11:00", "11:05:00", "外勤", "符合", "已處理", "GPS", "", "否", "", ""],
        ["1", "E001", "王專員", "業務一部", work_date, "25.050,121.516", "14:00", "14:20:00", "外勤", "符合", "已處理", "GPS", "", "否", "", ""],
        ["1", "E001", "王專員", "業務一部", work_date, "25.050,121.516", "18:00", "18:05:00", "下班", "符合", "已處理", "GPS", "", "否", "", ""],

        # ❌ 非預期員工 E002 (李專員)
        ["2", "E002", "李專員", "業務二部", work_date, "25.060,121.600", "09:00", "09:30:00", "上班", "未打卡", "待處理", "GPS", "居家打卡", "否", "", ""],
        ["2", "E002", "李專員", "業務二部", work_date, "24.990,121.500", "12:00", "12:10:00", "外勤", "符合", "待處理", "GPS", "偏離業務熱區打卡", "否", "", ""],
        ["2", "E002", "李專員", "業務二部", work_date, "25.060,121.600", "18:00", "17:50:00", "下班", "符合", "待處理", "GPS", "返回起點", "否", "", ""],
    ]
    
    cols = ["#", "員工編號", "姓名", "部門", "工作日期", "打卡地址", "應刷卡時間", "實際打卡時間", "卡別", "比對結果", "異常處理", "來源", "備註", "超時出勤", "超時出勤原因", "超時出勤說明"]
    df_data = pd.DataFrame(events, columns=cols)
    
    with pd.ExcelWriter(demo_dir / "mock_attendance.xlsx", engine="openpyxl") as writer:
        df_data.to_excel(writer, index=False, startrow=5)
    
    print("Running pipeline to process mock data...")
    config = build_config(root_dir=demo_dir)
    # 把 mock_attendance 放進 config 預設的匯入路徑，讓 pipeline 可以吃
    import shutil
    config.attendance_import_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(demo_dir / "mock_attendance.xlsx", config.attendance_import_dir / "mock_attendance.xlsx")
    
    run_pipeline(config)
    print("Mock data generated successfully in demo_data/ !")

if __name__ == "__main__":
    generate_mock_data()
