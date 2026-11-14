# -*- coding: utf-8 -*-
"""
測試沙盒的共用設定。

沙盒是正式站旁邊的一份獨立副本：
- 程式碼：git worktree（例如 Desktop\\CafeMatch-test），不碰正式站資料夾
- 資料庫：同一台 MariaDB 上的 <正式庫名>_sandbox，從正式庫複製一份
- 埠：後端 5001、前端 5174（正式站是 5000 / 5173）

資料庫帳密從正式站的 .env 讀，不必另外輸入，也不會印到畫面上。
"""
import os
import sys
from urllib.parse import urlsplit, urlunsplit

from dotenv import dotenv_values

SANDBOX_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROD_ROOT = os.environ.get('CAFEMATCH_PROD_ROOT') or os.path.join(os.path.dirname(SANDBOX_ROOT), 'CafeMatch')
PROD_ENV = os.path.join(PROD_ROOT, '.env')

SUFFIX = '_sandbox'
BACKEND_PORT = 5001
FRONTEND_PORT = 5174
HOST = '127.0.0.1'
FRONTEND_URL = f'http://{HOST}:{FRONTEND_PORT}/'


def die(msg):
    print(f'[錯誤] {msg}')
    sys.exit(1)


def prod_env():
    if os.path.normcase(os.path.abspath(PROD_ROOT)) == os.path.normcase(SANDBOX_ROOT):
        die('沙盒資料夾不能就是正式站資料夾，請用 git worktree 另外建一個。')
    if os.path.exists(os.path.join(SANDBOX_ROOT, '.env')):
        die(f'沙盒資料夾裡有 .env（{SANDBOX_ROOT}），它會蓋掉沙盒設定，請先刪掉。')
    if not os.path.exists(PROD_ENV):
        die(f'找不到正式站的 .env：{PROD_ENV}')
    return dotenv_values(PROD_ENV)


def split_db(uri):
    parts = urlsplit(uri)
    db = parts.path.lstrip('/')
    if not db:
        die('正式站 DB_URI 裡沒有資料庫名稱。')
    return parts, db


def prod_db_uri():
    uri = prod_env().get('DB_URI')
    if not uri or not uri.startswith('mysql'):
        die('正式站 .env 的 DB_URI 不是 MySQL / MariaDB 連線字串。')
    return uri


def sandbox_names():
    """回傳 (正式庫名, 沙盒庫名, 正式 URI, 沙盒 URI)。"""
    uri = prod_db_uri()
    parts, db = split_db(uri)
    if db.endswith(SUFFIX):
        die(f'正式站的資料庫名稱 {db} 已經是 {SUFFIX} 結尾，停止以免搞混。')
    sb = db + SUFFIX
    sb_uri = urlunsplit(parts._replace(path='/' + sb))
    return db, sb, uri, sb_uri
