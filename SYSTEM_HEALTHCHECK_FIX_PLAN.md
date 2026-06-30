# CafeMatch 系統健檢修復任務單

健檢日期：2026-06-22

這份文件是給 AI 工程代理直接執行的修復清單。請在修改前先讀現有程式碼，保留目前產品行為與 UI 方向，不要還原使用者既有未提交變更。每完成一組修復都要跑對應驗證指令。

## 目前驗證結果

- `python test_import.py`：通過
- `python test_guide.py`：通過
- `python -m compileall app.py routes services models config utils.py`：通過
- `pip check`：通過
- `npm.cmd run build`：失敗，`frontend/src/ChatPage.css` 有 CSS 語法錯誤
- `npm.cmd run lint`：失敗，76 errors、15 warnings

## 優先修復順序

1. 先修到前端可以 build。
2. 修聊天串流解析，避免 AI 回覆被截斷或消失。
3. 修後端安全設定與錯誤外洩。
4. 補資料完整性與刪除流程。
5. 收斂 lint、測試與維運檔案。

## P0：前端 build 失敗

### 問題

`npm.cmd run build` 目前失敗：

```text
[lightningcss minify] Invalid empty selector
```

真正位置在 `frontend/src/ChatPage.css:543-549`。`@media (max-width: 1366px)` 區塊結尾多了 `}`，造成 CSS parser 在 minify 階段報錯。

### 修復要求

- 修正 `frontend/src/ChatPage.css` 的括號結構。
- 確認 `@media (max-width: 1366px)` 只關閉一次。
- 不要順手重排整份 CSS，避免製造大量 diff。

### 驗收

```powershell
cd frontend
npm.cmd run build
```

## P0：聊天串流 NDJSON 解析會掉資料

### 問題

`frontend/src/pages/ChatPage.jsx:217-223` 直接把每個 `reader.read()` chunk 用 `chunk.split('\n')` 解析 JSON。串流 chunk 不保證剛好落在換行邊界，當 JSON 被拆成兩段時會進入 `catch` 並被忽略，導致 AI 回覆缺字、狀態遺失或最後不存檔。

### 修復要求

- 在 `executeChatStream` 中加入持久化 buffer，例如 `let ndjsonBuffer = ''`。
- 每次 read 後 append 到 buffer，只解析完整行，最後一段不完整內容留到下一次。
- stream 結束後處理 buffer 中最後一行。
- JSON parse 失敗時不要靜默吞掉，至少用 `logger.warn` 記錄不含敏感 prompt 的摘要。
- 保留現有 `status`、`debug_info`、`response/content`、`error`、`done` 行為。

### 驗收

- 手動測試 `/chat` 長回覆不缺字。
- 新增或補上最小測試：模擬 NDJSON 被切成半行時仍能完整組回。
- `npm.cmd run build` 通過。

## P1：後端仍是開發模式安全設定

### 問題

`app.py` 有多個生產風險：

- `app.py:10` 永遠設定 `OAUTHLIB_INSECURE_TRANSPORT=1`。
- `app.py:22` `SECRET_KEY` 預設為 `dev_key`。
- `app.py:31-32` `CORS(app, supports_credentials=True)` 未限制來源。
- `app.py:52-104` import app 時直接 `db.create_all()`、`ALTER TABLE`、設定管理員。
- `app.py:99` 管理員 email 寫死在程式碼。

### 修復要求

- 只在 `FLASK_ENV=development` 或明確 `ALLOW_INSECURE_OAUTH=1` 時設定 `OAUTHLIB_INSECURE_TRANSPORT`。
- 生產環境若沒有 `SECRET_KEY` 要啟動失敗；本機開發可保留安全警告或 dev fallback。
- CORS 改成白名單，從 `FRONTEND_URL` 或 `CORS_ORIGINS` 讀取，仍需支援 credentials。
- 移除 import 時自動遷移資料庫的副作用。改用 Alembic/Flask-Migrate，或至少改成明確 CLI 指令。
- 管理員設定改讀 `ADMIN_EMAILS` 環境變數，支援逗號分隔，多個管理員。

