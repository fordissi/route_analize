# 指標與資料來源說明

本頁整理目前系統中主要指標、資料來源與計算邏輯，方便使用者理解畫面上的數據代表什麼。

## 1. 原始資料來源

### `20260422打卡資料匯出.xlsx`
- 來源：104 打卡匯出檔
- 用途：建立每日事件流、GPS 點位、上下班時間、異常標記
- 主要欄位：
  - `員工編號` / `姓名` / `部門`
  - `工作日期`
  - `應刷卡時間`
  - `實際打卡時間`
  - `卡別`
  - `打卡地址`
  - `比對結果`
  - `來源`

### `employees.csv`
- 來源：員工主檔
- 用途：顯示員工資訊、住家座標、通勤相關規則
- 目前用到：
  - `員工編號`
  - `姓名`
  - `Home_Lon`
  - `Home_Lat`

### `hospitals.csv`
- 來源：醫療院所主檔
- 用途：GPS 近鄰候選院所匹配
- 目前用到：
  - `機構代碼`
  - `機構名稱`
  - `Response_X`
  - `Response_Y`

### `existing_clients.csv`
- 來源：既有客戶名單
- 用途：標記候選院所是否為既有客戶

### `monthly_claims.csv`
- 來源：每月申請里程資料
- 用途：財務稽核比對
- 比對鍵值：
  - `year_month`
  - `employee_id`

### `attendance_aux.csv`
- 來源：補充制度資料
- 用途：日當費與制度相關計算
- 目前用到：
  - `attendance_uid`
  - `attendance_status`
  - `daily_report_submitted`
  - `meals_provided_count`

## 2. 單日路徑檢視

### 出勤時段
- 資料來源：`attendance_day_group.first_actual_time` 到 `last_actual_time`
- 說明：該日該員工最早與最晚的實際事件時間

### 打卡 / GPS 點數
- 資料來源：
  - 打卡次數：`attendance_day_group.event_count`
  - GPS 點數：`attendance_day_group.gps_event_count`

### 預估總里程
- 資料來源：`daily_route_summary.estimated_total_km`
- 計算方式：
  - 依當日 GPS 點位順序計算點對點直線距離
  - 再乘上 `Detour Index`
  - 若採 `hybrid_rule_based` 且員工有住家座標，會納入住家到首點、末點回住家的估算距離

### 預估公務里程
- 資料來源：`daily_route_summary.estimated_business_km`
- 計算方式：
  - 目前 v1 預設等於 `estimated_total_km`
  - 若未來有 `base_commute_km` 與制度啟用，會扣除通勤基準後得到公務里程

### 預估移動時間
- 資料來源：`daily_route_summary.estimated_travel_min`
- 計算方式：
  - `estimated_total_km / average_speed_kmph * 60`

### 預估通勤時間
- 資料來源：
  - 優先使用 `google_route_cache` 中的 `home_to_first` 與 `last_to_home` 路段時間
  - 若尚未執行 Google Routes，則用住家到首點、末點回住家的估算里程換算
- 計算方式：
  - `家 -> 第一個出勤地點` + `最後一個出勤地點 -> 家`
  - 用來協助判讀當日總打卡時數偏少時，是否因為出勤地點較遠

### 路徑信心
- 資料來源：`daily_route_summary.route_confidence`
- 計算方式：
  - 依當日匹配到的有效停留點比例計算
  - 目前公式：`0.45 + matched_stop_count / total_stop_count * 0.55`
  - 上限為 `1.0`

### 最近既有客戶
- 資料來源：醫療院所主檔 + 既有客戶名單
- 計算方式：
  - 從全部既有客戶院所中找出距離該打卡點最近者
  - 不受前五候選限制

### 最近醫院
- 資料來源：醫療院所主檔
- 計算方式：
  - 從全部院所主檔中挑選名稱可判定為「醫院」的最近者
  - 目前預設包含：
    - `醫院`
    - `衛生所`
    - `療養院`
  - 目前預設排除：
    - `診所`
    - `藥局`

### 系統選定院所
- 資料來源：`route_stop_match.is_selected = 1`
- 計算方式：
  - 先從較大的候選池中判斷優先序，再選出一筆
  - 目前優先序：
    - `既有客戶`
    - `1000 公尺內的醫院`
    - `潛在院所`

### 前五可能拜訪院所
- 資料來源：`route_stop_match`
- 計算方式：
  - 每個打卡點畫面上預設顯示最近的前 5 個候選院所
  - 若系統選定院所不在前 5 名，也會額外顯示該筆
  - 會顯示距離與院所類型（既有客戶 / 醫院 / 潛在院所）

## 3. 個人期間報表

期間報表支援：
- 月報
- 週報
- 自訂日期區間

### 出勤天數
- 計算方式：期間內 `attendance_uid` 去重後的筆數

### 總出勤時數
- 資料來源：`bi_daily_metrics.raw_span_minutes`
- 計算方式：
  - 期間內 `raw_span_minutes` 加總後除以 60

### 總有效外勤時數
- 資料來源：`bi_daily_metrics.effective_field_minutes`
- 計算方式：
  - 期間內 `effective_field_minutes` 加總後除以 60

### 總打卡次數
- 資料來源：`attendance_day_group.event_count`
- 計算方式：期間內加總

### 總 GPS 點數
- 資料來源：`attendance_day_group.gps_event_count`
- 計算方式：期間內加總

### 總計預估里程
- 資料來源：`daily_route_summary.estimated_total_km`
- 計算方式：期間內加總

### 總計預估公務里程
- 資料來源：`daily_route_summary.estimated_business_km`
- 計算方式：期間內加總

### 平均每日里程
- 資料來源：`daily_route_summary.estimated_total_km`
- 計算方式：期間平均值

