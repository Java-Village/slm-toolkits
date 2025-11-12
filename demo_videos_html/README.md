# Solar Panel Maintenance System - Demo

專業的太陽能板維護系統展示頁面，包含完整的診斷流程演示。

## 📁 文件結構

```
demo_videos_html/
├── index.html          # 主展示頁面
├── yolo.jpg           # YOLO 檢測結果圖片（需要準備）
├── rover.jpg          # Rover 維修圖片（需要準備）
└── README.md          # 本文件
```

## 🎯 功能特色

### 1. 專業 Dashboard

- **深色主題**：參考 Jupiter 風格的現代化深色界面
- **實時數據卡片**：
  - 總發電量（Total Power Output）
  - 系統效率（System Efficiency）
  - 活躍面板數（Active Panels）
  - 每日收益（Daily Revenue）
- **動態圖表**：
  - 24 小時發電量趨勢圖（折線圖）
  - 面板性能柱狀圖
- **狀態徽章**：顯示系統健康狀態

### 2. AI Chatbox

- **Streaming 效果**：機器人回應逐字顯示
- **圖片淡入動畫**：診斷圖片優雅呈現
- **打字指示器**：三點動畫顯示 AI 思考中

### 3. 完整演示流程

#### 初始狀態（異常）

- 發電量：2.8 kW（低於正常 35%）
- 系統效率：52%（危險）
- 活躍面板：14/18（4 個離線）
- 圖表顯示異常數據（紅色警告）

#### 演示步驟

1. **用戶輸入**：`Run a full diagnostic`

2. **AI 回應 - 診斷掃描**：

   ```
   🔍 Initiating full system diagnostic...
   ✓ Scanning panel array
   ✓ Analyzing power output
   ✓ Checking sensor data
   ```

3. **AI 回應 - 故障檢測**：

   ```
   ⚠️ Fault detected in panels P-002 and P-004.

   Issue: Dust accumulation and debris blocking solar cells.
   Estimated power loss: 35%

   Initiating drone deployment for inspection...
   ```

   附圖：`yolo.jpg`（YOLO 檢測結果）

4. **AI 回應 - Rover 部署**：

   ```
   🚀 Deploying maintenance rover to affected panels...

   ✓ Route calculated
   ✓ Rover en route
   ✓ ETA: 2 minutes
   ```

5. **AI 回應 - 任務完成**：

   ```
   ✅ Rover has completed cleaning operations.

   Panels cleaned: P-002, P-004
   Returning to base station...
   ```

   附圖：`rover.jpg`（Rover 維修圖片）

6. **AI 回應 - 系統恢復**：

   ```
   🎉 All systems are now functioning within optimal parameters!

   ✓ Power output: 4.5 kW (100%)
   ✓ System efficiency: 94%
   ✓ All panels online: 18/18
   ✓ Revenue target: Met

   Diagnostic complete. System operating normally.
   ```

#### 最終狀態（正常）

- 發電量：4.5 kW（100%）
- 系統效率：94%（優秀）
- 活躍面板：18/18（全部在線）
- 圖表恢復正常（綠藍色）
- 狀態徽章：System Optimal

## 🖼️ 圖片資源

Demo 使用專案中現有的圖片：

### yolo.jpg

- 位置：`../yolo.jpg`（專案根目錄）
- 內容：YOLO 物件檢測結果
- 用途：顯示故障檢測結果

### panel_healthy.png

- 位置：`../outside/coordination-server/images/panel_healthy.png`
- 內容：清潔後的太陽能板
- 用途：顯示 Rover 完成維修後的結果

✅ **無需額外準備圖片，直接使用即可！**

## 🚀 使用方式

1. **開啟展示**：

   - 直接在瀏覽器中開啟 `index.html`
   - 或使用 Live Server

2. **啟動演示**：
   - 在輸入框輸入：`Run a full diagnostic`
   - 點擊 Send 按鈕或按 Enter
   - 坐下來欣賞完整的自動演示流程

## 🎨 設計特色

### 顏色方案（參考現代化設計）

- **主背景**：深色綠黑漸層 (#0a0a0a → #1a2a1a → #2d3d1a)
- **主色調**：霓虹綠黃漸層 (#76ff03 → #cddc39)
- **警告色**：鮮紅色 (#ff5252)
- **成功色**：霓虹綠 (#76ff03)
- **文字色**：淡綠灰 (#e8f5e9)

### 專業 SVG 圖標

- ✅ 太陽能板圖標（Solar Panel Icon）
- ✅ AI 機器人圖標（Robot Icon）
- ✅ 用戶頭像圖標（User Avatar Icon）
- ✅ 無使用 Emoji，純 SVG 設計
- ✅ 所有圖標支援填充色變化

### 動畫效果

- 訊息淡入（fadeIn）
- 圖片淡入（fadeInImage）
- 打字指示器（typing dots）
- 卡片懸停效果（hover transform）
- 狀態點脈衝（pulse）

### 響應式設計

- 使用 CSS Grid 佈局
- 左側 Dashboard：自適應寬度
- 右側 Chatbox：固定 500px

## 🛠️ 技術棧

- **HTML5**：語義化標籤
- **CSS3**：
  - Grid Layout
  - Flexbox
  - Animations
  - Backdrop Filter（毛玻璃效果）
  - Gradients
- **JavaScript**：
  - Async/Await
  - DOM 操作
  - Promise
- **Chart.js**：圖表庫（CDN）

## 📝 自訂設置

### 調整 Streaming 速度

在 `addMessage` 函數中修改：

```javascript
const interval = setInterval(() => {
  // ...
}, 30); // 降低數字 = 更快，提高數字 = 更慢
```

### 調整延遲時間

在 `runDiagnosticDemo` 函數中修改各步驟的延遲：

```javascript
await new Promise((resolve) => setTimeout(resolve, 2000)); // 2秒延遲
```

### 修改數據

在腳本中找到 `abnormalData` 和 `normalData` 物件來修改圖表數據。

## 🎬 錄製建議

1. **準備**：

   - 全螢幕瀏覽器（F11）
   - 隱藏工具列
   - 確保圖片已就位

2. **錄製流程**：

   - 開始時顯示異常的 Dashboard（紅色警告）
   - 輸入指令並按下 Send
   - 讓整個流程自動完成
   - 最後顯示恢復正常的綠色 Dashboard

3. **時長**：約 15-20 秒（可調整各步驟延遲）

## 📄 授權

此展示頁面為專案內部使用，請勿用於商業用途。
