# Function Route Report

外勤業務路徑、院所拜訪、里程申報與 HR/財務稽核報表工具。

本 repo 是正式版工作專案，包含資料匯入、清理、院所匹配、路線估算、風險判讀、Streamlit 操作介面與 PDF/CSV 匯出功能。公開展示用的輕量版 demo 另放在 [`fordissi/route-audit-demo`](https://github.com/fordissi/route-audit-demo)。

## 主要功能

- 匯入 104 HR 打卡匯出 Excel，整理為出勤日、GPS 打卡點與原始事件資料。
- 維護員工主檔、既有客戶資料與醫療院所公開資料。
- 將 GPS 點與院所/客戶候選點做距離匹配，產生拜訪點判讀依據。
- 估算單日路線、總里程、公務里程、移動時間與路徑信心。
- 支援 Google Routes API 快取與診斷，降低重複查詢成本。
- 稽核月申報里程與系統估算里程差異，提供綠/黃/紅燈參考。
- 產生日風險、員工風險、事件風險與全業務總覽。
- 提供單日路徑、週路徑、個人期間報表、全業務總覽與資料品質頁面。
- 匯出全業務總覽 PDF、個人期間 PDF、全部業務個人期間 PDF ZIP，以及 CSV/Excel 參考報表。

## 目前報表重點

- **單日路徑檢視**：查看單一業務某日 GPS 點、候選院所、路線摘要與財務摘要。
- **週路徑檢視**：以週為單位檢視每日拜訪脈絡與風險訊號。
- **個人期間報表**：支援月報、週報與自訂區間，包含里程、風險、申報差異與 PDF 匯出。
- **全業務總覽**：以日期區間彙整所有業務的里程、風險排名、月趨勢、申報差異與 PDF 匯出。
- **路徑核算調整**：可針對路段排除、通勤里程或特殊路線狀況進行核算修正。
- **資料品質與說明**：檢查匯入資料、GPS、院所匹配、Google Routes 與報表指標說明。

## 專案結構

- `app.py`：正式版 Streamlit app。
- `demo_app.py`：由正式版抽取出的本機 demo app，不是公開 demo repo 的部署主檔。
- `pipeline.py`：資料處理主流程。
- `checkin_importer.py`：打卡 Excel 匯入與事件整理。
- `master_data_service.py`：員工、客戶、院所主檔載入。
- `matcher.py`：GPS 與院所/客戶候選點匹配。
- `routing_engine.py`：路線與里程估算。
- `google_routes_service.py`：Google Routes API 快取、查詢、診斷與排除路段支援。
- `risk_service.py` / `risk_presentation.py`：風險判讀與呈現欄位。
- `finance_auditor.py`：月申報里程與補貼稽核。
- `overview_pdf_exporter.py`：全業務總覽 PDF 匯出。
- `personal_period_pdf_exporter.py`：個人期間 PDF 匯出。
- `personal_period_batch_exporter.py`：全部業務個人期間 PDF ZIP 匯出。
- `tools/`：demo data、demo app、PDF/Google Sheet 輔助工具。
- `tests/`：核心邏輯與匯出功能測試。

## 本機執行

建議使用 Python 3.13 或目前開發環境相容版本。

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

如果系統的 `python` 指令不可用，也可以使用 Windows Python launcher：

```bash
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

## 產出目錄

執行 pipeline 或 Streamlit app 後，輸出會放在 `outputs/`：

- `outputs/cleaned/`：清理後 CSV，例如出勤日、路線摘要、風險摘要、財務稽核結果。
- `outputs/database/`：SQLite 資料庫與 Google Routes 快取。
- `outputs/reports/`：PDF、ZIP、CSV、run summary 與匯入紀錄。
- `outputs/templates/`：月申報與出勤補充資料範本。
- `outputs/logs/`：執行紀錄與診斷資訊。

## 資料與隱私

正式版 repo 的根目錄資料檔，例如 `employees.csv`、`hospitals.csv`、`existing_clients.csv`、`monthly_claims.csv` 與打卡 Excel，視為本機資料來源。`.gitignore` 已排除多數正式資料、輸出結果、資料庫與 PDF，以避免誤提交敏感資訊。

`demo_data/` 則是可追蹤的小型展示 fixture，用於本機 demo 生成器與功能驗證；其中院所資料只保留足以覆蓋北區醫院、南區醫院、北區診所藥局與中區混合通路的少量公開資料。公開部署用的 standalone demo 仍以 `route-audit-demo` repo 為主。

歷史產出的 sample PDF、正式根目錄 CSV 與打卡 Excel 都應留在本機，不納入 Git 追蹤。若需要重新產生 PDF 範例，請從 Streamlit app 或匯出器產出到 `outputs/reports/`。

## 測試

```bash
py -m pytest
```

目前測試涵蓋：

- 匯入與資料庫 schema
- 院所 geocode 匯入
- GPS/院所匹配
- 路段排除
- 風險判讀與呈現欄位
- PDF 匯出與批次 ZIP
- demo data 生成器

## Demo Repo

公開展示版位置：

[`fordissi/route-audit-demo`](https://github.com/fordissi/route-audit-demo)

它是獨立的 Streamlit Cloud 部署 repo，內容較小，使用合成資料展示四個月趨勢、A/B/C/D 業務角色與單日路徑稽核故事。正式版的新概念若要公開展示，建議轉譯成非敏感、合成資料後再同步到 demo repo。
