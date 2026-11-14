"""咖啡盲盒：每週一盒，挑一家「模型覺得你會喜歡、但你自己大概不會選」的店。

流程：
  sealed     只給提示（區域、價位、兩個標籤），看不到店名
  opened     使用者決定拆盒，店家整個翻開
  completed  在任何地方把這家按成「去過」就算完成（不一定要先拆）
  skipped    不想去，換一盒（每週一次），順便問一下為什麼
  expired    週一換週時，上週沒完成的盒子

挑店（pick_cafe）：
  1. 排除去過、收藏過、以前盲盒抽過的店 —— 都是使用者已經知道的
  2. 有測驗分數且 GNN 可用：取 GNN 排名前 POOL_SIZE 名，
     再依「跟舒適圈（去過＋收藏的店的標籤）有多不一樣」排序，從前 PICK_FROM 名隨機挑一家
  3. 否則從剩下的店隨機挑
挑選依據（名次、分數、新鮮度、來源）全部存進 blind_boxes，之後才能回頭驗證。
"""

import random

from sqlalchemy.orm import selectinload

from config.settings import get_utc_now
from database import db
from models import BlindBox, Cafes, UserQuizResult, UserShopState
from services.google_maps_service import get_cafe_image_url
from services.passport_service import area_of, week_end_utc, week_key, _iso

# GNN 排名前幾名才有資格進盲盒：太後面的店，模型自己都不看好
POOL_SIZE = 12
# 新鮮度最高的前幾名裡隨機挑一家，同一個人每週才不會總是同一種店
PICK_FROM = 3
# 每週可以換幾次盒
REROLLS_PER_WEEK = 1
# 換盒時可選的原因（存進 skip_reason，給之後分析「為什麼推了沒人去」）
SKIP_REASONS = ('too_far', 'not_my_type', 'been_there', 'no_time', 'other')
# 提示露出幾個標籤
HINT_TAGS = 2

DIMS = ('work', 'env', 'social', 'taste', 'cp')


# ==========================================
# 挑店（純函式，方便測試）
# ==========================================

def novelty(cafe_tags, comfort_tags):
    """1 - Jaccard。舒適圈還是空的（新使用者）時，每家店都算全新。"""
    a, b = set(cafe_tags), set(comfort_tags)
    if not b or not a:
        return 1.0
    return 1.0 - len(a & b) / len(a | b)


def choose_from_ranked(ranked, cafe_tags, comfort_tags, rng=random):
    """從 GNN 完整排名裡挑一家。

    ranked:      gnn_recommender.rank_all() 的結果（已排除不該出現的店）
    cafe_tags:   {cafe_id: [tag_name]}
    comfort_tags 使用者舒適圈的標籤集合
    回傳 (候選 dict, novelty)；ranked 是空的回傳 (None, None)
    """
    pool = ranked[:POOL_SIZE]
    if not pool:
        return None, None
    scored = [(novelty(cafe_tags.get(c['cafe_id'], []), comfort_tags), c) for c in pool]
    # 新鮮度高的優先；一樣新鮮就看 GNN 名次
    scored.sort(key=lambda x: (-x[0], x[1]['rank']))
    nov, chosen = rng.choice(scored[:PICK_FROM])
    return chosen, nov


def _latest_quiz_scores(user_id):
    r = (UserQuizResult.query.filter_by(user_id=user_id)
         .order_by(UserQuizResult.created_at.desc()).first())
    if not r:
        return None
    scores = {d: getattr(r, f'score_{d}') or 0 for d in DIMS}
    return scores if any(scores.values()) else None


def pick_cafe(user_id, rng=random):
    """回傳要放進盲盒的 dict：{cafe_id, pick_source, gnn_rank, gnn_score, novelty}；沒店可挑回傳 None。"""
    states = UserShopState.query.filter_by(user_id=user_id).all()
    known = {s.cafe_id for s in states if s.is_visited or s.is_fav}
    previous = {b.cafe_id for b in BlindBox.query.filter_by(user_id=user_id).all()}

    cafes = Cafes.query.options(selectinload(Cafes.tags)).all()
    cafe_tags = {c.id: [t.tag_name for t in c.tags] for c in cafes}
    all_ids = set(cafe_tags)

    excluded = known | previous
    if not (all_ids - excluded):
        # 以前抽過的都輪完了：放寬成只排除去過／收藏的
        excluded = known
    remaining = all_ids - excluded
    if not remaining:
        return None

    comfort = {t for cid in known for t in cafe_tags.get(cid, [])}

    scores = _latest_quiz_scores(user_id)
    if scores:
        try:
            from services import gnn_recommender
            ranked = gnn_recommender.rank_all(scores, exclude_ids=excluded)
            ranked = [c for c in ranked if c['cafe_id'] in remaining]
            chosen, nov = choose_from_ranked(ranked, cafe_tags, comfort, rng)
            if chosen:
                return {'cafe_id': chosen['cafe_id'], 'pick_source': 'gnn',
                        'gnn_rank': chosen['rank'], 'gnn_score': chosen['gnn_score'],
                        'novelty': nov}
        except Exception:  # GnnUnavailable 或任何推論錯誤：退回隨機，盲盒不能因此打不開
            pass

    cafe_id = rng.choice(sorted(remaining))
    return {'cafe_id': cafe_id, 'pick_source': 'random', 'gnn_rank': None,
            'gnn_score': None, 'novelty': novelty(cafe_tags.get(cafe_id, []), comfort)}