### 驗收

```powershell
python test_import.py
python -m compileall app.py routes services models config utils.py
```

並確認 import `app` 不會在沒有明確指令時改資料庫 schema。

## P1：錯誤訊息與 debug prompt 會外洩

### 問題

- `routes/chat.py:204-209` 會把例外 `str(e)` 回傳給使用者，並寫入未忽略的 `api_error.log`。
- `services/ai_service.py:251-259` 每次串流都先送出完整 prompt、RAG context、模型名稱。即使前端 UI 只有 admin 顯示 debug，後端仍把敏感內容送給所有呼叫者。

### 修復要求

- 用 `current_app.logger.exception(...)` 取代手動寫 `api_error.log`。
- 對外只回傳泛用錯誤訊息，例如「系統暫時無法處理，請稍後再試」。
- `.gitignore` 增加 `*.log` 或至少 `api_error.log`。
- `/api/chat` 增加 `debug` request flag，但後端必須檢查目前 session 使用者是否為 admin。
- 非 admin 或未開啟 debug 時，不要串流 prompt、RAG context、內部模型細節。
- admin debug 可保留，但避免包含使用者 OAuth token、環境變數或 secrets。

### 驗收

- 一般使用者呼叫 `/api/chat` 不會收到 `debug_info`。
- admin 且開啟 debug 才會收到 debug payload。
- 模擬後端 exception 時，前端只看到泛用錯誤，server log 有 traceback。

## P1：資料完整性與刪除流程不完整

### 問題

多個資料表關係缺少 foreign key、unique constraint 或 cascade，刪除時容易失敗或留下孤兒資料。

涉及位置：

- `models/user.py:16-22` `UserShopState.user_id`、`cafe_id` 沒有 foreign key，也沒有 `(user_id, cafe_id)` unique constraint。
- `models/community.py:14-19` `PostLike` 沒有 `(user_id, post_id)` unique constraint，重複請求可能建立重複讚。
- `models/community.py:37-42` `CommunityLike` 沒有 `(user_id, note_id)` unique constraint。
- `routes/auth.py:142-143` 刪使用者只刪 `UserShopState`，沒有處理 chat sessions、feedback、quiz results、community posts/comments/likes/notes。
- `routes/community.py:580-581` 刪貼文時沒有先處理 likes、comments、reposts。

### 修復要求

- 為 `UserShopState` 補 foreign key 與 unique constraint。
- 為 `PostLike`、`CommunityLike` 補 unique constraint。
- 明確設計刪除策略：使用 SQLAlchemy relationships cascade，或在 route/service 中集中刪除相關資料。
- 刪貼文時要處理該貼文的 likes/comments，以及被轉發貼文的 `original_post_id` 策略。
- 管理員刪使用者與使用者自行刪帳號應共用同一個 service function，避免兩套邏輯。

### 驗收

- 重複按讚不會建立重複 row。
- 刪除貼文後查不到該貼文相關 likes/comments。
- 刪除使用者後不會留下該使用者的互動資料。
- 若使用 migration，需提供 migration 檔與資料去重策略。

## P1：聊天 session 儲存需要強化

### 問題

`routes/chat.py:57-84` 允許 client 提供 `session_id`。若傳入不存在或屬於其他人的 id，後端會嘗試用該 id 建立新 session，可能撞 primary key 或造成錯誤訊息外洩。

### 修復要求

- 新建 session 時一律由後端產生 UUID。
- 更新 session 時只接受屬於目前 user 的 id，不存在就回 404，不要用 client id 新增。
- 限制 `title`、`messages` 大小，避免單次請求寫入過大的 JSON。
- 驗證 `messages` 每筆都只有允許欄位與合法 role。

### 驗收

