"""咖啡護照：蓋章、徽章與收藏／去過的流水帳。

徽章不另開資料表，每次從「去過哪些店、什麼時候去的」即時算出來：
  - 規則改了（data/passport_badges.json）不用回填資料
  - 取消「去過」，徽章就跟著收回，不會有對不上的狀態
  - 解鎖日期 = 剛好達標的那一章的蓋章日期，一樣算得出來

規則的判斷集中在 evaluate_badges()，是不碰資料庫的純函式，方便單元測試。
"""

import json
import math
import os
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import selectinload

from config.settings import get_utc_now
from database import db
from models import BlindBox, Cafes, ShopStateEvent, UserShopState
from services.google_maps_service import get_cafe_image_url

BADGES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'passport_badges.json')

# 收藏／去過是從哪個畫面按的。不在白名單的一律記成 unknown，不信任前端亂帶。
VALID_SOURCES = {'explore', 'chat', 'blindbox', 'passport'}

TAIPEI = timezone(timedelta(hours=8))

_badges_cache = None
_badges_lock = threading.Lock()


# ==========================================
# 時間工具
# ==========================================

def naive_utc(dt):
    """統一成「不帶時區的 UTC」。

    get_utc_now() 給的是帶時區的時間，但 MySQL／SQLite 讀回來是不帶時區的，
    兩種混在一起比大小會直接 TypeError。
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def week_key(dt=None):
    """台灣時間的 ISO 週次，例如 2026-W46。週一 00:00 換週。"""
    dt = naive_utc(dt or get_utc_now())
    local = dt.replace(tzinfo=timezone.utc).astimezone(TAIPEI)
    year, week, _ = local.isocalendar()
    return f'{year}-W{week:02d}'


def week_end_utc(dt=None):
    """這週結束（下週一 00:00 台灣時間）換算成 UTC，給前端倒數用。"""
    dt = naive_utc(dt or get_utc_now())
    local = dt.replace(tzinfo=timezone.utc).astimezone(TAIPEI)
    monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return naive_utc(monday + timedelta(days=7))


def _iso(dt):
    dt = naive_utc(dt)
    return dt.isoformat() + 'Z' if dt else None


def area_of(address):
    """從地址抓出鄉鎮市，例如「970花蓮縣花蓮市軒轅路15號」→「花蓮市」。"""
    if not address:
        return ''
    text = address.lstrip('0123456789 ')
    for county_end in ('縣', '市'):
        i = text.find(county_end)
        if 0 <= i <= 3:
            rest = text[i + 1:]
            for suffix in ('市', '鄉', '鎮', '區'):
                j = rest.find(suffix)
                if 0 < j <= 3:
                    return rest[:j + 1]
            break
    return ''


# ==========================================
# 徽章規則
# ==========================================

def load_badge_defs():
    global _badges_cache
    if _badges_cache is None:
        with _badges_lock:
            if _badges_cache is None:
                with open(BADGES_PATH, encoding='utf-8') as f:
                    _badges_cache = json.load(f)['badges']
    return _badges_cache


def _sort_key(dt):
    # 沒有日期的舊紀錄排最前面：它們一定比加上欄位之後的紀錄早
    return (dt is not None, dt or datetime.min)


def _streak_progress(dates, target):
    """連續幾週都有去新店。回傳 (最長連續週數, 達標當週第一筆的日期)。"""
    weeks = []
    for d in sorted(d for d in dates if d is not None):
        local = d.replace(tzinfo=timezone.utc).astimezone(TAIPEI)
        monday = (local - timedelta(days=local.weekday())).date()
        if not weeks or weeks[-1][0] != monday:
            weeks.append((monday, d))

    best, run, unlocked_at = 0, 0, None
    prev = None
    for monday, first_dt in weeks:
        run = run + 1 if prev is not None and (monday - prev).days == 7 else 1
        prev = monday
        if run > best:
            best = run
        if unlocked_at is None and run >= target:
            unlocked_at = first_dt
    return best, unlocked_at


def evaluate_badges(stamps, total_cafes, blindbox_done_dates, defs=None):
    """算出每個徽章的進度與是否解鎖。

    stamps:              [{'visited_at': datetime|None, 'tags': [str], 'cost': str, 'address': str}]
    total_cafes:         收錄的店家總數（visit_ratio 用）
    blindbox_done_dates: 完成的盲盒的 completed_at 清單

    回傳 [{id, name, icon, desc, unlocked, unlocked_at, progress, target}]
    """
    defs = defs if defs is not None else load_badge_defs()
    ordered = sorted(stamps, key=lambda s: _sort_key(s.get('visited_at')))
    results = []

    for badge in defs:
        rule = badge['rule']
        kind = rule['type']
        unlocked_at = None

        if kind == 'week_streak':
            target = int(rule['count'])
            progress, unlocked_at = _streak_progress([s.get('visited_at') for s in ordered], target)
            unlocked = unlocked_at is not None
        else:
            if kind == 'visit_count':
                target = int(rule['count'])
                dates = [s.get('visited_at') for s in ordered]
            elif kind == 'visit_ratio':
                target = max(1, math.ceil(float(rule['ratio']) * total_cafes))
                dates = [s.get('visited_at') for s in ordered]
            elif kind == 'tag_count':
                target = int(rule['count'])
                keywords = rule.get('keywords', [])
                dates = [s.get('visited_at') for s in ordered
                         if any(k in tag for tag in s.get('tags', []) for k in keywords)]
            elif kind == 'cost_count':
                target = int(rule['count'])
                dates = [s.get('visited_at') for s in ordered if (s.get('cost') or '') == rule['cost']]
            elif kind == 'area_excludes':
                target = int(rule['count'])
                dates = [s.get('visited_at') for s in ordered
                         if s.get('address') and rule['text'] not in s['address']]
            elif kind == 'blindbox_count':
                target = int(rule['count'])
                dates = sorted(blindbox_done_dates, key=_sort_key)
            else:
                continue  # 不認得的規則種類：直接略過，不要讓整個護照壞掉

            progress = len(dates)
            unlocked = progress >= target
            if unlocked:
                unlocked_at = dates[target - 1]

        results.append({
            'id': badge['id'],
            'name': badge['name'],
            'icon': badge.get('icon', 'Award'),
            'desc': badge.get('desc', ''),
            'unlocked': unlocked,
            'unlocked_at': _iso(unlocked_at),
            'progress': min(progress, target),
            'target': target,
        })
    return results


# ==========================================
# 資料存取
# ==========================================

def _visited_stamps(user_id):
    rows = (db.session.query(UserShopState, Cafes)
            .join(Cafes, Cafes.id == UserShopState.cafe_id)
            .options(selectinload(Cafes.tags))
            .filter(UserShopState.user_id == user_id, UserShopState.is_visited.is_(True))
            .all())
    return [{
        'cafe_id': cafe.id,
        'visited_at': naive_utc(state.visited_at),
        'tags': [t.tag_name for t in cafe.tags],
        'cost': cafe.cost or '',
        'address': cafe.address or '',
    } for state, cafe in rows]


def _blindbox_done_dates(user_id):
    rows = BlindBox.query.filter_by(user_id=user_id, status='completed').all()
    return [naive_utc(b.completed_at) for b in rows]


def compute_badges(user_id):
    total = Cafes.query.count()
    return evaluate_badges(_visited_stamps(user_id), total, _blindbox_done_dates(user_id))


def _unlocked_ids(user_id):
    return {b['id'] for b in compute_badges(user_id) if b['unlocked']}


def toggle_shop_state(user, cafe_id, action_type, source):
    """切換收藏／去過，記一筆流水帳，並回報這次新解鎖的徽章。

    回傳 dict；cafe 不存在時回傳 None。
    """
    from services import blindbox_service  # 避免循環匯入

    if not db.session.get(Cafes, cafe_id):
        return None
    source = source if source in VALID_SOURCES else 'unknown'
    now = get_utc_now()
    before = _unlocked_ids(user.id)

    state = UserShopState.query.filter_by(user_id=user.id, cafe_id=cafe_id).first()
    if not state:
        state = UserShopState(user_id=user.id, cafe_id=cafe_id, is_fav=False, is_visited=False)
        db.session.add(state)

    completed_box = None
    if action_type == 'fav':
        state.is_fav = not state.is_fav
        state.fav_at = now if state.is_fav else None
        action = 'fav' if state.is_fav else 'unfav'
    else:
        state.is_visited = not state.is_visited
        state.visited_at = now if state.is_visited else None
        action = 'visit' if state.is_visited else 'unvisit'
        if state.is_visited:
            completed_box = blindbox_service.complete_if_matches(user.id, cafe_id, now)

    db.session.add(ShopStateEvent(user_id=user.id, cafe_id=cafe_id, action=action,
                                  source=source, created_at=now))
    db.session.commit()

    after = compute_badges(user.id)
    new_badges = [b for b in after if b['unlocked'] and b['id'] not in before]
    return {
        'fav': bool(state.is_fav),
        'visited': bool(state.is_visited),
        'new_badges': new_badges,
        'blindbox_completed': completed_box is not None,
    }


def get_shop_states(user_id):
    """{cafe_id: {fav, visited}}，給聊天推薦卡片顯示按鈕狀態用。"""
    rows = UserShopState.query.filter_by(user_id=user_id).all()
    return {r.cafe_id: {'fav': bool(r.is_fav), 'visited': bool(r.is_visited)}
            for r in rows if r.is_fav or r.is_visited}


def get_passport(user):
    """護照頁需要的全部資料：集章冊、徽章牆、統計。"""
    cafes = Cafes.query.options(selectinload(Cafes.tags)).order_by(Cafes.id).all()
    states = {s.cafe_id: s for s in UserShopState.query.filter_by(user_id=user.id).all()}
    box_cafes = {b.cafe_id for b in BlindBox.query.filter_by(user_id=user.id, status='completed').all()}

    book = []
    for cafe in cafes:
        st = states.get(cafe.id)
        stamped = bool(st and st.is_visited)
        book.append({
            'cafe_id': cafe.id,
            'name': cafe.name,
            'image_url': get_cafe_image_url(cafe),
            'area': area_of(cafe.address),
            'tags': [t.tag_name for t in cafe.tags[:3]],
            'stamped': stamped,
            'visited_at': _iso(st.visited_at) if stamped else None,
            'via_blindbox': stamped and cafe.id in box_cafes,
        })

    badges = compute_badges(user.id)
    stamped_count = sum(1 for b in book if b['stamped'])
    return {
        'total_cafes': len(book),
        'stamp_count': stamped_count,
        'badge_count': sum(1 for b in badges if b['unlocked']),
        'badge_total': len(badges),
        'book': book,
        'badges': badges,
    }
