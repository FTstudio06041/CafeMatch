"""咖啡護照與咖啡盲盒的資料表。

ShopStateEvent  —— 收藏／去過的「流水帳」。user_shop_state 只存現況（按兩下就歸零），
                   這張表把每一次按下去都留下來：什麼時候、從哪個畫面按的。
                   推薦成效（聊天推薦 → 真的去了）與之後重新訓練 GNN 都靠它。
BlindBox        —— 每週一盒。挑選時的依據（GNN 名次、分數、新鮮度）一起存下來，
                   之後才能回頭驗證「模型猜的 vs 使用者實際反應」。
"""

from database import db
from config.settings import get_utc_now


class ShopStateEvent(db.Model):
    __tablename__ = 'shop_state_events'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    cafe_id = db.Column(db.Integer, db.ForeignKey('cafes.id'), nullable=False, index=True)
    # fav / unfav / visit / unvisit
    action = db.Column(db.String(10), nullable=False)
    # explore / chat / blindbox / passport / unknown —— 白名單見 services/passport_service.py
    source = db.Column(db.String(20), nullable=False, default='unknown')
    created_at = db.Column(db.DateTime, default=get_utc_now, index=True)


class BlindBox(db.Model):
    __tablename__ = 'blind_boxes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    cafe_id = db.Column(db.Integer, db.ForeignKey('cafes.id'), nullable=False)
    # ISO 週次（台灣時間），例如 2026-W46
    week_key = db.Column(db.String(10), nullable=False, index=True)
    # sealed（只看得到提示）→ opened（拆開，看得到店）→ completed（真的去了）
    # 另有 skipped（換一盒）、expired（這週結束還沒去）
    status = db.Column(db.String(10), nullable=False, default='sealed')

    # ---- 挑選依據（離線分析用）----
    # gnn：照測驗分數用 GNN 排名後挑；random：沒測驗或 GNN 不可用時隨機
    pick_source = db.Column(db.String(10), nullable=False, default='random')
    gnn_rank = db.Column(db.Integer, nullable=True)      # 在候選裡的 GNN 名次（1 起算）
    gnn_score = db.Column(db.Float, nullable=True)       # 0~1
    novelty = db.Column(db.Float, nullable=True)         # 跟使用者舒適圈標籤的差異，0~1

    # ---- 使用者反應 ----
    created_at = db.Column(db.DateTime, default=get_utc_now)
    opened_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)    # skipped / expired 的時間
    skip_reason = db.Column(db.String(20), nullable=True)
    rating = db.Column(db.Integer, nullable=True)        # 去過之後的 1~5 分
    comment = db.Column(db.String(200), nullable=True)
