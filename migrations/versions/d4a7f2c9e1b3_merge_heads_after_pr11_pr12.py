"""merge migration heads after PR #11 and #12

三支遷移都接在 a1c4e7f20b93 後面平行開發，合併進 main 後變成三個 head，
`flask db upgrade` 會因為不知道要升到哪一個而失敗：
  b7d2e9a4c1f0  修正 Ngchus 晤子咖啡地址
  c3d9a1f5e2b7  咖啡護照與盲盒（#11）
  c3e8a1d4f7b2  首頁改版欄位（#12）
三者動到的資料表互不重疊，這裡只把它們接回同一條線，不做任何變更。

Revision ID: d4a7f2c9e1b3
Revises: b7d2e9a4c1f0, c3d9a1f5e2b7, c3e8a1d4f7b2
Create Date: 2026-11-22

"""


# revision identifiers, used by Alembic.
revision = 'd4a7f2c9e1b3'
down_revision = ('b7d2e9a4c1f0', 'c3d9a1f5e2b7', 'c3e8a1d4f7b2')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
