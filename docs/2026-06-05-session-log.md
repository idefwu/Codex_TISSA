# 2026-06-05 Codex_TISSA 開發紀錄

本文件整理今天與 Codex 的主要對話、已完成工作、執行指令與目前系統狀態。紀錄中不包含 `.env` 內的任何私密內容或 API Key。

## 專案目標

課程主題為「OpenAI Codex 實戰：打造可串接資料庫的 AI Agent 系統」。

最終系統方向：

- React + Vite 聊天室 UI。
- Python Flask 後端 API。
- Docker MySQL 8 資料庫。
- 公司營運 Demo 資料：部門、員工、廠商、費用、發票。
- OpenAI API 聊天能力。
- Context Router：一般聊天、查資料庫、RAG、圖片辨識。
- SQL Agent 安全查詢資料庫。
- 圖片辨識結果可經使用者確認後寫入資料庫。

## 今日工作摘要

今天完成了從最小前後端、聊天 UI、MySQL schema、seed data，到聊天訊息透過後端 API 寫入資料庫的階段性實作。

目前已完成：

- `frontend/`：React + Vite 前端。
- `backend/`：Flask API。
- Docker MySQL 8：`codex_db` 容器運作中。
- SQLAlchemy + PyMySQL + python-dotenv。
- 公司營運資料表與 seed data。
- 資料庫健康檢查與 DB 概況 API。
- 三欄式聊天 UI。
- Light / Dark mode 切換。
- 模型選擇：`gpt-4o`、`gpt-5.5`、`gpt-5.4`。
- 聊天室 CRUD API。
- 聊天訊息寫入 DB，重新整理後可保留。

## 對話與實作歷程

### 第 1 階段：環境與專案規劃

使用者要求先檢查目前電腦環境，不先大改檔案。

檢查重點：

- 目前資料夾內容。
- Node.js / npm 是否可用。
- Python 版本是否可用，優先 Python 3.10+。
- 已建立虛擬環境 `Codex_Demo`，Python 版本為 `3.11.15`。
- Docker 是否可用。
- 是否已有 `docker-compose.yml` 或其他專案檔案。
- 根據課程目標建議專案結構。

建議專案結構：

```text
frontend/
backend/
backend/app/
backend/scripts/
backend/data/
docker-compose.yml
README.md
```

### 第 2 階段：建立最小可啟動前後端

使用者要求直接建立 React + Vite 前端與 Flask 後端。

完成內容：

- 建立 `frontend/` React + Vite 專案。
- 建立 `backend/` Flask API。
- 新增 `GET /api/health`。
- 前端首頁顯示：
  - `DB Agent Chat`
  - 後端連線狀態
  - 重新檢查後端狀態按鈕
- 新增 `backend/requirements.txt`。
- 新增 `.gitignore`，排除：
  - `.env`
  - `node_modules/`
  - `__pycache__/`
  - `.venv/`
  - `backend/uploads/`
- README 寫入前後端安裝與啟動方式。

驗證：

- 前端可啟動於 `http://localhost:5173`。
- 後端可啟動於 `http://127.0.0.1:5000`。
- `/api/health` 回傳正常。

### README 中文化

使用者要求將 README 改成中文。

完成內容：

- README 改為中文說明。
- 保留前端、後端、Flask、React 啟動指令。
- 說明如果需要開兩個 terminal，前後端需分別啟動。

### GitHub 推送

使用者要求推送檔案至 `idefwu/Codex_TISSA.git`。

已完成推送過的 commit：

```text
f82ce3c Initial commit
ab59dac Add minimal frontend and backend starter
9b805ba Build chat UI prototype
839d05e Add company operations demo database
```

目前本機 `main` 分支追蹤 `origin/main`。

### 第 3 階段：聊天 UI，不串 OpenAI API

使用者要求把前端改造成三欄式聊天工具。

完成內容：

- 左側 Sidebar：
  - 新增聊天室。
  - 聊天室列表。
  - 重新命名、刪除聊天室。
  - 可收合。
  - 左下設定區。
- 中間 Chat Area：
  - 使用者訊息靠右。
  - 系統訊息靠左。
  - 送出後顯示思考泡泡，再顯示 mock response。
  - Enter 送出，Shift+Enter 換行。
  - 圖片上傳按鈕先 disabled，顯示「圖片功能尚未啟用」。
