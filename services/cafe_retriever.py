# services/cafe_retriever.py
import logging
import re
from datetime import time as _time
from sqlalchemy import or_
from config.ai_constants import CAFE_TAG_MATCH_LIMIT, CAFE_NAME_MATCH_LIMIT, CAFE_TAGS_DISPLAY_LIMIT

DAY_NAMES = ['', '一', '二', '三', '四', '五', '六', '日']


def retrieve_cafe_data(matched_keywords, Cafes, Tags, *,
                       tag_weights=None, hours_window=None, cost_range=None):
    """
    選出相關咖啡廳並回傳「cafe 物件清單」（供文字上下文與結構化卡片共用）。

    兩種模式（由是否帶入 tag_weights / hours_window / cost_range 決定）：
      1. 關鍵字模式（預設，自由聊天用）：tag / 名稱 / 地址 OR 子字串比對。
      2. 加權情境模式（chat 情境元件用）：先以營業時間、價位硬過濾，再依標籤權重評分。
    """
    try:
        use_weighted = bool(tag_weights) or bool(hours_window) or bool(cost_range)
        if use_weighted:
            return _weighted_retrieve(Cafes, tag_weights or [], hours_window, cost_range)
        return _keyword_retrieve(matched_keywords, Cafes, Tags)
    except Exception as e:
        logging.error(f"RAG 查詢失敗: {e}")
        return []


def retrieve_cafe_context(matched_keywords, Cafes, Tags, *,
                          tag_weights=None, hours_window=None, cost_range=None):
    """相容舊介面：回傳可注入 Prompt 的文字上下文。"""
    cafes = retrieve_cafe_data(
        matched_keywords, Cafes, Tags,
        tag_weights=tag_weights, hours_window=hours_window, cost_range=cost_range
    )
    return format_cafe_context(cafes)


def format_cafe_context(cafes):
    """把 cafe 物件清單組成文字上下文（給 LLM 參考）。"""
    lines = _format_cafe_lines(cafes)
    return "\n".join(lines) if lines else ""


def serialize_cafe(cafe):
    """把 cafe 物件序列化成前端卡片用的結構（圖片、資訊）。"""
    return {
        "id": cafe.id,
        "name": cafe.name,
        "image": cafe.image or None,
        "address": cafe.address or None,
        "cost": cafe.cost or None,
        "url": cafe.url or None,
        "website": cafe.website or None,
        "tags": [t.tag_name for t in cafe.tags[:CAFE_TAGS_DISPLAY_LIMIT]],
        "hours": _hours_string(cafe),
    }


# ==========================================
# 檢索策略
# ==========================================

def _keyword_retrieve(matched_keywords, Cafes, Tags):
    """舊有行為：關鍵字對 tag / 名稱 / 地址做 OR 子字串比對，最多取 5 家。"""
    tag_filters = []
    name_filters = []
    for kw in matched_keywords or []:
        tag_filters.append(Tags.tag_name.contains(kw))
        name_filters.append(Cafes.name.contains(kw))
        name_filters.append(Cafes.address.contains(kw))

    tagged_cafes = Cafes.query.join(Cafes.tags).filter(
        or_(*tag_filters)
    ).distinct().limit(CAFE_TAG_MATCH_LIMIT).all() if tag_filters else []

    name_cafes = Cafes.query.filter(
        or_(*name_filters)
    ).limit(CAFE_NAME_MATCH_LIMIT).all() if name_filters else []

    seen_ids = set()
    relevant = []
    for cafe in tagged_cafes + name_cafes:
        if cafe.id not in seen_ids and len(relevant) < 5:
            seen_ids.add(cafe.id)
            relevant.append(cafe)

    if not relevant:
        relevant = Cafes.query.order_by(Cafes.num.desc()).limit(CAFE_TAG_MATCH_LIMIT).all()
    return relevant


