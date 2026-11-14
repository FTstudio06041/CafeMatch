# -*- coding: utf-8 -*-
"""
沙盒用的 Flask 進入點：設定好沙盒環境變數後才載入 app.py，
另外加一個只在沙盒存在的 /sandbox-login，免 Google 直接登入。

    python -m flask --app scripts/sandbox/sandbox_app.py run --port 5001

資料庫是沙盒資料夾裡的 sandbox.db（由 copy_db.py 建立），不連正式庫。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sandbox_config import (  # noqa: E402
    FRONTEND_URL, HOST, SANDBOX_DB_FILE, SANDBOX_DB_URI, SANDBOX_ROOT, die, prod_env,
)

# 沿用正式站的非機密設定（Ollama、地圖金鑰等），蓋掉所有會指向正式站的設定
for k, v in prod_env().items():
    if v is not None:
        os.environ[k] = v
os.environ.update({
    'DB_URI': SANDBOX_DB_URI,
    'SECRET_KEY': 'cafematch-sandbox-only',
    'FLASK_ENV': 'development',
    'FRONTEND_URL': FRONTEND_URL,
    'CORS_ORIGINS': FRONTEND_URL.rstrip('/'),
})
for k in ('GOOGLE_CALLBACK_URL', 'TEST_DB_URI'):
    os.environ.pop(k, None)

sys.path.insert(0, SANDBOX_ROOT)
os.chdir(SANDBOX_ROOT)
from flask import redirect, request, session  # noqa: E402

from app import app  # noqa: E402
from database import db  # noqa: E402
from models import User  # noqa: E402

# 最後一道保險：真的連到沙盒的 SQLite 檔才放行
if app.config['SQLALCHEMY_DATABASE_URI'] != SANDBOX_DB_URI:
    die('沙盒沒有連到 sandbox.db，停止。')

print(f'[沙盒] 資料庫：{SANDBOX_DB_FILE}　前端：{FRONTEND_URL}')


@app.route('/sandbox-login')
def sandbox_login():
    """沙盒專用：直接以指定 email 登入（不存在就建立）。只在本機 127.0.0.1 可連。"""
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return '只限本機', 403
    email = (request.args.get('email') or 'tester@sandbox.local').strip()
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name='沙盒測試帳號')
        db.session.add(user)
        db.session.commit()
    session['user_email'] = email
    return redirect(FRONTEND_URL + (request.args.get('next') or 'passport').lstrip('/'))


def _login_via_sandbox():
    # 沙盒頁面上的「Google 登入」也改走沙盒登入，不會去 Google、也不會碰到正式站
    return redirect(f'http://{HOST}:5001/sandbox-login')


app.view_functions['auth.login'] = _login_via_sandbox


if __name__ == '__main__':
    app.run(host=HOST, port=5001, debug=False)
