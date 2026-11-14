"""護照頁的滑卡：一張一張看店，右滑「有興趣」（加入想去清單），左滑「沒興趣」。

- 牌堆隨機排序，只出還沒滑過、沒去過、不在想去清單的店
- 每家店只留最後一次的決定（cafe_swipes）；每一次滑動另外記進 shop_state_events，
  source=swipe，動作是 want / pass，復原是 unwant / unpass
- 左滑的店不會進咖啡盲盒（blindbox_service.pick_cafe 會排除）
- 牌堆滑完後可以「重新看看略過的店」：清掉左滑紀錄，那些店回到牌堆
"""

import random

from sqlalchemy.orm import selectinload

from config.settings import get_utc_now
from database import db
from models import Cafes, CafeSwipe, ShopStateEvent, UserShopState
from services.google_maps_service import get_cafe_image_url
from services.passport_service import area_of

DIRECTIONS = ('right', 'left')
# 一次送幾張到前端；滑完再要下一批
DECK_SIZE = 20


def _card(cafe):
    tags = [t.tag_name for t in cafe.tags]
    return {
        'cafe_id': cafe.id,
        'name': cafe.name,
        'image_url': get_cafe_image_url(cafe),
        'area': area_of(cafe.address),
        'address': cafe.address or '',
        'cost': cafe.cost or '',
        'tags': tags[:6],
    }


def _state(user_id, cafe_id):
    state = UserShopState.query.filter_by(user_id=user_id, cafe_id=cafe_id).first()
    if not state:
        state = UserShopState(user_id=user_id, cafe_id=cafe_id, is_fav=False, is_visited=False, is_want=False)
        db.session.add(state)
    return state


def _log(user_id, cafe_id, action, now):
    db.session.add(ShopStateEvent(user_id=user_id, cafe_id=cafe_id, action=action,
                                  source='swipe', created_at=now))


def deck(user_id, size=DECK_SIZE, rng=random):
    """回傳 {cards: [...], remaining: 還有幾張沒滑, passed: 左滑過幾家}。"""
    swiped = {s.cafe_id: s.direction for s in CafeSwipe.query.filter_by(user_id=user_id).all()}
    known = {s.cafe_id for s in UserShopState.query.filter_by(user_id=user_id).all()
             if s.is_visited or s.is_want}
    cafes = Cafes.query.options(selectinload(Cafes.tags)).all()
    pool = [c for c in cafes if c.id not in swiped and c.id not in known]
    rng.shuffle(pool)
    return {
        'cards': [_card(c) for c in pool[:size]],
        'remaining': len(pool),
        'passed': sum(1 for d in swiped.values() if d == 'left'),
    }


def swipe(user_id, cafe_id, direction):
    """記下一次滑動。回傳 (結果 dict, 錯誤訊息)。"""
    if direction not in DIRECTIONS:
        return None, '方向只能是 right 或 left'
    if not db.session.get(Cafes, cafe_id):
        return None, '找不到這間咖啡廳'
    now = get_utc_now()

    record = CafeSwipe.query.filter_by(user_id=user_id, cafe_id=cafe_id).first()
    if record:
        record.direction = direction
        record.created_at = now
    else:
        db.session.add(CafeSwipe(user_id=user_id, cafe_id=cafe_id, direction=direction, created_at=now))

    state = _state(user_id, cafe_id)
    if direction == 'right':
        if not state.is_want:
            state.is_want = True
            state.want_at = now
        _log(user_id, cafe_id, 'want', now)
    else:
        _log(user_id, cafe_id, 'pass', now)
    db.session.commit()
    return {'cafe_id': cafe_id, 'direction': direction, 'want': bool(state.is_want)}, None


def undo(user_id):
    """復原最後一次滑動：那張卡回到牌堆最上面。右滑的話一併從想去清單拿掉。"""
    last = (CafeSwipe.query.filter_by(user_id=user_id)
            .order_by(CafeSwipe.created_at.desc(), CafeSwipe.id.desc()).first())
    if not last:
        return None, '沒有可以復原的滑動'
    now = get_utc_now()
    cafe = db.session.get(Cafes, last.cafe_id, options=[selectinload(Cafes.tags)])
    if last.direction == 'right':
        state = UserShopState.query.filter_by(user_id=user_id, cafe_id=last.cafe_id).first()
        if state and state.is_want:
            state.is_want = False
            state.want_at = None
        _log(user_id, last.cafe_id, 'unwant', now)
    else:
        _log(user_id, last.cafe_id, 'unpass', now)
    direction = last.direction
    db.session.delete(last)
    db.session.commit()
    return {'card': _card(cafe), 'direction': direction}, None


def reset_passed(user_id):
    """清掉左滑紀錄，讓略過的店回到牌堆。流水帳保留，分析時看得到使用者後來又重看。"""
    now = get_utc_now()
    rows = CafeSwipe.query.filter_by(user_id=user_id, direction='left').all()
    for r in rows:
        _log(user_id, r.cafe_id, 'unpass', now)
        db.session.delete(r)
    db.session.commit()
    return len(rows)
