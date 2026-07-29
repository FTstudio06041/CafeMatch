# -*- coding: utf-8 -*-
"""
資料庫備份腳本。

用法：
    venv\\Scripts\\python.exe scripts\\backup_db.py            # 備份
    venv\\Scripts\\python.exe scripts\\backup_db.py --list      # 列出現有備份

輸出到專案的 backups/ 目錄，檔名帶時間戳，只保留最新 KEEP_LATEST 份。
優先使用 mysqldump；找不到時退回純 Python 產生 INSERT 語句（較慢但不需外部工具）。
"""

import os
import re
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BACKUP_DIR = os.path.join(ROOT, 'backups')
KEEP_LATEST = 10

# mysqldump 可能的位置（環境變數 > PATH > 常見安裝路徑）
_MYSQLDUMP_CANDIDATES = [
    os.environ.get('MYSQLDUMP_PATH'),
    'mysqldump',
    r'C:\xampp\mysql\bin\mysqldump.exe',
    r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe',
    r'C:\Program Files\MariaDB 11.0\bin\mysqldump.exe',
]


def find_mysqldump():
    for path in _MYSQLDUMP_CANDIDATES:
        if not path:
            continue
        if os.path.isfile(path):
            return path
        if path == 'mysqldump':
            try:
                subprocess.run([path, '--version'], capture_output=True, timeout=5)
                return path
            except (OSError, subprocess.SubprocessError):
                continue
    return None


def parse_db_uri():
    """從 .env / 環境變數的 DB_URI 解析連線資訊。"""
    uri = os.environ.get('DB_URI')
    if not uri:
        env_path = os.path.join(ROOT, '.env')
        if os.path.exists(env_path):
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith('DB_URI='):
                        uri = line.strip().split('=', 1)[1]
                        break
    if not uri:
        uri = 'mysql+pymysql://root:@localhost/cafematch'

    cleaned = re.sub(r'^[a-z+]+://', '//', uri)
    parsed = urlparse(cleaned)
    return {
        'host': parsed.hostname or '127.0.0.1',
        'port': str(parsed.port or 3306),
        'user': unquote(parsed.username or 'root'),
        'password': unquote(parsed.password or ''),
        'db': (parsed.path or '/cafematch').lstrip('/').split('?')[0],
    }


def rotate_backups():
    """只保留最新 KEEP_LATEST 份備份。"""
    files = sorted(
        (f for f in os.listdir(BACKUP_DIR) if f.endswith('.sql')),
        reverse=True,
    )
    removed = []
    for old in files[KEEP_LATEST:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
            removed.append(old)
        except OSError:
            pass
    return removed


def backup_with_mysqldump(dump_path, conf, out_file):
    cmd = [
        dump_path,
        f'--host={conf["host"]}', f'--port={conf["port"]}', f'--user={conf["user"]}',
        '--single-transaction', '--routines', '--events',
        '--default-character-set=utf8mb4',
        conf['db'],
    ]
    if conf['password']:
        cmd.insert(1, f'--password={conf["password"]}')

    with open(out_file, 'wb') as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode('utf-8', 'replace')[:300])


def backup_with_python(out_file):
    """退路：用 SQLAlchemy 逐表產生 INSERT 語句。"""
    from app import app
    from database import db
    from sqlalchemy import inspect, text

    with app.app_context():
        insp = inspect(db.engine)
        tables = insp.get_table_names()
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write('SET FOREIGN_KEY_CHECKS=0;\n')
            for table in tables:
                rows = db.session.execute(text(f'SELECT * FROM `{table}`')).mappings().all()
                if not rows:
                    continue
                cols = ', '.join(f'`{c}`' for c in rows[0].keys())
                f.write(f'\n-- {table} ({len(rows)} rows)\n')
                for row in rows:
                    vals = []
                    for v in row.values():
                        if v is None:
                            vals.append('NULL')
                        elif isinstance(v, (int, float)):
                            vals.append(str(v))
                        else:
                            vals.append("'" + str(v).replace('\\', '\\\\').replace("'", "\\'") + "'")
                    f.write(f'INSERT INTO `{table}` ({cols}) VALUES ({", ".join(vals)});\n')
            f.write('\nSET FOREIGN_KEY_CHECKS=1;\n')


def run_backup():
    """執行備份，回傳 (成功: bool, 訊息: str)。"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    conf = parse_db_uri()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = os.path.join(BACKUP_DIR, f'{conf["db"]}_{stamp}.sql')

    dump_path = find_mysqldump()
    try:
        if dump_path:
            backup_with_mysqldump(dump_path, conf, out_file)
            method = f'mysqldump ({os.path.basename(dump_path)})'
        else:
            backup_with_python(out_file)
            method = 'Python 備援'
    except Exception as e:
        if os.path.exists(out_file):
            os.remove(out_file)
        return False, f'備份失敗：{e}'

    size_kb = os.path.getsize(out_file) / 1024
    removed = rotate_backups()
    msg = f'已備份 {os.path.basename(out_file)}（{size_kb:.0f} KB，{method}）'
    if removed:
        msg += f'；清除 {len(removed)} 份舊備份'
    return True, msg


def list_backups():
    if not os.path.isdir(BACKUP_DIR):
        return []
    out = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith('.sql'):
            p = os.path.join(BACKUP_DIR, f)
            out.append({'name': f, 'size_kb': round(os.path.getsize(p) / 1024)})
    return out


if __name__ == '__main__':
    if '--list' in sys.argv:
        items = list_backups()
        if not items:
            print('尚無備份')
        for i in items:
            print(f'  {i["name"]}  {i["size_kb"]} KB')
    else:
        ok, message = run_backup()
        print(message)
        sys.exit(0 if ok else 1)
