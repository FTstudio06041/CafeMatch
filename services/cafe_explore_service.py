import logging
from datetime import timedelta
from urllib.parse import quote

from sqlalchemy import func, text

from config.settings import get_utc_now
from database import db
from models import Cafes, UserShopState, CommunityPost, CommunityNote
from services.cache_service import cached
from services.cafe_hours import today_summary, weekly_hours
from services.google_maps_service import get_cafe_image_url, has_google_maps_key

# 卡片底色（照片載入前或沒有照片時的色塊）
PALETTE = [
    "#8D6E63", "#A1887F", "#BCAAA4", "#D7CCC8",
    "#795548", "#6D4C41", "#5D4037", "#4E342E",
    "#78909C", "#607D8B", "#546E7A"
]

REPORT_TTL = timedelta(hours=24)


@cached(prefix="google_review_stats", ttl=3600)
def google_review_stats():
    """
    舊 reviews 表（爬下來的 Google 評論，約 2.5 萬則）的每店平均星等與則數。

    這張表不在 models 裡（它是 GNN 訓練資料的來源，不歸 ORM 管），
    所以用原生 SQL 查；測試用的 SQLite 沒有這張表，查不到就回傳空的。
    評論不會即時增加，快取一小時。
    """
    try:
        rows = db.session.execute(text(
            'SELECT cafe_id, AVG(score), COUNT(*) FROM reviews GROUP BY cafe_id'
        )).fetchall()
    except Exception as e:
        db.session.rollback()
        logging.info(f'Google 評論統計不可用（{e.__class__.__name__}），略過')
        return {}
    return {int(cid): (round(float(avg), 1), int(cnt)) for cid, avg, cnt in rows if cid is not None}


def platform_review_stats():
    """本站使用者評論（community_posts 有星等的那些）的每店平均與則數。"""
    rows = db.session.query(
        CommunityPost.cafe_id, func.avg(CommunityPost.rating), func.count(CommunityPost.id)
    ).filter(
        CommunityPost.cafe_id.isnot(None), CommunityPost.rating.isnot(None)
    ).group_by(CommunityPost.cafe_id).all()
    return {cid: (round(float(avg), 1), int(cnt)) for cid, avg, cnt in rows}


def recent_report_counts():
    """每店 24 小時內的現況回報數，讓地圖與卡片標出「有人剛回報」。"""
    since = get_utc_now() - REPORT_TTL
    rows = db.session.query(CommunityNote.cafe_id, func.count(CommunityNote.id)).filter(
        CommunityNote.cafe_id.isnot(None), CommunityNote.created_at >= since
    ).group_by(CommunityNote.cafe_id).all()
    return {cid: int(cnt) for cid, cnt in rows}


def google_maps_link(cafe):
    """
    Google Maps 連結。cafe.url 存的是短碼、直接拼網址會導向空白頁，
    改用官方的搜尋網址格式；有 place_id 時一併帶上，能精準定位到那家店。
    """
    query = ' '.join(p for p in (cafe.name, cafe.address) if p)
    if not query:
        return ''
    link = f'https://www.google.com/maps/search/?api=1&query={quote(query)}'
    if cafe.google_place_id:
        link += f'&query_place_id={quote(cafe.google_place_id)}'
    return link


def serialize_cafe(cafe, *, user_state=None, google_stats=None, platform_stats=None, report_count=0):
    tag_names = [t.tag_name for t in cafe.tags]
    hours_rows = list(cafe.hours or [])
    today = today_summary(hours_rows)
    g_avg, g_cnt = google_stats or (None, 0)
    p_avg, p_cnt = platform_stats or (None, 0)
    state = user_state or {'fav': False, 'visited': False}

    return {
        "id": cafe.id,
        "name": cafe.name,
        # 舊欄位（字串形式的標籤）保留給還在用的地方，新前端用 tag_list
        "tags": " ".join(f"#{t}" for t in tag_names) if tag_names else "#無標籤",
        "tag_list": tag_names,
        "cost": cafe.cost or "",
        "hours": today['today_hours'] or "營業時間請洽店家",
        "today_hours": today['today_hours'],
        "is_open_now": today['is_open_now'],
        "weekly_hours": weekly_hours(hours_rows),
        "phone": cafe.phone or "",
        "address": cafe.address or "",
        "website": cafe.website or "",
        "lat": cafe.lat,
        "lng": cafe.lng,
        "color": PALETTE[cafe.id % len(PALETTE)],
        "image": cafe.image or "",
        "image_url": get_cafe_image_url(cafe),
        "image_source": "manual" if cafe.image else ("google" if has_google_maps_key() else ""),
        "image_attribution": cafe.google_photo_attribution or "",
        "map_url": google_maps_link(cafe),
        "google_rating": g_avg,
        "google_review_count": g_cnt,
        "rating": p_avg,
        "review_count": p_cnt,
        "report_count": report_count,
        "is_fav": bool(state['fav']),
        "is_visited": bool(state['visited']),
    }


def get_cafes_data(current_user):
    all_cafes = Cafes.query.order_by(Cafes.id).all()

    user_states = {}
    if current_user:
        for s in UserShopState.query.filter_by(user_id=current_user.id).all():
            user_states[s.cafe_id] = {'fav': s.is_fav, 'visited': s.is_visited}

    g_stats = google_review_stats()
    p_stats = platform_review_stats()
    reports = recent_report_counts()

    return [
        serialize_cafe(
            cafe,
            user_state=user_states.get(cafe.id),
            google_stats=g_stats.get(cafe.id),
            platform_stats=p_stats.get(cafe.id),
            report_count=reports.get(cafe.id, 0),
        )
        for cafe in all_cafes
    ]
