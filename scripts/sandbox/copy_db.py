# -*- coding: utf-8 -*-
"""
把正式資料庫複製成 <庫名>_sandbox（每次執行都重建，回到正式站當下的資料）。

對正式庫只做讀取：SHOW TABLES / SHOW CREATE TABLE / SELECT。
所有建表、寫入、刪除都只發生在 _sandbox 庫。

用法：
    python scripts/sandbox/copy_db.py          複製
    python scripts/sandbox/copy_db.py --drop   測完後刪掉沙盒庫
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sqlalchemy import create_engine, text  # noqa: E402

from sandbox_config import die, sandbox_names  # noqa: E402


def q(name):
    return '`' + name.replace('`', '``') + '`'


def main():
    prod_db, sb_db, prod_uri, _ = sandbox_names()
    assert sb_db != prod_db and sb_db.endswith('_sandbox')

    engine = create_engine(prod_uri, pool_pre_ping=True)
    with engine.connect() as conn:
        if '--drop' in sys.argv:
            conn.execute(text(f'DROP DATABASE IF EXISTS {q(sb_db)}'))
            conn.commit()
            print(f'已刪除沙盒資料庫 {sb_db}（正式庫 {prod_db} 沒有動）')
            return

        tables = [r[0] for r in conn.execute(
            text(f"SHOW FULL TABLES FROM {q(prod_db)} WHERE Table_type = 'BASE TABLE'"))]
        if not tables:
            die(f'正式庫 {prod_db} 裡沒有資料表？停止。')

        print(f'複製 {prod_db} → {sb_db}（{len(tables)} 張表）')
        conn.execute(text(f'DROP DATABASE IF EXISTS {q(sb_db)}'))
        conn.execute(text(f'CREATE DATABASE {q(sb_db)} CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci'))
        conn.execute(text(f'USE {q(sb_db)}'))
        conn.execute(text('SET FOREIGN_KEY_CHECKS = 0'))
        for t in tables:
            ddl = conn.execute(text(f'SHOW CREATE TABLE {q(prod_db)}.{q(t)}')).fetchone()[1]
            conn.execute(text(ddl))  # 建在目前 USE 的沙盒庫
            conn.execute(text(f'INSERT INTO {q(sb_db)}.{q(t)} SELECT * FROM {q(prod_db)}.{q(t)}'))
            n = conn.execute(text(f'SELECT COUNT(*) FROM {q(sb_db)}.{q(t)}')).scalar()
            print(f'  {t:<28} {n:>6} 筆')
        conn.execute(text('SET FOREIGN_KEY_CHECKS = 1'))
        conn.commit()
    print('複製完成。')


if __name__ == '__main__':
    main()
