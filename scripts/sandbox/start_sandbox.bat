@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0..\.."
title CafeMatch 測試沙盒

set "PROD=%CD%\..\CafeMatch"
set "PY=%PROD%\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [錯誤] 找不到 %PY%
  pause
  exit /b 1
)

echo.
echo === 1/3 複製正式資料庫到沙盒的 sandbox.db（只讀正式庫）===
"%PY%" scripts\sandbox\copy_db.py
if errorlevel 1 ( pause & exit /b 1 )

echo.
echo === 2/3 安裝前端套件（第一次會久一點）===
cd frontend
if not exist node_modules call npm install --no-audit --no-fund
if errorlevel 1 ( pause & exit /b 1 )
cd ..

echo.
rem VITE_API_URL 一定要設：前端在 127.0.0.1 上預設會直連 localhost:5000（正式站後端）。
rem 設成沙盒前端自己，所有 API 都經 Vite proxy 轉到沙盒後端 5001。
echo === 3/3 啟動沙盒（後端 5001、前端 5174）===
start "CafeMatch 沙盒後端 5001" cmd /k ""%PY%" -m flask --app scripts/sandbox/sandbox_app.py run --host 127.0.0.1 --port 5001"
start "CafeMatch 沙盒前端 5174" /d "%CD%\frontend" cmd /k "set BACKEND_ORIGIN=http://127.0.0.1:5001&& set VITE_API_URL=http://127.0.0.1:5174&& npx vite --host 127.0.0.1 --port 5174 --strictPort"

echo 等待服務啟動...
timeout /t 20 /nobreak >nul
start "" "http://127.0.0.1:5001/sandbox-login"

echo.
echo 沙盒已開啟，瀏覽器會自動用沙盒測試帳號登入。
echo 用自己的帳號登入請開：
echo http://127.0.0.1:5001/sandbox-login?email=YOUR_GMAIL
echo 測完把兩個沙盒視窗關掉即可。
pause