### 平均每日公務里程
- 資料來源：`daily_route_summary.estimated_business_km`
- 計算方式：期間平均值

### 異常率
- 資料來源：`bi_daily_metrics.anomaly_flag`
- 計算方式：期間內異常日數 / 出勤日數

### 未打卡未處理次數
- 資料來源：`raw_check_events.compare_result`、`raw_check_events.exception_action`
- 計算方式：
  - 篩選 `compare_result = 未打卡`
  - 且 `exception_action = 待處理`
  - 以事件筆數加總
- 用途：
  - 作為考勤上「未打卡且尚未補請假單/公出單」的依據

### 超時出勤率
- 資料來源：`raw_check_events.overtime_flag`
- 計算方式：
  - 若該日任一事件的 `overtime_flag = *`
  - 則該 `attendance_uid` 視為超時出勤日
  - 期間內超時出勤日數 / 出勤日數

### 實際加班率
- 資料來源：`raw_check_events.overtime_flag`、`raw_check_events.overtime_reason`
- 計算方式：
  - 若該日任一事件滿足 `overtime_flag = *` 且 `overtime_reason = 實際加班`
  - 則該日視為實際加班日
  - 期間內實際加班日數 / 出勤日數

### 匹配院所總次數
- 資料來源：`daily_route_summary.matched_stop_count`
- 計算方式：期間內加總

### 月申請里程 vs 系統預估公務里程
- 資料來源：
  - `monthly_claims.csv.claimed_km`
  - `daily_route_summary.estimated_business_km`
- 計算方式：
  - 先將 `monthly_claims.csv.year_month` 正規化成 `YYYY-MM`
  - 再用 `employee_id + year_month` 聚合月申請里程
  - 系統端則用同員工同月份的 `estimated_business_km` 加總成月預估公務里程
  - 個人頁若選週報或自訂區間，會以涵蓋到的月份整月比較

### 最常拜訪院所
- 資料來源：`route_stop_match`
- 計算方式：
  - 篩選 `is_selected = 1`
  - 依院所名稱聚合統計拜訪次數

## 4. 全業務總覽

### 各業務總計預估里程比較
- 資料來源：`daily_route_summary.estimated_total_km`
- 計算方式：依員工於所選區間加總

### 異常率 vs 超時出勤率
- 資料來源：
  - `bi_daily_metrics.anomaly_flag`
  - `raw_check_events.overtime_flag`
- 計算方式：
  - 依員工於所選區間聚合

### 全業務未打卡未處理次數
- 資料來源：`raw_check_events.compare_result`、`raw_check_events.exception_action`
- 計算方式：
  - 依員工於所選區間加總 `未打卡且待處理` 的事件筆數

### 員工月申請里程 vs 系統預估公務里程
- 資料來源：
  - `monthly_claims.csv.claimed_km`
  - `daily_route_summary.estimated_business_km`
- 計算方式：
  - 先篩出所選日期區間涵蓋到的月份
  - 以月份整月為單位，彙總各員工的申請里程與預估公務里程
  - 用群組柱狀圖對照每位員工兩組數值

### 差異率排名
- 資料來源：
  - `monthly_claims.csv.claimed_km`
  - `daily_route_summary.estimated_business_km`
- 計算方式：
  - `差異里程 = 實際月申請里程 - 系統預估月公務里程`
  - `差異率 = 差異里程 / 實際月申請里程`
  - 以差異率絕對值排序顯示

### 月申請里程散點圖
- 資料來源：
  - `monthly_claims.csv.claimed_km`
  - `daily_route_summary.estimated_business_km`
- 計算方式：
  - X 軸為系統預估月公務里程
  - Y 軸為實際月申請里程
  - 參考線 `y = x` 代表申請值與預估值完全一致
  - 點越偏離參考線，代表差異越大

### 出勤時數與 GPS 點數比較
- 資料來源：
  - `bi_daily_metrics.raw_span_minutes`
  - `bi_daily_metrics.gps_event_count`

### 財務補貼總覽
- 資料來源：`finance_audit_result`
- 顯示項目：
  - `fuel_subsidy`
  - `maintenance_subsidy`
  - `per_diem_amount`

## 5. 財務稽核

### 月申請里程
- 資料來源：`monthly_claims.csv`

### 當日公務里程
- 資料來源：`finance_audit_result.approved_business_km`

### 燈號
- 資料來源：`finance_audit_result.audit_light`
- 計算方式：
  - 先用 `year_month + employee_id` 聚合月申請里程
  - 再與同月份的系統估算公務里程總和比較
  - 規則：
    - `green`：誤差 <= 15%
    - `yellow`：15% < 誤差 <= 30%
    - `red`：誤差 > 30%
    - `gray`：缺申請值或資料不足

### 油資補貼
- 資料來源：`finance_audit_result.fuel_subsidy`
- 計算方式：
  - `approved_business_km * fuel_rate`

### 維修補貼
- 資料來源：`finance_audit_result.maintenance_subsidy`
- 計算方式：
  - `approved_business_km * maintenance_rate`

### 日當費
- 資料來源：`attendance_aux.csv`
- 計算方式：
  - `normal` 且有交日報且未供兩餐：`300`
  - `half_day` 且未供餐：`150`
  - 若供餐達門檻則為 `0`

## 6. 參數設定頁

目前顯示的設定來自 [settings.py](C:\Users\fordi\antigravity\Personal Project\IDE_new_workstyle_test\HR\function_route_report\settings.py)，包含：
- 路徑模式
- Detour Index
- 平均時速
- 候選院所數量
- 信心距離閾值
- 財務補貼費率
- 休息時間
- 燈號閾值

目前為唯讀顯示頁，尚未支援 UI 直接修改後寫回設定檔。
