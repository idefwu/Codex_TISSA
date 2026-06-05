# DB Agent Chat

這是「OpenAI Codex 實戰：打造可串接資料庫的 AI Agent 系統」課程的最小可啟動前後端專案。

目前內容：

- `frontend/`：React + Vite 前端
- `backend/`：Python Flask API
- `GET /api/health`：後端健康檢查 API

## 安裝前端套件

請在專案根目錄開啟 terminal，執行：

```powershell
cd frontend
npm install
```

## 安裝後端套件

建議使用課程用的 conda 環境 `Codex_Demo`。

請在專案根目錄執行：

```powershell
conda activate Codex_Demo
pip install -r backend/requirements.txt
```

## 啟動 Flask 後端

請開啟第一個 terminal，執行：

```powershell
conda activate Codex_Demo
cd backend
flask --app app.main run --host 127.0.0.1 --port 5000 --debug
```

後端健康檢查網址：

```text
http://127.0.0.1:5000/api/health
```

預期回應：

```json
{"service":"backend","status":"ok"}
```

## 啟動 React 前端

請開啟第二個 terminal，執行：

```powershell
cd frontend
npm run dev
```

前端網址通常是：

```text
http://localhost:5173
```

前端會透過 Vite proxy 呼叫 Flask 的 `/api/health`，所以建議先啟動 Flask 後端，再啟動 React 前端。
