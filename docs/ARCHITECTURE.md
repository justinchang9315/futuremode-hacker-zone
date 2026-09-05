# 小芽 Phase I 系統架構與資料流程

> 狀態：2026-09-05 Web Demo 實作基準。現階段聚焦瀏覽器版虛擬角色；實體機器人與邊緣／雲端部署切分屬後期範圍。

## 設計目標

讓 6～8 歲孩子以「小老師」身分朗讀公版唐詩教小芽，取得透明、可追溯而不宣稱發音診斷能力的文字對照結果。角色能力依完成、進步與精通里程碑解鎖，不使用聊天次數或模擬好感度建立依附。

## 系統架構

```mermaid
flowchart TB
    Guardian[在場家長] --> Gate[家長確認與家長操作]
    Child[6～8 歲孩子] --> Web

    subgraph Web[靜態 Web Client]
        World[學習島與 3D 小芽]
        Lesson[唐詩、注音與朗讀引導]
        BrowserASR[Browser ASR]
        BrowserTTS[Browser TTS]
        ResultUI[分數、獎勵、Level 與道具]
        Chat[心情與課業對話]
    end

    Gate -->|Guardian Token| API
    Web -->|Session Token| API

    subgraph API[FastAPI AI Orchestrator]
        Auth[Session、短效權杖與基本限流]
        Quality[ASR Quality Gate]
        Safety[Input Safety Engine]
        Scorer[規則式文字評分]
        Reward[冪等獎勵帳本與 Inventory]
        Progression[Level 與家長核准]
        Composer[Template-first 回應編排]
        OutputGuard[JSON Schema 與 Output Guard]
        Feedback[結構化相關性回饋]
        Privacy[摘要與資料刪除]
    end

    API --> DB[(SQLite 開發環境／PostgreSQL 可替換)]
    Composer --> Gateway

    subgraph Gateway[可替換 LLM Gateway]
        Fake[Fake]
        Gemini[Gemini]
        OpenAI[OpenAI]
        GMI[GMI Cloud]
        EastRouter[EastRouter]
    end

    BrowserASR --> Quality --> Safety
    Safety --> Scorer --> Reward --> Progression --> Composer
    Chat --> Safety --> Composer
    Composer --> Gateway --> OutputGuard --> World
    OutputGuard --> BrowserTTS
```

## 朗讀與成長流程

```mermaid
flowchart TD
    Start[家長完成三項確認] --> Session[建立限時 Session]
    Session --> Pick[孩子選擇公版唐詩]
    Pick --> Teach[孩子按下麥克風朗讀]
    Teach --> ASR[瀏覽器產生逐字稿與信心值]
    ASR --> Usable{逐字稿可信？}
    Usable -->|否| NoScore[不計分、不發獎勵並邀請再試]
    Usable -->|是| Score[正確度 60%＋完整度 25%＋節奏估計 15%]
    Score --> Ledger[寫入冪等金幣／鑽石帳本]
    Ledger --> Level{後端成長里程碑}
    Level -->|Level 1| Body[只用動作]
    Level -->|Level 2| Template[動作＋核准固定短句]
    Level -->|Level 3 eligible| Parent[等待家長明確核准]
    Parent --> LLM[受限 LLM 對話]
    LLM --> Validate{格式、長度、安全與關係邊界合法？}
    Validate -->|否| Fallback[固定安全模板]
    Validate -->|是| Output[顯示回應與瀏覽器 TTS]
    Body --> Continue{繼續或結束}
    Template --> Continue
    Output --> Continue
    NoScore --> Continue
    Continue -->|繼續| Pick
    Continue -->|時間到或家長結束| Summary[產生家長摘要]
```

## AI Orchestrator 的責任邊界

| 模組 | 主要責任 | 不負責的事情 |
| --- | --- | --- |
| Auth / Session | 家長確認、兩種短效權杖、時限與基本限流 | 正式帳號與真實家長身分驗證 |
| Quality / Scoring | 判斷 ASR 結果能否評分，產生可追溯文字分數 | 發音診斷、智力或學習能力判定 |
| Safety | 危機、個資、操控及不適齡內容的規則式路由 | 取代真人危機服務或專業評估 |
| Rewards / Progression | 獎勵帳本、兌換、里程碑與 Level 3 核准 | 用依附、聊天量或付費刺激升級 |
| Composer / LLM Gateway | 先用規則與模板，必要時才呼叫指定 Provider | 讓 LLM 自行決定獎勵、權限或安全政策 |
| Output Guard | 驗證模型 JSON、長度、問句數及關係邊界 | 保證模型回答永遠正確 |
| Privacy | 最小化事件、家長摘要與刪除 API | 正式資料治理、備份刪除與跨區法遵 |

## 儲存與隱私

- 瀏覽器處理語音辨識及語音合成；後端不保存原始音訊。
- 新朗讀紀錄保存逐字稿 SHA-256 與評分證據，不保存逐字稿原文。
- 一般對話原文不落地；安全事件只保存必要分類、政策版本與固定話術識別碼。
- SQLite 用於本機 Demo；SQLAlchemy 與 Alembic 保留切換 PostgreSQL 的路徑。
- 前端 `sessionStorage` 保存短效權杖，`localStorage` 保存本機 child ID 與裝飾狀態。

## 尚未完成、不可對外宣稱的能力

- 兒童研究倫理審查、家長知情同意文件與兒童適齡同意。
- 由教育、兒童心理或安全專業人士審查危機分類、固定話術和轉介流程。
- 真實兒童繁體中文 ASR Benchmark 與無障礙測試。
- 正式帳號、HTTPS、Secret Manager、集中式 Rate Limit、監控與告警。
- 實體機器人的感測器、運動控制、安全停機，以及本地端／雲端任務切分。
