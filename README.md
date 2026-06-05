# DB Agent Chat

這是「OpenAI Codex 實戰：打造可串接資料庫的 AI Agent 系統」課程專案。

目前內容：

- `frontend/`：React + Vite 前端
- `backend/`：Python Flask API
- `docker-compose.yml`：MySQL 8 資料庫
- `GET /api/health`：後端健康檢查
- `GET /api/db/health`：MySQL 連線健康檢查
- `GET /api/db/tables`：資料表與筆數
- `GET /api/db/summary`：資料庫摘要
- `GET /api/employees`：員工資料
- `GET /api/expenses`：費用資料
- `GET /api/invoices`：發票資料
- `GET /api/llm/health`：OpenAI API Key 與 LLM 連線狀態檢查
- `POST /api/chat/rooms/:id/messages`：接收前端訊息與模型設定，呼叫 OpenAI API 產生回覆並寫入資料庫

## 1. 建立環境變數

請先複製 `.env.example` 成 `.env`：

```powershell
Copy-Item .env.example .env
```

`.env.example` 內容：

```env
DATABASE_URL=mysql+pymysql://codex_user:codex_pass@127.0.0.1:3306/codex_demo
OPENAI_API_KEY=請填入你的 key
```

`.env` 只放在本機使用，請不要提交到 GitHub。`.env.example` 只能保留 placeholder，不要放入真實 API Key。

## 2. 啟動 MySQL

請在專案根目錄執行：

```powershell
docker compose up -d
```

查看 container 狀態：

```powershell
docker compose ps
```

查看 MySQL log：

```powershell
docker compose logs db
```

如果你的電腦已經有其他 MySQL 使用 `3306`，`docker compose up -d` 可能會失敗。請先停止佔用 `3306` 的服務，或調整 `docker-compose.yml` 與 `.env` 的 port。

## 3. 安裝後端套件

建議使用課程用的 conda 環境 `Codex_Demo`。

請在專案根目錄執行：

```powershell
conda activate Codex_Demo
pip install -r backend/requirements.txt
```

## 4. 初始化資料庫與匯入範例資料

請在專案根目錄執行：

```powershell
conda activate Codex_Demo
python backend/scripts/init_db.py
python backend/scripts/seed_db.py
```

如果你想重建所有 demo tables，可以執行：

```powershell
python backend/scripts/init_db.py --drop
python backend/scripts/seed_db.py
```

Seed data 會建立：

- 4 個部門
- 12 位員工
- 8 個廠商
- 30 筆費用資料
- 5 筆發票資料
- 1 個 demo chat room
- 2 筆 demo chat messages
- 1 筆 audit log

## 5. 啟動 Flask 後端

請開啟第一個 terminal，執行：

```powershell
conda activate Codex_Demo
cd backend
flask --app app.main run --host 127.0.0.1 --port 5000 --debug
```

後端健康檢查：

```text
http://127.0.0.1:5000/api/health
```

DB 健康檢查：

```text
http://127.0.0.1:5000/api/db/health
```

資料庫摘要：

```text
http://127.0.0.1:5000/api/db/summary
```

LLM 健康檢查：

```text
http://127.0.0.1:5000/api/llm/health
```

這個 API 只會回傳遮罩後的 key，例如 `sk-...abcd`，不會回傳完整 `OPENAI_API_KEY`。

## 6. 重啟 Flask 後端

如果你是在 terminal 前景執行 Flask：

1. 按 `Ctrl+C` 停止 Flask
2. 重新執行：

```powershell
conda activate Codex_Demo
cd backend
flask --app app.main run --host 127.0.0.1 --port 5000 --debug
```

如果你修改了 `.env`，也請重啟 Flask，讓新的環境變數生效。

## 7. 安裝前端套件

請開啟第二個 terminal，執行：

```powershell
cd frontend
npm install
```

## 8. 啟動 React 前端

請在第二個 terminal 執行：

```powershell
cd frontend
npm run dev
```

前端網址通常是：

```text
http://localhost:5173
```

## 9. Memory 輪數設定

右側 Control Panel 的 `Memory 輪數` 範圍是 1 到 10。

一輪代表一組歷史對話：

```text
user 一則訊息 + assistant 一則訊息
```

