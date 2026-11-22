"""passport and blind box

咖啡護照、每日咖啡盲盒與滑卡：
  - user_shop_state 加上 fav_at / visited_at（蓋章日期）、is_want / want_at（想去清單）
  - 新增 shop_state_events（收藏／去過／想去／滑卡的流水帳）
  - 新增 blind_boxes（每日盲盒與使用者反應）
  - 新增 cafe_swipes（護照頁滑卡：每人每店最後一次的左右滑）

跟上一支一樣逐項檢查再建，重複執行不會有副作用 —— 有些環境是先跑 init-db
（db.create_all 會直接建出新資料表）才跑遷移的。

Revision ID: c3d9a1f5e2b7
Revises: a1c4e7f20b93
Create Date: 2026-11-14

"""
import sqlalchemy as sa
from alembic import op


revision = 'c3d9a1f5e2b7'
down_revision = 'a1c4e7f20b93'
branch_labels = None
depends_on = None


def _columns(inspector, table):
    return {c['name'] for c in inspector.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'user_shop_state' in tables:
        existing = _columns(inspector, 'user_shop_state')
        for name in ('fav_at', 'visited_at', 'want_at'):
            if name not in existing:
                op.add_column('user_shop_state', sa.Column(name, sa.DateTime(), nullable=True))
        if 'is_want' not in existing:
            op.add_column('user_shop_state', sa.Column('is_want', sa.Boolean(), nullable=True))

    if 'shop_state_events' not in tables:
        op.create_table(
            'shop_state_events',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('cafe_id', sa.Integer(), sa.ForeignKey('cafes.id'), nullable=False),
            sa.Column('action', sa.String(10), nullable=False),
            sa.Column('source', sa.String(20), nullable=False, server_default='unknown'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_shop_state_events_user_id', 'shop_state_events', ['user_id'])
        op.create_index('ix_shop_state_events_cafe_id', 'shop_state_events', ['cafe_id'])
        op.create_index('ix_shop_state_events_created_at', 'shop_state_events', ['created_at'])

    if 'blind_boxes' not in tables:
        op.create_table(
            'blind_boxes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('cafe_id', sa.Integer(), sa.ForeignKey('cafes.id'), nullable=False),
            sa.Column('day_key', sa.String(10), nullable=False),
            sa.Column('status', sa.String(10), nullable=False, server_default='sealed'),
            sa.Column('pick_source', sa.String(10), nullable=False, server_default='random'),
            sa.Column('gnn_rank', sa.Integer(), nullable=True),
            sa.Column('gnn_score', sa.Float(), nullable=True),
            sa.Column('novelty', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('opened_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('closed_at', sa.DateTime(), nullable=True),
            sa.Column('skip_reason', sa.String(20), nullable=True),
            sa.Column('rating', sa.Integer(), nullable=True),
            sa.Column('comment', sa.String(200), nullable=True),
        )
        op.create_index('ix_blind_boxes_user_id', 'blind_boxes', ['user_id'])
        op.create_index('ix_blind_boxes_day_key', 'blind_boxes', ['day_key'])

    if 'cafe_swipes' not in tables:
        op.create_table(
            'cafe_swipes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('cafe_id', sa.Integer(), sa.ForeignKey('cafes.id'), nullable=False),
            sa.Column('direction', sa.String(5), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('user_id', 'cafe_id', name='uix_user_cafe_swipe'),
        )
        op.create_index('ix_cafe_swipes_user_id', 'cafe_swipes', ['user_id'])
        op.create_index('ix_cafe_swipes_created_at', 'cafe_swipes', ['created_at'])


def downgrade():
    """新功能的資料表與欄位，降版就整個拿掉（裡面只有這個功能自己產生的資料）。"""
    op.drop_table('cafe_swipes')
    op.drop_table('blind_boxes')
    op.drop_table('shop_state_events')
    with op.batch_alter_table('user_shop_state') as batch:
        batch.drop_column('want_at')
        batch.drop_column('is_want')
        batch.drop_column('visited_at')
        batch.drop_column('fav_at')