def _weighted_retrieve(Cafes, tag_weights, hours_window, cost_range, limit=5):
    """
    情境模式：店家數量少（約 50 家），全部載入後在記憶體中做硬過濾 + 加權評分。
    硬過濾若導致候選全空，會自動放寬該條件（寧可推薦、不要開天窗）。
    """
    candidates = Cafes.query.all()

    if hours_window:
        filtered = [c for c in candidates if _open_during(c, hours_window)]
        if filtered:
            candidates = filtered

    if cost_range:
        filtered = [c for c in candidates if _cost_matches(c.cost, cost_range)]
        if filtered:
            candidates = filtered

    scored = []
    for cafe in candidates:
        cafe_tag_names = [t.tag_name for t in cafe.tags]
        score = 0
        for tw in tag_weights:
            tag = tw.get("tag")
            weight = tw.get("weight", 1)
            if tag and any((tag in tn) or (tn in tag) for tn in cafe_tag_names):
                score += weight
        scored.append((score, cafe.num or 0, cafe))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [c for _, _, c in scored[:limit]]


# ==========================================
# 硬過濾輔助
# ==========================================

def _open_during(cafe, window):
    """cafe 在指定時間窗內是否有營業（不分星期，任一天符合即算）。無營業資訊 → 保留。"""
    wstart = _parse_hhmm(window.get("start"))
    wend = _parse_hhmm(window.get("end"))
    if not wstart or not wend:
        return True

    saw_hours = False
    for h in cafe.hours:
        if h.is_closed:
            continue
        if not h.open_time or not h.close_time:
            continue
        saw_hours = True
        if _time_overlaps(h.open_time, h.close_time, wstart, wend):
            return True
    return not saw_hours


def _time_overlaps(open_t, close_t, wstart, wend):
    if close_t > open_t:
        return open_t < wend and close_t > wstart
    # 跨午夜（如 18:00-02:00）：視為 open_t..24:00 及 00:00..close_t 兩段
    return (open_t < wend) or (close_t > wstart)


def _cost_matches(cost_str, cost_range):
    """cafe 最低消費是否在預算上限內；無法解析 cost → 保留（保守不排除）。"""
    parsed = _parse_cost(cost_str)
    if not parsed:
        return True
    cmin, _cmax = parsed
    dmax = cost_range.get("max")
    if dmax is not None and cmin > dmax:
        return False
    return True


def _parse_cost(cost_str):
    """從 '60-150'、'100'、'約120' 這類字串抽出 (最低, 最高)。抽不到 → None。"""
    if not cost_str:
        return None
    nums = [int(n) for n in re.findall(r'\d+', cost_str)]
    if not nums:
        return None
    return (min(nums), max(nums))


def _parse_hhmm(s):
    try:
        hh, mm = s.split(':')
        return _time(int(hh), int(mm))
    except (ValueError, AttributeError):
        return None


# ==========================================
# 上下文組裝
# ==========================================

def _hours_string(cafe):
    parts = []
    for h in sorted(cafe.hours, key=lambda x: x.day_of_week or 0):
        dname = DAY_NAMES[h.day_of_week] if h.day_of_week and 1 <= h.day_of_week <= 7 else '?'
        if h.is_closed:
            parts.append(f"週{dname}:公休")
        elif h.open_time and h.close_time:
            parts.append(f"週{dname}:{h.open_time.strftime('%H:%M')}-{h.close_time.strftime('%H:%M')}")
    return '、'.join(parts) if parts else '未提供'


def _format_cafe_lines(cafes):
    lines = []
    for cafe in cafes:
        tags_str = ', '.join([t.tag_name for t in cafe.tags[:CAFE_TAGS_DISPLAY_LIMIT]])
        lines.append(
            f"- {cafe.name} | 地址：{cafe.address or '未提供'} | 消費：{cafe.cost or '未提供'} | "
            f"標籤：{tags_str or '無'} | 營業：{_hours_string(cafe)}"
        )
    return lines
