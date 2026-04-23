# Google Routes API 申請與使用說明

本文件說明如何申請 Google Routes API、啟用計費、建立 API Key，以及在本專案中使用。

## 1. 申請前準備

你需要：
- 一個 Google 帳號
- 一個 Google Cloud 專案
- 可綁定的 Billing 帳戶

官方文件：
- [Set up the Routes API](https://developers.google.com/maps/documentation/routes/get-api-key)
- [Routes API Pricing](https://developers.google.com/maps/billing-and-pricing/pricing)
- [Routes API Usage and Billing](https://developers.google.com/maps/documentation/routes/usage-and-billing)

## 2. 建立與設定 Google Cloud 專案

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 建立新專案，或選擇既有專案
3. 到 `Billing` 綁定付款帳戶

注意：
- 沒有啟用 Billing，Routes API 無法正常使用

## 3. 啟用 Routes API

1. 在 Cloud Console 搜尋 `Routes API`
2. 進入 API 頁面
3. 按下 `Enable`

官方入口：
- [Set up the Routes API](https://developers.google.com/maps/documentation/routes/get-api-key)

## 4. 建立 API Key

1. 到 `APIs & Services` → `Credentials`
2. 點 `Create Credentials`
3. 選 `API key`
4. 複製建立好的 key

## 5. 建議的 API Key 限制

建立完成後，務必設定限制：

### API restrictions
- 只允許：
  - `Routes API`

### Application restrictions
- 若是內部批次工具或固定機器執行：
  - 建議限制 IP 位址
- 若未來改成 Web：
  - 改成限制 HTTP referrer

官方建議：
- [API security best practices](https://developers.google.com/maps/api-security-best-practices)

## 6. 本專案如何使用 API Key

本專案提供兩種方式：

### 方式 A：頁面手動貼上
1. 開啟 `Google Routes 執行` 頁面
2. 在 `Google Maps API Key` 欄位貼上 key
3. 選擇日期區間
4. 按 `手動執行 Google Routes 計算`

### 方式 B：環境變數

PowerShell：

```powershell
$env:GOOGLE_MAPS_API_KEY="你的_api_key"
streamlit run app.py
```

之後頁面會自動讀取這個環境變數。

## 7. 執行流程

建議實務流程：

1. 每月匯入前月打卡檔
2. 到 `Google Routes 執行` 頁面
3. 看 `Google Routes API 月度用量估算器`
4. 確認 API Key 與日期區間
5. 手動執行
6. 系統把結果寫入 SQLite 快取
7. 後續報表與地圖優先讀快取結果

## 8. 本專案目前怎麼呼叫 Routes API

本專案目前使用：
- `computeRoutes`
- `travelMode = DRIVE`
- `routingPreference = TRAFFIC_AWARE`

回傳欄位：
- `distanceMeters`
- `duration`
- `polyline`

用途：
- 路徑距離
- 預估行車時間
- 真實道路折線顯示

官方文件：
- [Get a route](https://developers.google.com/maps/documentation/routes/compute_route_directions)
- [Request route polylines](https://developers.google.com/maps/documentation/routes/traffic_on_polylines)

## 9. 快取機制

為避免重複估算與重複計費，本專案會把 Google Routes 結果存到 SQLite：

- `google_route_cache`
- `google_route_summary`

流程：
- 先查快取
- 沒有才打 API
- 算完就寫回本地

因此：
- 不需要每次開頁面都重算
- 也能避免浪費免費額度

## 10. 關於 polyline 與計費

### basic polyline
- 不會把一次請求變成多次事件
- 仍然是同一個 `ComputeRoutes` request
- 適合用來顯示實際道路路徑

### traffic-aware polyline
- 也不是增加請求數量
- 但可能套用較高計價層級

因此目前專案建議：
- 先用 `basic polyline`
- 不開 traffic-aware polyline

## 11. 本專案目前支援的手動執行頁面

在介面中：
- `首頁流程`
- `Google Routes 執行`

都能引導你進行 Routes API 相關操作。

## 12. 常見問題

### Q1. 沒執行 Google Routes 會怎樣？
- 系統會回到原本的離線估算模式

### Q2. 執行過一次之後還會重算嗎？
- 不會
- 有快取就優先讀快取

### Q3. 如果我重新匯入新打卡資料？
- 新的路徑段會產生新的快取鍵
- 只有新資料才需要再打 API

### Q4. 如果我更換 API Key？
- 只要新的 key 有啟用 Routes API 並綁定 billing，就可繼續使用

## 13. 官方參考連結

- [Set up the Routes API](https://developers.google.com/maps/documentation/routes/get-api-key)
- [Get a route](https://developers.google.com/maps/documentation/routes/compute_route_directions)
- [Request route polylines](https://developers.google.com/maps/documentation/routes/traffic_on_polylines)
- [Routes API Usage and Billing](https://developers.google.com/maps/documentation/routes/usage-and-billing)
- [Google Maps Platform Pricing](https://developers.google.com/maps/billing-and-pricing/pricing)
