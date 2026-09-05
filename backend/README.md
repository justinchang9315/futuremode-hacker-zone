# 兒童 AI 學習夥伴後端

Phase I 的核心體驗是「孩子當小老師」：選擇公版唐詩、使用語音朗讀、取得可追溯的文字對照分數與獎勵，再逐步解鎖角色能力。

## 本機啟動

需要 Python 3.12 與 [`uv`](https://docs.astral.sh/uv/)。從**儲存庫根目錄**執行：

```powershell
cd backend
Copy-Item .env.example .env   # 已有 .env 時不要覆蓋
uv sync --dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

開啟 **<http://127.0.0.1:8000/>**。後端會一併提供 `index/` 的前端檔案，所以
**不需要另外啟動前端伺服器**：

| 路徑 | 內容 |
| --- | --- |
| `/` | 前端 |
| `/v1/...` | API |
| `/docs` | Swagger UI |

`.env.example` 預設 `LLM_PROVIDER=fake`、`TTS_PROVIDER=fake`，初次執行不需要任何 API Key。

### 只想單獨跑前端時（可選）

前端是單一 HTML 檔，改完重新整理即可，不需要重啟後端。若要用獨立的靜態伺服器：

```powershell
cd index
python -m http.server 5173
```

瀏覽 `http://127.0.0.1:5173`。這時前端會呼叫 `http://localhost:8000/v1`，所以後端仍需
啟動，而且埠必須是 5173 或 3000（`CORS_ORIGINS` 只放行這兩個）。不要直接雙擊 HTML，
`file://` 來源會被瀏覽器與 CORS 限制。

部署到公開網址的設定（`APP_SECRET_KEY`、`ENVIRONMENT`、金鑰、資料庫）見主
[README 的公開部署一節](../README.md#公開部署)。

## LLM Provider

`.env` 可同時保存各 Provider 欄位，但一次只會使用 `LLM_PROVIDER` 指定的一家：

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=你的_Gemini_Key
GEMINI_MODEL=你的可用模型
```

可選值為 `fake`、`gemini`、`openai`、`gmi_cloud`、`eastrouter`。EastRouter 必須同時設定 Key、Base URL 與 Model。正式部署必須另外設定長而隨機的 `APP_SECRET_KEY`。

## 小芽的聲音（VoAI TTS）

預設 `TTS_PROVIDER=fake`，前端用瀏覽器內建的 Web Speech Synthesis。改成 `voai` 就會走
[VoAI 絕好聲創](https://connect.voai.ai/doc-vocal/index.html) 的台灣口音聲優：

```dotenv
TTS_PROVIDER=voai
VOAI_API_KEY=你的_VoAI_Key
VOAI_SPEAKER=            # 留空會自動用清單第一位
```

**金鑰只留在後端。**前端呼叫 `POST /v1/tts`（body：`{"text": "..."}`，需要 `X-Session-Token`），
後端合成完把音檔位元組原樣回傳，瀏覽器用 `<audio>` 播。前端拿不到金鑰，也沒有任何地方會把它寫進頁面。

要權杖是因為 VoAI **按字扣點**（Classic／Neo 1 字 1 點、Sota+ 1 字 2 點），
不能開成任何人都打得到的免費轉語音。`MAX_TTS_CHARS`（預設 200）是單句字數上限，
前端另外把同一句話的音檔快取在記憶體裡，所以「再念一次」和重複點注音不會重複扣點。

`GET /v1/tts/speakers`（需要 `X-Guardian-Token`）會列出這把金鑰可用的聲優，
挑好名字再填回 `VOAI_SPEAKER`。其餘可調參數：`VOAI_MODEL`（`Neo`／`Classic`）、
`VOAI_STYLE`、`VOAI_SPEED`（0.5–1.5）、`VOAI_PITCH_SHIFT`（-5–5）、
`VOAI_STYLE_WEIGHT`（0–1）、`VOAI_BREATH_PAUSE`（0–10）、
`VOAI_OUTPUT_FORMAT`（`wav`／`mp3`）、`VOAI_SAMPLE_RATE`（8000／16000／32000／44100，留空用預設）。

Neo 的取樣率上限是 32000；`pcm` 是串流格式，`<audio>` 播不了，所以 factory 只接受 `wav` 與 `mp3`。

**任何一步失敗都不會讓小芽啞掉**：provider 是 fake 回 204、金鑰錯回 502、額度用完回 502，
前端一律自動退回瀏覽器內建語音，畫面照常進行。

## 注音標註

`GET /v1/content` 每筆會多回一個 `zhuyin` 陣列，長度與 `reference_text` 完全相同，
標點與非漢字為 `null`。前端用它做「點字問注音」。

`POST /v1/zhuyin`（body：`{"texts": ["...", ...]}`）則是給前端標**整個介面**用的批次端點，
回傳 `[{text, readings}]`。純字典查詢、不涉及孩童資料，所以不需要權杖；
一次最多 300 段、每段 400 字。

兩者共用 `app/domain/zhuyin.py`，用 `pypinyin` 依整句上下文推斷，所以破音字會對
（「花落知多少」是 ㄕㄠˇ、「少年」是 ㄕㄠˋ，「不是」會變調成 ㄅㄨˊ）。
新增教材或改介面文案都不需要手動維護對照表。

## 獎勵規則

只有評分狀態是 `FINAL`（信心足夠、聽得清楚）才會發獎勵，聽不清楚一律不計分也不扣分。

| 事由 | 給什麼 | 條件 | 頻率 |
| --- | --- | --- | --- |
| `FIRST_COMPLETION` | 🪙 10 | 評分成立 | 每篇教材一次 |
| `GOOD_READING` | 🪙 5 | 分數 ≥ `GOOD_READING_SCORE`（預設 60） | 每篇教材一次 |
| `PERSONAL_BEST_IMPROVEMENT` | 🪙 5 | 比自己前次最佳高 `PERSONAL_BEST_MIN_GAIN`（5）分以上 | 每次評分都可觸發 |
| `CONTENT_MASTERY` | 💎 1 | 分數 ≥ `MASTERY_SCORE`（80）且信心 ≥ `MASTERY_CONFIDENCE` | 每篇教材一次 |

設計原則是**只加不減**：念得不好仍拿得到完成獎勵，念得好則額外加碼。
這是為了符合 `PhaseI_6-8歲錨定_修訂建議.md` 對兒童挫折感的考量 —
辨識失敗要框架成「AI 的限制」而不是孩子的錯，所以低分不會比完成獎勵更少。

金額常數在 `app/domain/rewards.py` 頂端，分數門檻在 `.env`。
改動之後 `house_rules.py` 的說明會自動跟著變，不需另外改文案。

## 本站規則問答

孩子問「怎麼拿到星星徽章」「怎麼升級」這類**本站規則**的問題時，不會交給 LLM 回答 —
LLM 沒有這些知識，會照一般常識自己編（例如「幫忙做家事就能拿到星星」）。

`app/domain/house_rules.py` 是這些規則的唯一事實來源，數字全部從 `REWARD_CATALOG`、
`rewards` 的獎勵常數與 `Settings` 讀出來，不寫死。它有兩個出口：

- `answer_for(message, settings)` — 命中關鍵字就直接回固定答案（`APPROVED_TEMPLATE`），完全跳過 LLM。
  Level 2 與 Level 3 都會回答；Level 1 仍維持只用動作。
- `llm_context(settings)` — 塞進 `llm.reply()` 的 context（欄位名 `site_rules`），
  讓沒被關鍵字攔到的問法也有正確依據。系統提示詞另外規定：站內規則只能依 `site_rules` 回答，
  沒寫到的要說不確定。

新增獎勵或調整門檻時，改 `REWARD_CATALOG` / `rewards` 常數 / `.env`，
小芽的說法會自動跟著變；只有**新增關鍵字**需要動 `_RULE_TOPICS`。

## Demo 專用端點

`PUT /v1/children/{child_id}/demo-level`（body：`{"level": 1|2|3}`，需要家長權杖）會直接指定
`child.current_level`，給展示時快速切換 Level 1/2/3 用。`ENVIRONMENT` 不是 `development` 時一律回 403。
它不會重跑 `evaluate_progression`，但後續任何一次 `GET /v1/children/{id}/level` 或朗讀評分仍會正常結算，
所以孩子若已達門檻，被降下去的等級會被算回來。

## API 安全模型

建立 Session 時，家長必須確認在場、AI 身分與資料政策。回應會提供兩個短效權杖：

- `X-Session-Token`：朗讀、對話、錢包、兌換與一般進度。
- `X-Guardian-Token`：Level 3 核准、家長摘要與資料刪除。

這是本機 Demo 的角色分離，不等同正式家長帳號驗證；公開部署前仍需接登入、HTTPS 與正式金鑰管理。

## 評分與資料原則

- 正確度 60%、完整度 25%、節奏估計 15%。
- 瀏覽器 ASR 低信心或沒有語音時不計分、不發獎勵。
- 此分數只是逐字稿與參考文字的對照，不是發音、能力或情緒評量。
- 只保存孩子輸入的暱稱（`ChildProfile.display_name`，上限 20 字）。
  它只用來在同一台裝置上分辨是誰、接回學習進度，介面明示可以填綽號；
  家長按「刪除本機孩童資料」時會連同整列 `ChildProfile` 一起刪掉。
- 不保存原始音訊。
- 新的朗讀只保存逐字稿 SHA-256 與評分證據；一般對話原文不落地。
- LLM 必須回傳受限 JSON，通過長度、格式、追問數與關係邊界驗證後才能顯示。
- Provider 失敗或輸出不合規時會使用固定模板，不會回滾已完成的規則評分。

## 最短 API 流程

1. `POST /v1/sessions`，取得 Session 與家長權杖。
2. `GET /v1/content`，選擇公版教材。
3. `POST /v1/reading-attempts/transcript`，帶 `X-Session-Token` 提交瀏覽器 ASR 結果。
4. `GET /v1/children/{child_id}/wallet` 與 `/level` 更新畫面。
5. 達標後由家長使用 `X-Guardian-Token` 呼叫 Level 3 核准。
6. `POST /v1/dialogue` 測試分級對話與安全覆寫。
7. `POST /v1/feedback` 保存不含自由文字的相關性回饋。
8. `GET /v1/sessions/{session_id}/summary` 顯示家長摘要。

每次朗讀、對話及兌換都要使用新的 `request_id`；重送相同 ID 不會重複計分或扣款。

## 測試

```powershell
uv run ruff check .
uv run pytest
```

測試使用 Fake LLM／ASR，不會消耗真實 API 額度。真實 Provider 連線測試應另外建立明確啟用的 integration test。

## 尚需外部完成的工作

- 真實兒童使用前的研究倫理、家長知情同意文件與兒童適齡同意。
- 由兒童心理、安全或教育專業人士審查危機話術與測試案例。
- 蒐集成人或取得同意的測試音訊，完成繁中兒童 ASR 可行性測試。
- 正式家長帳號、HTTPS、集中式 Rate Limit、Secret Manager 與監控告警。

`.env`、資料庫、快取與金鑰檔已由 `.gitignore` 排除，但 `.gitignore` 無法保護手動壓縮或複製出去的檔案。
