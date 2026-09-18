"""欄位對帳表的行為測試（純 SQLite，不需要 MySQL）。"""

import sqlalchemy as sa

from utils.schema_sync import ADHOC_COLUMNS, sync_adhoc_columns


def _bare_database():
    """建出缺了那些欄位的資料表，模擬對帳前的舊資料庫。"""
    engine = sa.create_engine('sqlite:///:memory:')
    conn = engine.connect()
    for table in {t for t, _, _ in ADHOC_COLUMNS}:
        conn.execute(sa.text(f'CREATE TABLE `{table}` (id INTEGER PRIMARY KEY)'))
    return conn


def test_missing_columns_are_added():
    conn = _bare_database()
    added = sync_adhoc_columns(conn)
    assert sorted(added) == sorted(f'{t}.{c}' for t, c, _ in ADHOC_COLUMNS)
    inspector = sa.inspect(conn)
    for table, column, _ in ADHOC_COLUMNS:
        assert column in {c['name'] for c in inspector.get_columns(table)}


def test_running_twice_changes_nothing():
    """遷移與 init-db 都會呼叫它，重跑不能有副作用。"""
    conn = _bare_database()
    sync_adhoc_columns(conn)
    assert sync_adhoc_columns(conn) == []


def test_only_the_missing_column_is_touched():
    conn = _bare_database()
    conn.execute(sa.text('ALTER TABLE `cafes` ADD COLUMN `image` LONGTEXT'))
    added = sync_adhoc_columns(conn)
    assert 'cafes.image' not in added
    assert 'cafes.google_place_id' in added


def test_absent_table_is_skipped_instead_of_failing():
    """資料表還沒建出來時直接跳過，不能整個炸掉。"""
    engine = sa.create_engine('sqlite:///:memory:')
    conn = engine.connect()
    conn.execute(sa.text('CREATE TABLE `cafes` (id INTEGER PRIMARY KEY)'))
    added = sync_adhoc_columns(conn)
    assert all(name.startswith('cafes.') for name in added)
    assert 'cafes.image' in added
