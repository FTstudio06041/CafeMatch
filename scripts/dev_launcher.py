# -*- coding: utf-8 -*-
"""
CafeMatch 開發啟動面板

一個本機小網頁（http://localhost:5999），顯示開發環境四個服務的即時狀態，
並可一鍵啟動缺少的服務：

    MySQL（僅狀態檢查，Windows 服務需自行啟動）
    Ollama（ollama serve）
    後端 Flask（venv python app.py，port 5000）
    前端 Vite（npm run dev，port 5173）

使用方式：雙擊專案根目錄的 start_dev_panel.bat，或
    venv\\Scripts\\python.exe scripts\\dev_launcher.py
"""

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from flask import Flask, jsonify, render_template_string

PANEL_PORT = 5999
CREATE_NEW_CONSOLE = 0x00000010  # 每個服務開自己的主控台視窗，日誌可見、要關就關視窗

SERVICES = {
    "mysql":    {"label": "MySQL 資料庫", "port": 3306, "startable": False,
                 "hint": "Windows 服務，請從「服務」管理員或 MySQL Workbench 啟動"},
    "ollama":   {"label": "Ollama（AI 模型）", "port": 11434, "startable": True},
    "backend":  {"label": "後端 Flask API", "port": 5000, "startable": True},
    "frontend": {"label": "前端 Vite 網站", "port": 5173, "startable": True},
}


def port_open(port: int) -> bool:
    # 用 localhost 解析（同時嘗試 IPv4 與 IPv6）：
    # 新版 Vite 預設只綁 ::1，僅檢查 127.0.0.1 會誤判為未啟動
    try:
        with socket.create_connection(("localhost", port), timeout=0.6):
            return True
    except OSError:
        return False


# 各服務的啟動指令與工作目錄（用 cmd /k：指令失敗時視窗會留著顯示錯誤，方便排查）
_START_COMMANDS = {
    "backend": (r'"%s" app.py' % os.path.join(ROOT, "venv", "Scripts", "python.exe"), ROOT),
    "frontend": ("npm run dev", os.path.join(ROOT, "frontend")),
    "ollama": ("ollama serve", ROOT),
}

# 啟動後等待連線的秒數（前端 Vite 冷啟較久）
_STARTUP_WAIT = {"backend": 12, "frontend": 25, "ollama": 20}


def start_service(name: str) -> str:
    """
    啟動服務：開新的 cmd 視窗執行（失敗時視窗保留，錯誤訊息看得到），
    接著輪詢連接埠確認是否真的起來，回傳可讀的結果訊息。
    """
    svc = SERVICES[name]
    if port_open(svc["port"]):
        return "已經在執行中"
    if name not in _START_COMMANDS:
        return "此服務不支援從面板啟動"

    command, cwd = _START_COMMANDS[name]
    env = {**os.environ, "PYTHONUTF8": "1"}
    title = f"CafeMatch - {svc['label']}"
    try:
        # /k 保留視窗：服務正常時顯示日誌，啟動失敗時錯誤訊息不會一閃即逝
        subprocess.Popen(
            f'start "{title}" cmd /k {command}',
            shell=True, cwd=cwd, env=env,
        )
    except OSError as e:
        return f"啟動失敗：{e}"

    deadline = time.time() + _STARTUP_WAIT.get(name, 15)
    while time.time() < deadline:
        if port_open(svc["port"]):
            return "啟動成功"
        time.sleep(0.5)
    return f"尚未在 {_STARTUP_WAIT.get(name, 15)} 秒內就緒，請看新開的「{title}」視窗確認錯誤"


app = Flask(__name__)

