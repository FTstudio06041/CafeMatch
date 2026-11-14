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
echo === 1/4 複製正式資料庫到沙盒（只讀正式庫）===
"%PY%" scripts\sandbox\copy_db.py
if errorlevel 1 ( pause & exit /b 1 )

echo.
echo === 2/4 在沙盒資料庫跑新版遷移 ===
"%PY%" -m flask --app scripts/sandbox/sandbox_app.py db upgrade
if errorlevel 1 ( pause & exit /b 1 )

echo.
echo === 3/4 安裝前端套件（第一次會久一點）===
cd frontend
if not exist node_modules call npm install --no-audit --no-fund
if errorlevel 1 ( pause & exit /b 1 )
cd ..

echo.
echo === 4/4 啟動沙盒（後端 5001、前端 5174）===
start "CafeMatch 沙盒後端 5001" cmd /k ""%PY%" -m flask --app scripts/sandbox/sandbox_app.py run --host 127.0.0.1 --port 5001"
start "CafeMatch 沙盒前端 5174" /d "%CD%\frontend" cmd /k "set BACKEND_ORIGIN=http://127.0.0.1:5001&& npx vite --host 127.0.0.1 --port 5174 --strictPort"

echo 等待服務啟動...
timeout /t 20 /nobreak >nul
start "" "http://127.0.0.1:5001/sandbox-login"

echo.
echo 沙盒已開啟，瀏覽器會用「沙盒測試帳號」登入並進到護照頁。
echo 想用自己的帳號（有做過測驗，盲盒會走 GNN）：
echo   http://127.0.0.1:5001/sandbox-login?email=你的Gmail
echo 測完：關掉兩個沙盒視窗即可。正式站完全不受影響。
pause