# ==========================================
# 盒子的生命週期
# ==========================================

def _expire_old(user_id, current_week, now):
    stale = BlindBox.query.filter(
        BlindBox.user_id == user_id,
        BlindBox.week_key != current_week,
        BlindBox.status.in_(('sealed', 'opened')),
    ).all()
    for box in stale:
        box.status = 'expired'
        box.closed_at = now


def _current_box(user_id, wk):
    return (BlindBox.query
            .filter(BlindBox.user_id == user_id, BlindBox.week_key == wk,
                    BlindBox.status != 'skipped')
            .order_by(BlindBox.id.desc()).first())


def _rerolls_used(user_id, wk):
    return BlindBox.query.filter_by(user_id=user_id, week_key=wk, status='skipped').count()


def _new_box(user_id, wk, now, rng=random):
    picked = pick_cafe(user_id, rng)
    if not picked:
        return None
    box = BlindBox(user_id=user_id, week_key=wk, status='sealed', created_at=now, **picked)
    db.session.add(box)
    return box


def get_or_create_current(user_id, rng=random):
    """這週的盒子；還沒有就現抽一盒。上週沒完成的順便標成 expired。"""
    now = get_utc_now()
    wk = week_key(now)
    _expire_old(user_id, wk, now)
    box = _current_box(user_id, wk)
    if not box:
        box = _new_box(user_id, wk, now, rng)
    db.session.commit()
    return box


def open_box(user_id):
    box = _current_box(user_id, week_key())
    if box and box.status == 'sealed':
        box.status = 'opened'
        box.opened_at = get_utc_now()
        db.session.commit()
    return box


def reroll(user_id, reason, rng=random):
    """換一盒。回傳 (新盒子, 錯誤訊息)。"""
    now = get_utc_now()
    wk = week_key(now)
    box = _current_box(user_id, wk)
    if not box or box.status not in ('sealed', 'opened'):
        return None, '這週沒有可以換的盒子'
    if _rerolls_used(user_id, wk) >= REROLLS_PER_WEEK:
        return None, '這週已經換過了，下週一會有新的盒子'
    box.status = 'skipped'
    box.closed_at = now
    box.skip_reason = reason if reason in SKIP_REASONS else 'other'
    db.session.flush()
    new_box = _new_box(user_id, wk, now, rng)
    db.session.commit()
    return new_box, None


def complete_if_matches(user_id, cafe_id, now):
    """使用者把某家店按成「去過」時呼叫：剛好是這週盒子裡的店就算完成。

    不 commit，跟著呼叫端（passport_service.toggle_shop_state）同一個交易。
    """
    box = _current_box(user_id, week_key(now))
    if box and box.cafe_id == cafe_id and box.status in ('sealed', 'opened'):
        box.status = 'completed'
        box.completed_at = now
        if not box.opened_at:
            box.opened_at = now
        return box
    return None


def rate(user_id, box_id, rating, comment):
    box = BlindBox.query.filter_by(id=box_id, user_id=user_id).first()
    if not box or box.status != 'completed':
        return None, '只有完成的盲盒可以評分'
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return None, '評分要是 1 到 5'
    if not 1 <= rating <= 5:
        return None, '評分要是 1 到 5'
    box.rating = rating
    box.comment = (comment or '').strip()[:200] or None
    db.session.commit()
    return box, None


# ==========================================
# 序列化
# ==========================================

def serialize(box, user_id):
    if box is None:
        return {'status': 'empty'}
    cafe = db.session.get(Cafes, box.cafe_id, options=[selectinload(Cafes.tags)])
    tags = [t.tag_name for t in cafe.tags] if cafe else []
    wk = box.week_key
    data = {
        'id': box.id,
        'status': box.status,
        'week_key': wk,
        'ends_at': _iso(week_end_utc()),
        'rerolls_left': max(0, REROLLS_PER_WEEK - _rerolls_used(user_id, wk)),
        'hints': {
            'area': area_of(cafe.address) if cafe else '',
            'cost': (cafe.cost if cafe else '') or '',
            'tags': tags[:HINT_TAGS],
        },
        'rating': box.rating,
        'opened_at': _iso(box.opened_at),
        'completed_at': _iso(box.completed_at),
    }
    # 沒拆開之前，店名、地址、圖片都不能送到前端（看原始碼就破梗了）
    if box.status in ('opened', 'completed') and cafe:
        data['cafe'] = {
            'id': cafe.id,
            'name': cafe.name,
            'address': cafe.address or '',
            'image_url': get_cafe_image_url(cafe),
            'tags': tags[:6],
            'cost': cafe.cost or '',
        }
    return data


def history(user_id, exclude_id=None, limit=8):
    """過去的盒子。exclude_id 是目前顯示在卡片上的那盒（這週完成的），不要重複列。"""
    rows = (BlindBox.query.filter(BlindBox.user_id == user_id,
                                  BlindBox.id != (exclude_id or -1),
                                  BlindBox.status.in_(('completed', 'expired', 'skipped')))
            .order_by(BlindBox.id.desc()).limit(limit).all())
    names = {c.id: c.name for c in Cafes.query.filter(Cafes.id.in_([b.cafe_id for b in rows])).all()} if rows else {}
    return [{
        'id': b.id,
        'week_key': b.week_key,
        'status': b.status,
        # 沒拆就放掉的盒子，事後也不公開是哪家 —— 留著懸念
        'cafe_name': names.get(b.cafe_id) if b.opened_at else None,
        'rating': b.rating,
    } for b in rows]