- 右側 Control Panel：
  - 可收合。
  - 模型選擇。
  - Temperature。
  - System Prompt。
  - Memory 輪數。
  - Context Router / DB Query / RAG / Image Skill / Audit Log 開關。
- RWD：
  - 手機版改成上方聊天列表按鈕與設定抽屜。

### 模型選項調整

使用者要求模型選擇改為：

- `gpt-4o`
- `gpt-5.5`
- `gpt-5.4`

已完成於前端 Control Panel。

### DB 連線階段

使用者要求後端串接 MySQL。

完成內容：

- 後端使用 SQLAlchemy 連線 MySQL。
- 使用 PyMySQL driver。
- 使用 python-dotenv 讀取 `.env`。
- 建立 `.env.example`，包含：

```env
DATABASE_URL=mysql+pymysql://codex_user:codex_pass@127.0.0.1:3306/codex_demo
OPENAI_API_KEY=請填入你的 key
```

- 新增 `GET /api/db/health`：
  - 成功時回傳 DB 版本與連線狀態。
  - 失敗時回傳清楚錯誤訊息。
- 前端顯示 DB 連線狀態。
- README 補上：
  - `docker compose up -d`
  - `docker compose ps`
  - `docker compose logs db`
  - 如何重啟後端。

### Sidebar Light / Dark mode 修正

使用者指出左下設定應該有 Light / Dark 模式切換按鈕。

完成內容：

- Sidebar 左下角設定區加入模式切換。
- 使用 icon button / toggle button 形式。
- 可在 Light / Dark mode 間切換。

### 第 5 階段：公司營運資料表與 seed data

使用者要求建立適合課堂 Demo 的 MySQL schema 與 seed data。

完成資料表：

- `departments`
- `employees`
- `vendors`
- `expense_reports`
- `invoices`
- `chat_rooms`
- `chat_messages`
- `audit_logs`

完成後端內容：

- SQLAlchemy models。
- `backend/scripts/init_db.py`。
- `backend/scripts/seed_db.py`。
- API：
  - `GET /api/db/tables`
  - `GET /api/db/summary`
  - `GET /api/employees`
  - `GET /api/expenses`
  - `GET /api/invoices`

Seed data 數量：

- 4 個部門。
- 12 位員工。
- 8 個廠商。
- 30 筆費用資料。
- 5 筆發票資料。

前端完成：

- 右側 Control Panel 顯示 DB 概況：
  - 員工數
  - 廠商數
  - 費用筆數
  - 發票數
  - 費用總額
  - 發票總額

目前 DB 概況：

```text
員工：12
廠商：8
費用筆數：30
發票：5
費用總額：418,510 TWD
發票總額：166,560 TWD
```

Docker 中查看資料的方式已補充於 README，例如：

```powershell
docker exec -it codex_db mysql -ucodex_user -pcodex_pass codex_demo
SHOW TABLES;
SELECT * FROM employees LIMIT 5;
```

### 第 6 階段：聊天訊息透過後端 API 並存入資料庫

使用者要求將前端 Echo Bot 改為透過後端 API，且訊息寫入 DB。

後端新增 API：

- `POST /api/chat/rooms`：建立聊天室。
- `GET /api/chat/rooms`：取得聊天室列表。
- `PATCH /api/chat/rooms/:id`：修改聊天室名稱。
- `DELETE /api/chat/rooms/:id`：刪除聊天室與訊息。
- `GET /api/chat/rooms/:id/messages`：取得聊天室訊息。
- `POST /api/chat/rooms/:id/messages`：送出使用者訊息。

後端目前不串 OpenAI API，先回覆：

```text
後端已收到你的訊息：{message}。下一階段會由 LLM 回覆。
```

資料庫更新：

- `chat_rooms` 保存：
  - `title`
  - `created_at`
  - `updated_at`
- `chat_messages` 保存：
  - `room_id`
  - `role`
  - `content`
  - `metadata_json`
  - `created_at`
- 使用者訊息與 assistant mock 回覆都會寫入 DB。

前端更新：

- 聊天室列表從 DB API 取得。
- 重整頁面後聊天室與訊息仍存在。
- 新增、改名、刪除聊天室都打 API。
- 加入基本 loading / error UI。
- 送出訊息後仍保留 2 秒思考泡泡。

