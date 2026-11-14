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
import datetime as dt
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

from sqlalchemy import JSON, Date, DateTime, Time, create_engine, inspect, select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from sandbox_app import app, db  # noqa: E402  （載入時已確認連的是 sandbox.db）


def _parse_dt(value, kind):
    """MariaDB 的 0000-00-00 這類零日期，pymysql 會回傳字串，SQLite 收不了。"""
    text_value = value.decode() if isinstance(value, bytes) else str(value)
    if text_value.startswith('0000'):
        return None
    try:
        parsed = dt.datetime.fromisoformat(text_value.replace(' ', 'T'))
    except ValueError:
        return None
    return parsed.date() if kind is Date else parsed


def fix_value(col, value):
    if value is None:
        return None
    # MariaDB 的 JSON 欄位讀出來是字串，寫進 SQLite 的 JSON 欄位前要先還原，否則會被二次編碼
    if isinstance(col.type, JSON) and isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except ValueError:
            return value
    if isinstance(col.type, DateTime) and not isinstance(value, dt.datetime):
        return _parse_dt(value, DateTime)
    if isinstance(col.type, Date) and not isinstance(col.type, DateTime) and not isinstance(value, dt.date):
        return _parse_dt(value, Date)
    if isinstance(col.type, Time) and isinstance(value, dt.timedelta):
        secs = int(value.total_seconds()) % 86400
        return dt.time(secs // 3600, secs % 3600 // 60, secs % 60)
    return value


def short(err):
    msg = str(getattr(err, 'orig', None) or err).splitlines()[0]
    return msg[:200]


def insert_rows(conn, table, cols, rows):
    """整批寫入；失敗就逐筆寫，寫不進去的略過並回報，不讓整個複製中斷。"""
    data = [{c.name: fix_value(c, v) for c, v in zip(cols, r)} for r in rows]
    try:
        with conn.begin_nested():
            conn.execute(table.insert(), data)
        return len(data), []
    except SQLAlchemyError:
        pass
    ok, errors = 0, []
    for row in data:
        try:
            with conn.begin_nested():
                conn.execute(table.insert(), row)
            ok += 1
        except SQLAlchemyError as e:
            errors.append(short(e))
    return ok, errors


def main():
    prod = create_engine(prod_db_uri(), pool_pre_ping=True)
    prod_tables = set(inspect(prod).get_table_names())
    if not prod_tables:
        die('正式庫裡沒有資料表？停止。')

    with app.app_context():
        db.create_all()
        print(f'複製 {prod_db_name()}（正式，只讀）→ {SANDBOX_DB_FILE}')
        skipped_total = 0
        with prod.connect() as src, db.engine.begin() as dst:
            for table in db.metadata.sorted_tables:
                if table.name not in prod_tables:
                    print(f'  {table.name:<28}    新表')
                    continue
                prod_cols = {c['name'] for c in inspect(prod).get_columns(table.name)}
                cols = [c for c in table.columns if c.name in prod_cols]
                try:
                    rows = src.execute(select(*[db.column(c.name) for c in cols])
                                       .select_from(db.table(table.name))).fetchall()
                except SQLAlchemyError as e:
                    print(f'  {table.name:<28}  讀取失敗，略過：{short(e)}')
                    continue
                ok, errors = insert_rows(dst, table, cols, rows) if rows else (0, [])
                note = f'（略過 {len(errors)} 筆：{errors[0]}）' if errors else ''
                print(f'  {table.name:<28} {ok:>6} 筆{note}')
                skipped_total += len(errors)
        if skipped_total:
            print(f'注意：共略過 {skipped_total} 筆無法複製的資料，沙盒仍可使用。')
    prod.dispose()
    print('複製完成。')


if __name__ == '__main__':
    try:
        main()
    except SQLAlchemyError as e:
        die(f'複製失敗：{short(e)}')
