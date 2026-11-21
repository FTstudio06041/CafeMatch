"""fix garbled address of Ngchus 晤子咖啡

匯入時把英文格式的地址（No. 11, 建中街, 花蓮市, 花蓮縣 970）倒過來拼成了
「號 No, No. 11建中街花蓮市花蓮縣970」，推薦卡片直接顯示這串亂碼。
只改仍是這串錯誤值的那一筆，後台若已手動改過就不動。

Revision ID: b7d2e9a4c1f0
Revises: a1c4e7f20b93
Create Date: 2026-11-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7d2e9a4c1f0'
down_revision = 'a1c4e7f20b93'
branch_labels = None
depends_on = None

_BAD = '號 No, No. 11建中街花蓮市花蓮縣970'
_GOOD = '970花蓮縣花蓮市建中街11號'


def upgrade():
    op.get_bind().execute(
        sa.text('UPDATE cafes SET address = :good WHERE address = :bad'),
        {'good': _GOOD, 'bad': _BAD},
    )


def downgrade():
    op.get_bind().execute(
        sa.text('UPDATE cafes SET address = :bad WHERE address = :good AND name LIKE :name'),
        {'good': _GOOD, 'bad': _BAD, 'name': 'Ngchus%'},
    )
