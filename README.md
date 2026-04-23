# Function Route Report

依 `SDD_v2.md` 建立的 v1 原型，包含：

- 主檔清洗與 SQLite 匯入
- 104 打卡匯出解析與事件群組化
- 院所候選匹配與離線里程估算
- 財務稽核結果與 HR BI 基本指標
- Streamlit 檢視介面

## 執行

```bash
python run_project.py
streamlit run app.py
```

## 輸出目錄

- `outputs/cleaned/`: 清洗後明細與彙總 CSV
- `outputs/database/`: SQLite 資料庫
- `outputs/reports/`: 執行摘要
- `outputs/templates/`: 待補外部資料模板
