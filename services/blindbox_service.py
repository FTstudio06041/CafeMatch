"""咖啡盲盒：每天一盒，挑一家「模型覺得你會喜歡、但你自己大概不會選」的店。

流程：
  sealed     只給提示（區域、價位、兩個標籤），看不到店名
  opened     使用者決定拆盒，店家整個翻開
  completed  在任何地方把這家按成「去過」就算完成（不一定要先拆）
  skipped    不想去，換一盒（每天一次），順便問一下為什麼
  expired    沒拆的盒子隔天過期；拆了但還沒去的，保留 OPENED_KEEP_DAYS 天再過期
             （拆開代表有興趣，多數人不會當天就去，留幾天讓它還能完成）

挑店（pick_cafe）：
  1. 排除去過、收藏過、以前盲盒抽過、滑卡左滑（沒興趣）的店
  2. 有測驗分數且 GNN 可用：取 GNN 排名前 POOL_SIZE 名，
     再依「跟舒適圈（去過＋收藏的店的標籤）有多不一樣」排序，從前 PICK_FROM 名隨機挑一家
  3. 否則從剩下的店隨機挑
挑選依據（名次、分數、新鮮度、來源）全部存進 blind_boxes，之後才能回頭驗證。
"""

import random

from sqlalchemy.orm import selectinload

from config.settings import get_utc_now
from database import db
from models import BlindBox, Cafes, CafeSwipe, UserQuizResult, UserShopState
from services.google_maps_service import get_cafe_image_url
from datetime import timedelta

from services.passport_service import area_of, day_end_utc, day_key, naive_utc, _iso

# GNN 排名前幾名才有資格進盲盒：太後面的店，模型自己都不看好
POOL_SIZE = 12
# 新鮮度最高的前幾名裡隨機挑一家，同一個人才不會每天都是同一種店
PICK_FROM = 3
# 每天可以換幾次盒
REROLLS_PER_DAY = 1
# 拆開但還沒去的盒子保留幾天（期間把那家按成去過，一樣算完成）
OPENED_KEEP_DAYS = 7
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
    passed = {s.cafe_id for s in CafeSwipe.query.filter_by(user_id=user_id, direction='left').all()}

    cafes = Cafes.query.options(selectinload(Cafes.tags)).all()
    cafe_tags = {c.id: [t.tag_name for t in c.tags] for c in cafes}
    all_ids = set(cafe_tags)

    excluded = known | previous | passed
    if not (all_ids - excluded):
        # 以前抽過的都輪完了：放寬成只排除去過／收藏／沒興趣的
        excluded = known | passed
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

def _keep_until_day(now):
    """拆開的盒子，day_key 早於這天就過期。"""
    return day_key(naive_utc(now) - timedelta(days=OPENED_KEEP_DAYS - 1))


def _expire_old(user_id, today, now):
    stale = BlindBox.query.filter(
        BlindBox.user_id == user_id,
        BlindBox.day_key != today,
        BlindBox.status.in_(('sealed', 'opened')),
    ).all()
    keep_from = _keep_until_day(now)
    for box in stale:
        # 拆開了、還在保留期內：留著等使用者去
        if box.status == 'opened' and box.day_key >= keep_from:
            continue
        box.status = 'expired'
        box.closed_at = now


def _current_box(user_id, dk):
    return (BlindBox.query
            .filter(BlindBox.user_id == user_id, BlindBox.day_key == dk,
                    BlindBox.status != 'skipped')
            .order_by(BlindBox.id.desc()).first())


def _rerolls_used(user_id, dk):
    return BlindBox.query.filter_by(user_id=user_id, day_key=dk, status='skipped').count()


def _new_box(user_id, dk, now, rng=random):
    picked = pick_cafe(user_id, rng)
    if not picked:
        return None
    box = BlindBox(user_id=user_id, day_key=dk, status='sealed', created_at=now, **picked)
    db.session.add(box)
    return box


def get_or_create_current(user_id, rng=random):
    """今天的盒子；還沒有就現抽一盒。過期的順便標成 expired。"""
    now = get_utc_now()
    today = day_key(now)
    _expire_old(user_id, today, now)
    box = _current_box(user_id, today)
    if not box:
        box = _new_box(user_id, today, now, rng)
    db.session.commit()
    return box


def open_box(user_id):
    box = _current_box(user_id, day_key())
    if box and box.status == 'sealed':
        box.status = 'opened'
        box.opened_at = get_utc_now()
        db.session.commit()
    return box


def reroll(user_id, reason, rng=random):
    """換一盒。回傳 (新盒子, 錯誤訊息)。"""
    now = get_utc_now()
    today = day_key(now)
    box = _current_box(user_id, today)
    if not box or box.status not in ('sealed', 'opened'):
        return None, '今天沒有可以換的盒子'
    if _rerolls_used(user_id, today) >= REROLLS_PER_DAY:
        return None, '今天已經換過了，明天會有新的盒子'
    box.status = 'skipped'
    box.closed_at = now
    box.skip_reason = reason if reason in SKIP_REASONS else 'other'
    db.session.flush()
    new_box = _new_box(user_id, today, now, rng)
    db.session.commit()
    return new_box, None


def complete_if_matches(user_id, cafe_id, now):
    """使用者把某家店按成「去過」時呼叫：今天的盒子、或還在保留期內拆開的盒子是這家，就算完成。

    不 commit，跟著呼叫端（passport_service.toggle_shop_state）同一個交易。
    """
    today = day_key(now)
    candidates = (BlindBox.query
                  .filter(BlindBox.user_id == user_id, BlindBox.cafe_id == cafe_id,
                          BlindBox.status.in_(('sealed', 'opened')))
                  .order_by(BlindBox.id.desc()).all())
    keep_from = _keep_until_day(now)
    box = next((b for b in candidates
                if b.day_key == today or (b.status == 'opened' and b.day_key >= keep_from)), None)
    if box:
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
    dk = box.day_key
    data = {
        'id': box.id,
        'status': box.status,
        'day_key': dk,
        'ends_at': _iso(day_end_utc()),
        'rerolls_left': max(0, REROLLS_PER_DAY - _rerolls_used(user_id, dk)),
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
    """過去的盒子。exclude_id 是目前顯示在卡片上的那盒（今天的），不要重複列。

    以前拆開、還在保留期內等使用者去的盒子（status=opened）也列進來，前端標成「待去」。
    """
    rows = (BlindBox.query.filter(BlindBox.user_id == user_id,
                                  BlindBox.id != (exclude_id or -1),
                                  BlindBox.status.in_(('completed', 'expired', 'skipped', 'opened')))
            .order_by(BlindBox.id.desc()).limit(limit).all())
    names = {c.id: c.name for c in Cafes.query.filter(Cafes.id.in_([b.cafe_id for b in rows])).all()} if rows else {}
    return [{
        'id': b.id,
        'day_key': b.day_key,
        'status': b.status,
        'cafe_id': b.cafe_id if b.opened_at else None,
        # 沒拆就放掉的盒子，事後也不公開是哪家 —— 留著懸念
        'cafe_name': names.get(b.cafe_id) if b.opened_at else None,
        'rating': b.rating,
    } for b in rows]
