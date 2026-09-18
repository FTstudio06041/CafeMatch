"""init-db 與遷移共用的欄位對帳表。

這些欄位原本是 init-db 裡一串裸 ALTER TABLE 加的，包在 try/except 裡失敗就
當沒事。後果有兩個：Alembic 完全不知道它們存在（autogenerate 會拿一份錯的
現況去比對），而且真正的失敗會被靜靜吞掉 —— chat_sessions.pref_state 就這樣
在資料庫裡缺席，直到聊天整個 500 才被發現。

清單集中在這裡，遷移與 init-db 共用同一份，兩邊不會漂開。
"""

import sqlalchemy as sa

# (資料表, 欄位, DDL 型別宣告)
# 型別沿用當初 ALTER 寫的，不是 models 的宣告 —— 實際資料庫長這樣，
# 例如 cafes.image 是 LONGTEXT（存 base64 圖片），model 寫 db.Text，
# 改成 TEXT 會截斷資料。
ADHOC_COLUMNS = (
    ('user', 'is_admin', 'TINYINT(1) DEFAULT 0'),
    ('user', 'last_read_announcement_id', 'INT DEFAULT 0'),
    ('cafes', 'image', 'LONGTEXT'),
    ('cafes', 'google_place_id', 'VARCHAR(255) DEFAULT NULL'),
    ('cafes', 'google_photo_attribution', 'TEXT'),
    ('community_posts', 'original_post_id', 'INT DEFAULT NULL'),
    ('chat_sessions', 'pref_state', 'JSON NULL'),
)


def sync_adhoc_columns(bind):
    """逐欄檢查再新增，重複執行不會有副作用。

    回傳這次真的加了哪些欄位（`表.欄位` 字串）。跟舊版的差別是不再吞例外：
    欄位已存在就跳過，真的 ALTER 失敗就讓它炸出來，不要再無聲無息。
    """
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    added = []
    for table, column, ddl in ADHOC_COLUMNS:
        if table not in existing_tables:
            continue
        if column in {c['name'] for c in inspector.get_columns(table)}:
            continue
        bind.execute(sa.text(f'ALTER TABLE `{table}` ADD COLUMN `{column}` {ddl}'))
        added.append(f'{table}.{column}')
    return added
