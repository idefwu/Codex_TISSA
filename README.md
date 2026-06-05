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
- `POST /api/chat`：接收前端訊息與模型設定，目前先回傳 mock 回覆

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

目前 `/api/chat` 尚未真正呼叫 OpenAI API，但前端已經會把右側選擇的模型送到後端。

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

前端會透過 Vite proxy 呼叫 Flask API，所以建議啟動順序是：

1. `docker compose up -d`
2. `python backend/scripts/init_db.py`
3. `python backend/scripts/seed_db.py`
4. 啟動 Flask 後端
5. 啟動 React 前端

## 9. 在 Docker 裡查看目前資料

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
