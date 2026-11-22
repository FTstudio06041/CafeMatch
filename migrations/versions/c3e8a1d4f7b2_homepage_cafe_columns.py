"""homepage redesign: cafe coordinates, review ratings, cafe status reports

首頁改版需要的欄位：
  cafes.lat / lng            地圖座標（scripts/backfill_cafe_coords.py 回填）
  community_posts.rating     店家評論的星等（評論沿用社群貼文）
  community_posts.updated_at 評論編輯時間
  community_notes.cafe_id    店家的 24 小時現況回報（沿用便利貼）

與 init-db 共用 utils/schema_sync.py 的清單，逐欄檢查再新增，重跑不會有副作用。

Revision ID: c3e8a1d4f7b2
Revises: a1c4e7f20b93
Create Date: 2026-10-15

"""
import sys
from pathlib import Path

import sqlalchemy as sa
from alembic import op

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from utils.schema_sync import HOMEPAGE_COLUMNS, sync_columns  # noqa: E402


# revision identifiers, used by Alembic.
revision = 'c3e8a1d4f7b2'
down_revision = 'a1c4e7f20b93'
branch_labels = None
depends_on = None


def upgrade():
    added = sync_columns(op.get_bind(), HOMEPAGE_COLUMNS)
    for name in added:
        print(f'[MIGRATE] 已新增欄位 {name}')
    if not added:
        print('[MIGRATE] 欄位都已存在，只更新 Alembic 版本')


def downgrade():
    # 這些欄位是本遷移新增的，降版就拿掉。注意 rating 拿掉後，
    # 店家評論會退回成沒有星等的普通貼文。
    inspector = sa.inspect(op.get_bind())
    for table, column, _ in reversed(HOMEPAGE_COLUMNS):
        if column in {c['name'] for c in inspector.get_columns(table)}:
            op.drop_column(table, column)