每次送出新訊息時，後端會依照目前聊天室 `room_id` 從 `chat_messages` 讀取最近 N 輪歷史訊息，並組裝給 LLM：

```text
system prompt
最近 N 輪 user / assistant 歷史訊息
最新 user message
```

後端不會把整個聊天室所有訊息都送給 LLM，也不會把 `metadata_json` 當成聊天訊息傳入。這樣可以控制 token 使用量，也能讓課堂 Demo 清楚觀察「記憶輪數」對回答的影響。

## 10. Context Router

右側 Control Panel 的 `Enable Context Router` 開啟時，每次送出訊息後，後端會先請 LLM 判斷這次任務要走哪條路：

```text
general_chat：一般聊天
db_query：查詢員工、部門、費用、發票、廠商等資料
db_write：新增或修改資料庫資料
rag：查公司 SOP 或 MIS 常見問題
image_skill：圖片辨識，例如發票、收據、文件截圖
```

Router 會回傳：

```text
route
confidence
reason
required_capability
suggested_followup_question
```

如果 LLM Router 回傳不是合法 JSON，後端會使用 fallback 規則，不會讓系統壞掉。

右側 `Auto Route` 控制是否自動接受 Router 判斷：

- 開啟：系統自動接受 Router 判斷並執行。
- 關閉：前端會顯示五種 route 按鈕，讓使用者改選後按「確認執行」。

目前 `db_query` 已串接安全 SQL Agent。`db_write`、`rag`、`image_skill` 的完整能力會在後續階段實作；目前會先回覆「此能力將在下一階段啟用」。

如果對應功能 toggle 沒開，例如 `Enable DB Query` 關閉但 Router 判斷為 `db_query`，assistant 會回覆：

```text
DB Query 尚未啟用，請先在右側開啟。
```

前端會透過 Vite proxy 呼叫 Flask API，所以建議啟動順序是：

1. `docker compose up -d`
2. `python backend/scripts/init_db.py`
3. `python backend/scripts/seed_db.py`
4. 啟動 Flask 後端
5. 啟動 React 前端

## 11. 安全 SQL Agent

右側 Control Panel 同時開啟 `Enable Context Router` 與 `Enable DB Query` 時，如果 Router 判斷本次任務是 `db_query`，後端會執行 SQL Agent 流程：

```text
schema introspection
自然語言轉 SQL
SQL 安全驗證
執行 MySQL SELECT
LLM 整理繁體中文回答
```

安全限制：

- 只允許 `SELECT`。
- 禁止 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`TRUNCATE`、`CREATE` 等操作。
- 不允許多語句 SQL 或分號。
- 查詢必須有 `LIMIT`，後端最多允許 50 筆。
- 執行 SQL 前會用程式驗證，不只依賴 prompt。
- 發生錯誤時只回傳友善訊息，不會把完整 stack trace 顯示到前端。

前端 assistant 泡泡會顯示：

- 本次使用 route：DB Query
- 可收合的產生 SQL
- 可收合的查詢結果表格
- LLM 整理後的回答

可測試問題：

```text
資訊部有哪些員工？列出姓名、職稱、email。
各部門費用總額是多少？依金額高到低排序。
找出還沒核准且金額超過 3000 的費用。
哪個廠商的發票總金額最高？
```

## 12. 在 Docker 裡查看目前資料

如果你是用本專案的 `docker-compose.yml` 啟動 MySQL，可以進入 MySQL CLI：

```powershell
docker compose exec db mysql -ucodex_user -pcodex_pass codex_demo
```

進入 MySQL 後可以執行：

```sql
SHOW TABLES;
SELECT COUNT(*) FROM employees;
SELECT COUNT(*) FROM expense_reports;
SELECT COUNT(*) FROM invoices;
SELECT * FROM employees LIMIT 5;
SELECT category, SUM(amount) FROM expense_reports GROUP BY category;
```

也可以直接用一行指令查看資料表：

```powershell
docker compose exec db mysql -ucodex_user -pcodex_pass codex_demo -e "SHOW TABLES;"
```

如果你目前使用的是舊的 `codex_db` container，可以改用：

```powershell
docker exec -it codex_db mysql -ucodex_user -pcodex_pass codex_demo
```
