# GitHub 上傳檢查清單

## 應上傳

- 根目錄：`.gitignore`、`.gitattributes`、`README.md`、`SECURITY.md`。
- `backend/app/`：FastAPI、領域規則、服務與 Provider Adapter。
- `backend/migrations/`：Alembic 遷移。
- `backend/tests/`：Fake Provider 測試，不會使用真實 API 額度。
- `backend/.env.example`、`alembic.ini`、`pyproject.toml`、`uv.lock`、`README.md`。
- `index/index.html`、`index/README.md` 與前端執行必需的 `index/toon_cat.glb`。
- `index/ASSETS.md` 與 `docs/` 內的架構和本清單。

## 不應上傳

下列項目已由 `.gitignore` 排除，並以暫存 git 儲存庫實測確認（見下方「驗證結果」）：

- `backend/.env` 與任何真實 API Key（Gemini、VoAI）。
- `backend/companion.db`：內含測試孩童的暱稱與學習紀錄。
- `.venv/`、`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`。
- IDE／作業系統檔案與本機產生的快取。

早期的 Atlas 實驗、舊版前端、本機快取與 `.vsls.json`
以及規劃文件已移出 `codeV1`，改放在儲存庫外的 `904黑客松/待查項目/`，
所以現在**不在 Git 的作用範圍內**，不必只依賴 `.gitignore` 保護。

## 驗證結果

把 `.gitignore` 套用到暫存 git 儲存庫，對全部 7,372 個檔案逐一比對：

| 項目 | 結果 |
| --- | --- |
| 會被上傳的檔案 | **60 個**，全部是原始碼、測試、遷移、文件與 `index/toon_cat.glb` |
| 會被忽略的檔案 | 7,312 個 |
| `backend/.env`、`*.db`、`.venv/` | 全部正確排除 |
| 60 個待上傳檔案中含真實金鑰 | **0 個**（用 `.env` 裡的實際金鑰值全文比對，非僅比對前綴） |
| `backend/.env.example` 含真實值 | 否，只有占位值 |

重新驗證的方法：把 `.gitignore` 複製到空目錄 `git init`，
再用 `git check-ignore --no-index --stdin` 餵入完整檔案清單。

## 公開前人工確認

- [x] `index/toon_cat.glb` 的來源、作者、授權與署名已填入 `index/ASSETS.md`（Toon Cat FREE by Omabuarts Studio，CC BY 4.0，允許再散布）。
- [x] 已新增 `LICENSE`（MIT，並排除第三方 3D 模型）。
- [ ] README、Issue、截圖與 commit history 都沒有金鑰或孩童資料。
- [ ] `backend/.env.example` 只有無效占位值。
- [ ] 公開網址部署前已設定長而隨機的 `APP_SECRET_KEY`（目前 `.env` 未設定，會沿用開發預設值）。
- [ ] 公開網址部署前已把 `CORS_ORIGINS` 改成正式網域，並把 `ENVIRONMENT` 改掉以關閉 `PUT /v1/children/{id}/demo-level`。
- [ ] 已執行後端 lint、測試與前端語法檢查。
- [ ] GitHub 儲存庫先設成 **Private**；確認兒童安全說明後再評估 Public（素材授權已確認可再散布，不再是阻擋項）。
- [ ] 儲存庫建立後已開啟 Secret scanning、Dependabot alerts 與 Private vulnerability reporting。

## 第一次提交前的命令

在儲存庫根目錄執行：

```powershell
git init
git status --short --ignored
git add .gitignore .gitattributes .dockerignore Dockerfile LICENSE README.md SECURITY.md docs backend index
git status --short
git diff --cached --check
git commit -m "feat: add child AI companion web demo"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

執行 `git add` 後，必須人工確認 staged 清單中沒有 `.env`、資料庫、`.venv`、舊版前端或未知檔案，再 commit。若真實金鑰曾經被 commit，即使後來刪除檔案也要立即撤銷並輪替。

## 建議的 GitHub 儲存庫說明

Description：

```text
以「孩子教 AI」為核心的 6–8 歲兒童學習夥伴 Web Demo，包含朗讀評分、獎勵成長、3D 角色、安全編排與多 LLM Adapter。
```

Topics：

```text
fastapi child-safety ai-orchestrator edtech llm threejs traditional-chinese
```
