"""reconcile columns added outside alembic

把 init-db 裡那串裸 ALTER TABLE 加出來的欄位納入 Alembic 的認知。這些欄位在
實際資料庫裡多半已經存在，所以本遷移逐欄檢查再新增，重複執行不會有副作用；
真正的目的是讓 alembic_version 之後代表得了實際 schema，往後 autogenerate
才不會拿一份錯的現況去比對。

Revision ID: a1c4e7f20b93
Revises: f823bd42ac50
Create Date: 2026-09-18

"""
import sys
from pathlib import Path

from alembic import op

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from utils.schema_sync import sync_adhoc_columns  # noqa: E402


# revision identifiers, used by Alembic.
revision = 'a1c4e7f20b93'
down_revision = 'f823bd42ac50'
branch_labels = None
depends_on = None


def upgrade():
    added = sync_adhoc_columns(op.get_bind())
    for name in added:
        print(f'[MIGRATE] 已新增欄位 {name}')
    if not added:
        print('[MIGRATE] 欄位都已存在，只更新 Alembic 版本')


def downgrade():
    """刻意不刪欄位。

    這些欄位在本遷移之前就存在於實際資料庫，而且裝著線上資料
    （cafes.image 是 base64 圖片、chat_sessions.pref_state 是對話狀態）。
    降版把它們刪掉等於刪資料，不是這支遷移該做的事。
    """
    pass
