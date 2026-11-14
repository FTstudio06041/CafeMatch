# -*- coding: utf-8 -*-
"""
把正式資料庫複製到沙盒資料夾的 sandbox.db（SQLite 檔）。每次執行都重建，回到正式站當下的資料。

- 對正式庫只做讀取（SELECT），用正式站 .env 裡原本的帳號，不需要任何額外權限
- 資料表結構用這個分支的 models 建立（等於已經套用新版遷移）
- 正式庫有、新版 models 沒有的欄位／表會略過；新版多出來的欄位留空

用法：
    python scripts/sandbox/copy_db.py          複製
    python scripts/sandbox/copy_db.py --drop   測完後刪掉 sandbox.db
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sandbox_config import SANDBOX_DB_FILE, die, prod_db_name, prod_db_uri  # noqa: E402

if '--drop' in sys.argv:
    if os.path.exists(SANDBOX_DB_FILE):
        os.remove(SANDBOX_DB_FILE)
    print(f'已刪除 {SANDBOX_DB_FILE}（正式庫沒有動）')
    sys.exit(0)

if os.path.exists(SANDBOX_DB_FILE):
    os.remove(SANDBOX_DB_FILE)

from sqlalchemy import JSON, create_engine, inspect, select  # noqa: E402

from sandbox_app import app, db  # noqa: E402  （載入時已確認連的是 sandbox.db）


def fix_value(col, value):
    # MariaDB 的 JSON 欄位讀出來是字串，寫進 SQLite 的 JSON 欄位前要先還原，否則會被二次編碼
    if isinstance(col.type, JSON) and isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def main():
    prod = create_engine(prod_db_uri(), pool_pre_ping=True)
    prod_tables = set(inspect(prod).get_table_names())
    if not prod_tables:
        die('正式庫裡沒有資料表？停止。')

    with app.app_context():
        db.create_all()
        print(f'複製 {prod_db_name()}（正式，只讀）→ {SANDBOX_DB_FILE}')
        with prod.connect() as src, db.engine.begin() as dst:
            for table in db.metadata.sorted_tables:
                if table.name not in prod_tables:
                    print(f'  {table.name:<28}    新表')
                    continue
                prod_cols = {c['name'] for c in inspect(prod).get_columns(table.name)}
                cols = [c for c in table.columns if c.name in prod_cols]
                rows = src.execute(select(*[db.column(c.name) for c in cols])
                                   .select_from(db.table(table.name))).fetchall()
                if rows:
                    dst.execute(table.insert(), [
                        {c.name: fix_value(c, v) for c, v in zip(cols, r)} for r in rows
                    ])
                print(f'  {table.name:<28} {len(rows):>6} 筆')
    prod.dispose()
    print('複製完成。')


if __name__ == '__main__':
    main()