實測結果：

- 新增聊天室成功。
- 送出訊息成功。
- user message 與 assistant reply 都寫入 DB。
- 重新整理頁面後訊息仍存在。

測試時留下的聊天室：

```text
新聊天室 3
Stage 6 API Test
Finance demo room
```

目前 `/api/chat/rooms` 可正常回傳 3 個聊天室。

### 紅字 HTTP 404 問題

使用者詢問前端為何出現紅字 `HTTP 404`。

判斷原因：

- 前端打聊天室 API 時收到 404。
- 常見原因之一是 Flask 後端尚未重啟，仍是舊版本，沒有載入第 6 階段 routes。
- 另一種情境是前端仍選到已被刪除的聊天室，所以讀 `/api/chat/rooms/:id/messages` 時找不到。

修正內容：

- 前端 `apiRequest` 會保留 HTTP status。
- 如果聊天室 API 不存在，提示：

```text
找不到聊天室 API，請確認 Flask 後端已重啟。
```

- 如果只是某個聊天室已不存在，前端會清掉選取狀態，不再卡住紅字。

驗證：

- `npm run lint` 通過。
- `npm run build` 通過。

## 今日執行過的重要指令

後端檢查：

```powershell
C:\Users\ASUS\anaconda3\envs\Codex_Demo\python.exe -m compileall backend\app backend\scripts
```

資料庫初始化：

```powershell
C:\Users\ASUS\anaconda3\envs\Codex_Demo\python.exe backend\scripts\init_db.py
```

前端檢查：

```powershell
npm run lint
npm run build
```

後端健康檢查：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/health' -Method Get
```

聊天室 API 檢查：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/chat/rooms' -Method Get
```

前端狀態檢查：

```powershell
Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 3
```

Docker 狀態檢查：

```powershell
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
```

## 目前服務狀態

截至本紀錄建立時：

```text
Backend health：ok
Frontend：http://127.0.0.1:5173 回應 200
Docker MySQL：codex_db / mysql:8.0 / Up 2 hours
MySQL Port：3306 -> 3306
```

目前 `GET /api/chat/rooms` 回傳摘要：

```text
id=3，新聊天室 3，2 則訊息
id=2，Stage 6 API Test，2 則訊息
id=1，Finance demo room，2 則訊息
```

## 目前 Git 狀態

目前分支：

```text
main...origin/main
```

目前尚未提交的變更：

```text
backend/app/__init__.py
backend/app/models.py
backend/scripts/init_db.py
backend/scripts/seed_db.py
frontend/src/App.css
frontend/src/App.jsx
frontend/src/components/ChatArea.jsx
frontend/src/components/Sidebar.jsx
docs/2026-06-05-session-log.md
```

注意：`.env` 已在 `.gitignore` 中，未納入提交內容。

## 重要檔案索引

- `frontend/src/App.jsx`：前端主狀態與 API 串接。
- `frontend/src/components/Sidebar.jsx`：聊天室列表、新增、改名、刪除、模式切換。
- `frontend/src/components/ChatArea.jsx`：聊天訊息區、輸入框、loading/error 顯示。
- `frontend/src/components/ControlPanel.jsx`：模型設定與 DB 概況。
- `backend/app/__init__.py`：Flask routes。
- `backend/app/models.py`：SQLAlchemy models。
- `backend/app/db.py`：資料庫連線與 health check。
- `backend/scripts/init_db.py`：建立或更新資料表。
- `backend/scripts/seed_db.py`：匯入 demo seed data。
- `docker-compose.yml`：MySQL 8 容器設定。
- `README.md`：啟動與操作說明。

## 下一步建議

建議下一階段可以進入：

1. 將 `POST /api/chat/rooms/:id/messages` 串接 OpenAI API。
2. 將前端選擇的模型傳給後端並實際使用。
3. 加入 Context Router，判斷一般聊天、DB 查詢、RAG、圖片辨識。
4. 建立 SQL Agent 安全查詢層。
5. 加入 audit log，記錄使用者問題、路由結果、SQL 查詢與回覆摘要。
6. 加入圖片上傳與辨識流程，使用者確認後再寫入 invoices 或 expenses。
