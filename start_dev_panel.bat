@echo off
chcp 65001 >nul
cd /d "%~dp0"
title CafeMatch 啟動面板
echo 正在開啟 CafeMatch 啟動面板 (http://localhost:5999) ...
venv\Scripts\python.exe scripts\dev_launcher.py