- client 傳入別人的 session id 不會覆蓋或建立同 id session。
- 過大 payload 會回 413 或 400。

## P2：前端 lint 需要收斂

### 問題

`npm.cmd run lint` 目前有 76 errors、15 warnings。主要類型：

- 多數 React 19 檔案仍 import unused `React`。
- 多個 hook 先呼叫後宣告函式，例如 `frontend/src/components/CafeList.jsx:11-15`、`frontend/src/hooks/useCommunityPosts.js:14-18`。
- `frontend/src/components/FloatingBackgroundIcon.jsx:35-36` render/memo 過程使用 `Math.random()`，React compiler 視為 impure。
- 多個 effect 直接同步 setState，被 React hooks 規則擋下。

### 修復要求

- 移除不需要的 `import React`，保留有用到 `React.Fragment` 的檔案或改成 fragment shorthand。
- 將 effect 內使用的 async function 用 `useCallback` 包好，並放在 effect 前宣告。
- 對於只需初始化一次的隨機偏移，用固定 seed 或 module-level 常數，不要在 render path 呼叫 `Math.random()`。
- 對於 React compiler 的新規則，若確定是誤報，調整 eslint config 前要先說明理由；優先修程式。

### 驗收

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

## P2：API 與前端資料流一致性

### 問題

- `routes/explore.py` 每次 `/api/cafes` 都用 `random.uniform` 產生 rating、`random.choice` 產生 color，使用者刷新後結果會變。
- `frontend/src/utils/apiClient.js` 已有統一工具，但多數 hook/page 仍直接 `fetch`，錯誤處理和 toast 行為不一致。
- 社群列表 API 在迴圈中逐筆查作者、店家、讚數、留言數，有 N+1 query 風險。

### 修復要求

- 移除假 rating，或改成資料庫欄位；若暫無資料，回傳 `null` 或穩定預設值。
- 顏色若只是 UI 裝飾，改成由 cafe id hash 穩定產生。
- 新增 API helper 後逐步替換直接 `fetch`，至少先處理聊天以外的社群 hooks。
- 社群列表可用 `selectinload`、聚合查詢或批次查詢減少 N+1。

### 驗收

- 同一批 cafe 連續刷新資料不會隨機跳動。
- API 錯誤顯示一致，console 不再只有靜默失敗。

## P2：測試檔與維運檔案整理

### 問題

目前根目錄測試檔偏臨時腳本：

- `test_chat.py` 依賴本機 Flask server 已啟動。
- `test_extract.py` 讀取 `C:\Users\user\.gemini\...` 的外部絕對路徑，不可重現。
- 沒有正式 pytest 或前端測試設定。
- `api_error.log` 是未追蹤檔案，且 `.gitignore` 目前沒有忽略一般 `*.log`。

### 修復要求

- 將臨時腳本改成 `tests/` 下的 pytest 測試，或移到 `scripts/` 並清楚標示手動用途。
- 移除依賴外部絕對路徑的測試。
- 補基本後端測試：auth 未登入、chat session 權限、conversation guide、資料刪除。
- 前端至少補串流 parser 的單元測試，若尚未引入 test runner，先把 parser 抽成純函式。
- `.gitignore` 補 `*.log`，確認不提交本機 log。

### 驗收

```powershell
python -m compileall app.py routes services models config utils.py
python test_import.py
python test_guide.py
cd frontend
npm.cmd run lint
npm.cmd run build
```

若新增 pytest 或前端 test runner，也要把對應指令寫進 README。

## 最終完成標準

- 前端 `npm.cmd run lint` 與 `npm.cmd run build` 都通過。
- 後端 import、compile、現有 smoke test 都通過。
- `/api/chat` 不再向非 admin 串流 debug prompt。
- 生產環境不再使用 `dev_key`、不再允許 insecure OAuth、CORS 有明確白名單。
- 資料刪除流程不會留下主要孤兒資料。
- 所有新增行為都有簡短文件或測試覆蓋。
