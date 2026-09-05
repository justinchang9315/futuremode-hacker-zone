# 前端說明

`index.html` 是**單一靜態檔案**，沒有建置流程、沒有 npm、沒有打包步驟。改完存檔、
重新整理瀏覽器就生效。

## 啟動

最簡單的方式是讓後端一併提供前端。從儲存庫根目錄：

```powershell
cd backend
uv run uvicorn app.main:app --reload
```

然後開啟 **<http://127.0.0.1:8000/>**。前端、3D 模型與 API 都由這一個服務提供，
和部署到公開網址後的行為完全一致。

### 單獨跑前端（可選）

想用獨立的靜態伺服器時，另開一個終端機：

```powershell
cd index
python -m http.server 5173
```

開啟 `http://127.0.0.1:5173`。這時後端仍需在 8000 埠啟動。

## 後端位址怎麼決定

`index.html` 的 `API_BASE` 會自動判斷，**不需要重新編譯或修改程式碼**：

| 情境 | 使用的後端位址 |
| --- | --- |
| 網址帶 `?api=...` | 以參數為準 |
| 埠是 5173 或 3000（本機開發） | `http://localhost:8000/v1` |
| 其他（含部署後） | 同源，也就是 `目前網域/v1` |

所以部署時前後端同源，沒有 CORS 問題。只有在「前端單獨跑」時才受 `CORS_ORIGINS` 限制 ——
`backend/.env` 預設只放行 3000 與 5173 兩個埠，用其他埠會被擋掉，畫面右上角會顯示
「後端未連線」。

要指到別台後端測試時：

```text
http://127.0.0.1:5173/?api=http://127.0.0.1:8010/v1
```

不要直接雙擊 `index.html`，`file://` 來源會被瀏覽器擋掉。

## 瀏覽器

建議使用最新版 Chrome 或 Edge，才有繁體中文的 Web Speech Recognition。不支援時，
家長可展開朗讀卡下方的「文字備援」貼上逐字稿完成 Demo。

語音合成優先使用後端的 VoAI（台灣口音），失敗或未設定時自動退回瀏覽器內建語音。

## 這個版本已接上的後端能力

| 畫面位置 | 後端 API |
| --- | --- |
| 家長確認彈窗（問名字＋三項確認） | `POST /v1/sessions`（帶 `display_name`） |
| 故事森林・教材下拉選單、逐字注音 | `GET /v1/content`（含 `zhuyin` 陣列） |
| 故事森林・開始朗讀／文字備援 | `POST /v1/reading-attempts/transcript` |
| 分數面板・這次拿到的獎勵 | 來自 `POST /v1/reading-attempts/transcript` 回傳的 `rewards` |
| 分數面板的 👍👎 | `POST /v1/feedback` |
| 點小芽 → 對話視窗 | `POST /v1/dialogue` |
| 學習成果卡（金幣、鑽石、兌換） | `GET /v1/children/{id}/wallet`、`/level`、`/inventory`、`GET /v1/reward-catalog`、`POST /v1/rewards/redeem` |
| 家長專區・核准 Level 3 | `PUT /v1/children/{id}/level-3-approval` |
| 家長專區・結束這次學習 | `POST /v1/sessions/{id}/end` + `GET /v1/sessions/{id}/summary` |
| 家長專區・刪除本機孩童資料 | `DELETE /v1/children/{id}` |
| 右上角連線狀態 | `GET /v1/health` |
| Demo 控制台・Lv.1/2/3 切換 | `PUT /v1/children/{id}/demo-level`（**只在 development 環境開放**） |

## 資料保存

| 存什麼 | 存哪裡 | 活多久 |
| --- | --- | --- |
| 評分、獎勵、等級、精通紀錄 | 後端 SQLite `backend/companion.db` | 永久（除非家長按刪除） |
| `child_id` | 瀏覽器 `localStorage` | 永久（換瀏覽器或清網站資料才會沒） |
| 這台裝置的孩子名冊（`xiaoya-children`：暱稱＋`child_id`） | 瀏覽器 `localStorage` | 同上，最多 8 位 |
| session 權杖 | 瀏覽器 `sessionStorage` | 關掉分頁就沒 |
| 道具裝飾狀態 | 瀏覽器 `localStorage`（依 `child_id` 分開） | 同 `child_id` |

建立學習階段時前端會把記住的 `child_id` 一起送出，後端就沿用同一個 `ChildProfile`，
**金幣、等級、精通篇數會跨次累積**。沒帶 `child_id` 的話後端每次都會建一個新孩子，
成長紀錄就會從零開始。

記住的孩子若已被刪除，後端回 404，前端會自動改用新孩子重試。
家長專區的「換一位孩子」會忘掉這台裝置記住的 `child_id`（後端紀錄保留），
「刪除本機孩童資料」則會連後端資料一起刪掉。

學習階段有時間上限，右上角會倒數，歸零時自動結束並顯示家長摘要。
上限由 `backend/.env` 的 `SESSION_DURATION_MINUTES` 控制（預設 10 分鐘，範圍 5–60）。

## 三個畫面

畫面之間用同一頁切換，不會重新載入，3D 小芽只有一個 WebGL renderer，會跟著畫面搬家。