PAGE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CafeMatch 啟動面板</title>
<style>
  :root {
    --bg: #faf7f1; --surface: #ffffff; --ink: #2b2118; --muted: #7d6c59;
    --line: #e7ddcf; --accent: #432a00; --accent-2: #8b5a2b;
    --ok: #1d6f5c; --ok-bg: #e2f1ec; --down: #a32d2d; --down-bg: #fceaea;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: "Noto Sans TC", "Microsoft JhengHei", system-ui, sans-serif;
    line-height: 1.7;
  }
  .wrap { max-width: 720px; margin: 0 auto; padding: 40px 20px 64px; }
  header { border-bottom: 2px solid var(--accent); padding-bottom: 18px; margin-bottom: 24px; }
  .eyebrow { font-size: 12px; letter-spacing: .18em; color: var(--accent-2); margin: 0 0 6px; }
  h1 { font-size: 26px; margin: 0 0 4px; }
  .sub { font-size: 13px; color: var(--muted); margin: 0; }
  .actions { display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0 26px; }
  button, .linkbtn {
    font: inherit; font-size: 14px; font-weight: 700; cursor: pointer;
    border-radius: 999px; padding: 10px 22px; border: 1px solid var(--accent);
    background: var(--accent); color: #fff; text-decoration: none; display: inline-block;
  }
  button:hover, .linkbtn:hover { background: var(--accent-2); border-color: var(--accent-2); }
  button:disabled { opacity: .45; cursor: not-allowed; }
  .linkbtn.ghost { background: transparent; color: var(--accent); }
  .linkbtn.ghost:hover { background: var(--surface); color: var(--accent-2); }
  .grid { display: grid; gap: 14px; }
  .card {
    background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
    padding: 16px 20px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }
  .card .info { flex: 1; min-width: 200px; }
  .card h2 { font-size: 16px; margin: 0; }
  .card .hint { font-size: 12.5px; color: var(--muted); }
  .pill {
    display: inline-flex; align-items: center; gap: 7px;
    font-size: 13px; font-weight: 700; border-radius: 999px; padding: 4px 14px;
  }
  .pill .dot { width: 9px; height: 9px; border-radius: 50%; }
  .pill.ok { color: var(--ok); background: var(--ok-bg); }
  .pill.ok .dot { background: var(--ok); }
  .pill.down { color: var(--down); background: var(--down-bg); }
  .pill.down .dot { background: var(--down); }
  .card button { padding: 8px 18px; font-size: 13px; }
  .msg { font-size: 13px; color: var(--muted); min-height: 22px; margin-top: 14px; }
  footer { margin-top: 32px; font-size: 12px; color: var(--muted); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="eyebrow">CAFEMATCH · 啡你莫屬</p>
    <h1>開發啟動面板</h1>
    <p class="sub">狀態每 3 秒自動更新。啟動的服務會各自開一個主控台視窗，關閉視窗即停止服務。</p>
  </header>

  <div class="actions">
    <button id="startAll">一鍵啟動全部</button>
    <a class="linkbtn ghost" href="http://localhost:5173" target="_blank" rel="noopener">開啟網站</a>
    <a class="linkbtn ghost" href="http://localhost:5173/quiz" target="_blank" rel="noopener">開啟測驗頁</a>
  </div>

  <div class="grid" id="cards"></div>
  <p class="msg" id="msg"></p>

  <div class="card" style="margin-top:22px; align-items:flex-start; flex-direction:column; gap:10px;">
    <div class="info" style="width:100%">
      <h2>資料庫備份</h2>
      <div class="hint" id="backupHint">保留最新 10 份，輸出到專案的 backups/ 目錄</div>
    </div>
    <button id="backupBtn">立即備份</button>
  </div>

  <footer>面板本身跑在 http://localhost:5999 · 關閉面板不影響已啟動的服務</footer>
</div>

<script>
const SERVICES = {{ services_json | safe }};
const cards = document.getElementById('cards');
const msg = document.getElementById('msg');

function render(status) {
  cards.innerHTML = '';
  for (const [name, svc] of Object.entries(SERVICES)) {
    const up = status[name];
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="info">
        <h2>${svc.label}</h2>
        <div class="hint">port ${svc.port}${svc.hint ? '　·　' + svc.hint : ''}</div>
      </div>
      <span class="pill ${up ? 'ok' : 'down'}"><span class="dot"></span>${up ? '執行中' : '未啟動'}</span>
    `;
    if (svc.startable) {
      const btn = document.createElement('button');
      btn.textContent = up ? '執行中' : '啟動';
      btn.disabled = up;
      btn.onclick = () => startOne(name, svc.label);
      card.appendChild(btn);
    }
    cards.appendChild(card);
  }
}

async function refresh() {
  try {
    const r = await fetch('/api/status');
    render(await r.json());
  } catch (e) {}
}

async function startOne(name, label) {
  msg.textContent = `正在啟動 ${label}⋯`;
  const r = await fetch('/api/start/' + name, { method: 'POST' });
  const d = await r.json();
  msg.textContent = `${label}：${d.message}`;
  setTimeout(refresh, 1500);
}

document.getElementById('startAll').onclick = async () => {
  msg.textContent = '正在啟動缺少的服務⋯（等待就緒，最多約 25 秒）';
  const r = await fetch('/api/start-all', { method: 'POST' });
  const d = await r.json();
  msg.textContent = d.message;
  refresh();
};

const backupBtn = document.getElementById('backupBtn');
const backupHint = document.getElementById('backupHint');

async function loadBackups() {
  try {
    const r = await fetch('/api/backups');
    const d = await r.json();
    backupHint.textContent = d.items.length
      ? `最近一次：${d.items[0].name}（${d.items[0].size_kb} KB）　共 ${d.items.length} 份`
      : '尚無備份　·　保留最新 10 份，輸出到專案的 backups/ 目錄';
  } catch (e) {}
}

backupBtn.onclick = async () => {
  backupBtn.disabled = true;
  backupBtn.textContent = '備份中⋯';
  const r = await fetch('/api/backup', { method: 'POST' });
  const d = await r.json();
  msg.textContent = d.message;
  backupBtn.disabled = false;
  backupBtn.textContent = '立即備份';
  loadBackups();
};

refresh();
loadBackups();
setInterval(refresh, 3000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    import json
    return render_template_string(PAGE, services_json=json.dumps(SERVICES, ensure_ascii=False))


@app.route("/api/status")
def api_status():
    return jsonify({name: port_open(svc["port"]) for name, svc in SERVICES.items()})


@app.route("/api/start/<name>", methods=["POST"])
def api_start(name):
    if name not in SERVICES:
        return jsonify({"message": "未知的服務"}), 404
    return jsonify({"message": start_service(name)})


@app.route("/api/start-all", methods=["POST"])
def api_start_all():
    results = []
    # Ollama 先起，後端健康檢查會用到
    for name in ("ollama", "backend", "frontend"):
        if not port_open(SERVICES[name]["port"]):
            results.append(f"{SERVICES[name]['label']}：{start_service(name)}")
    if not port_open(SERVICES["mysql"]["port"]):
        results.append("MySQL 未啟動，請從 Windows 服務管理員啟動")
    return jsonify({"message": "；".join(results) if results else "全部服務都已在執行中"})


@app.route("/api/backup", methods=["POST"])
def api_backup():
    from scripts.backup_db import run_backup
    ok, message = run_backup()
    return jsonify({"ok": ok, "message": message})


@app.route("/api/backups")
def api_backups():
    from scripts.backup_db import list_backups
    return jsonify({"items": list_backups()})


if __name__ == "__main__":
    if port_open(PANEL_PORT):
        # 面板已開著，直接打開瀏覽器就好
        webbrowser.open(f"http://localhost:{PANEL_PORT}")
        sys.exit(0)
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PANEL_PORT}")).start()
    app.run(port=PANEL_PORT, debug=False)