1. **學習島（首頁）** — 地圖、成長進度與獎勵兌換。方向鍵／WASD 或點地圖可以移動小芽。
2. **故事森林** — 點地圖上的「故事森林」島直接進入。教材選擇、朗讀、分數與 👍👎 回饋都在這裡。
3. **和小芽獨處** — 點小芽（地圖上的小貓、故事森林裡的 3D 小芽，或「💬 和小芽獨處」按鈕）進入。
   小芽的房間 + 道具箱 + 成長面板 + 對話框，最下面另有 Demo 展示控制台。

### 小芽的房間

房間背景會隨小芽的情緒換色：開心（`happy`／`jump`／`greeting`／`wave`／`freeRoam`／`bellyUp`）用暖色，
低落（`sad`／`confused`／`shake`／`thinking`）用冷色，其餘維持中性米色，過渡 1.1 秒。
情緒由後端回傳的 `body_actions` 驅動，左下角的標籤會顯示目前心情。

### 道具箱與升級

| 動作 | 由誰負責 |
| --- | --- |
| 兌換星星徽章（🪙 20）／冠軍獎盃（🪙 30）／藍色光環（💎 1） | 後端 `POST /v1/rewards/redeem` |
| 裝飾：把徽章與獎盃放上架子、幫小芽點亮光環 | **前端本機**，存在 `localStorage`（key：`xiaoya-equipped-<child_id>`） |
| 升級 Level 1 → 2 → 3 | 後端 `evaluate_progression`，看累積金幣／鑽石與完成／精通篇數 |

後端的 `RewardItemOwnership` 有 `equipped` 欄位，但**沒有開設定它的 API**，所以裝飾狀態只存在本機，
換瀏覽器或清掉網站資料就會回到未裝飾。刪除孩童資料時會一併清除。

**道具不能拿來升級**：升級條件是完成朗讀累積的成果，兌換道具只扣「餘額」不扣「累積量」，
所以買道具不會讓小芽退級，但也不會讓牠升級。成長面板顯示的門檻寫死在 `index.html` 的 `LEVEL_RULES`，
對應 `backend/.env` 的這四個值，改 `.env` 時要一起改：

```dotenv
LEVEL_2_LIFETIME_COINS=30
LEVEL_2_COMPLETED_CONTENTS=2
LEVEL_3_LIFETIME_GEMS=2
LEVEL_3_MASTERED_CONTENTS=2
```

目前只有 3 篇教材、每篇滿分給 10 金幣 + 1 鑽石，所以要升到 Level 2 得把三篇都念完。

### 選取文字問注音

孩子把看不懂的字**選取**起來（滑鼠拖曳或長按選字），畫面會浮出確認框問
「「探索」這幾個字，你不知道怎麼念嗎？」，按「對，教我念」之後才把選取範圍包成
`<ruby>` 並唸出來。和詩的「點一個字」是同一套邏輯：**先問，再給答案**。

注音向後端 `POST /v1/zhuyin` 即時索取，結果存在記憶體快取。
標好的字再點一次會重唸一遍。

只要畫面上有任何注音，左下角就會出現「**↩ 取消注音**」，
一次把整頁的注音收乾淨 — 包含選取標的 `<ruby>` 和詩裡點過的字。
`<ruby>` 會換回原本的字並 `normalize()` 合併文字節點，往返無損。

限制與跳過的區塊：

- 只接受**落在同一個文字節點內**的選取（跨元素改寫 DOM 有風險，直接不回應）
- 一次最多 60 字
- `.no-zhuyin` 的區塊跳過：家長確認彈窗、家長專區、學習摘要、Demo 展示控制台、品牌字
- 詩的區塊 `#poemText` 跳過，它有自己的逐字機制

### 朗讀的靜音逾時

瀏覽器的 Web Speech API 大約 3–5 秒沒聲音就會自己結束，對還在想下一句的孩子太短。
前端改用 `continuous` 模式加上自己的靜音碼錶，常數在 `index.html`：

```js
const LISTEN_SILENCE_MS=5000;   // 連續 5 秒沒聲音才自動送出
```

瀏覽器中途自行結束時會自動接回去繼續聽；超過 1.5 秒沒聲音會在按鈕下方顯示倒數。
孩子也可以再按一次錄音鍵提早送出。

**朗讀和跟小芽聊天共用同一個 `startListening()` helper**。「和小芽獨處」的輸入框
左邊有麥克風按鈕，說話時逐字稿會即時填進輸入框，靜音 5 秒（或再按一次麥克風）
就自動送出。打字仍然可用。

### Demo 展示控制台

在「和小芽獨處」畫面最下方，分成兩區：

- **角色等級** — Lv.1／Lv.2／Lv.3 三顆按鈕，打 `PUT /v1/children/{id}/demo-level`，
  真的改寫 `child.current_level`，所以之後的對話回應會跟著變（Lv.1 只有動作、Lv.2 固定短句、Lv.3 走 LLM）。
  這支 API 在 `ENVIRONMENT` 不是 `development` 時回 403，且需要家長權杖。
- **情緒與動作** — 12 顆按鈕，只改前端 3D 表演與房間色調，不會呼叫後端。

切到低等級後如果孩子已經達到升級門檻，下一次讀 `/level` 時後端會把等級算回去（這是正常的結算邏輯）。
要穩定展示各等級，建議用剛建立、還沒念過詩的 session。

每個子畫面左上角都有返回鍵。數學山丘、創作湖、回家基地標示「建置中」，點下去只會出現提示。

## 素材

`toon_cat.glb` 必須和 `index.html` 放在同一個資料夾（3D 小芽與地圖上的小貓共用這個模型）。
