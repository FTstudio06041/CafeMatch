# -*- coding: utf-8 -*-
"""
cafe_facts.py — 硬條件的資料來源（寵物友善／晚間營業）

為什麼獨立成一個服務：
  硬條件原本比對 GNN/cafes_updated.json 的 review_tags，但那是從評論文字
  抽出來的關鍵詞，不是店家屬性 —— 56 家裡只有 2 家含「寵物」、0 家含「停車」、
  0 家含「夜」。使用者勾了條件等於沒勾，每次都會觸發「符合的不夠多就放寬」。

  資料庫裡的資料好得多：tags 表有 292 種標籤（含「寵物友善」），
  operatinghours 表有真實的營業時間。改從這裡取。

  查詢邏輯放這裡而不是塞進 gnn_recommender，是為了讓後者保持不依賴 Flask／DB
  —— 它要能被 GNN 目錄的離線腳本直接匯入。呼叫端負責把結果餵進去。

沒有資料的條件（目前是「好停車」）不會被悄悄放寬，而是明確回報「無法套用」，
免得使用者以為系統有考慮這個條件。
"""

import threading
import time as _time
from datetime import time as dtime

# 這些標籤代表「可以帶寵物」。tags 表是從評論與店家資訊整理出來的，
# 「貓」「狗」多半是店貓店狗，對想帶寵物的人也算正相關。
PET_TAG_NAMES = ('寵物友善', '寵物', '貓', '狗')

# 「好停車」標籤由 scripts/extract_parking_tag.py 從 24,770 則評論萃取而來
# ——資料庫原本沒有任何停車欄位，但評論裡一直有這個資訊。
# 重跑該腳本可更新名單（例如新增評論之後）。
PARKING_TAG_NAMES = ('好停車',)

# 晚間營業的門檻。實測 20:00 → 12 家、19:00 → 17 家、21:00 → 6 家；
# 取 20:00 是在「真的算晚」與「候選數夠推薦」之間的折衷。
NIGHT_CLOSE_AFTER = dtime(20, 0)

# 有資料可以判斷的條件。三個都有了：
#   pet     tags 表既有的「寵物友善」等標籤
#   night   operatinghours 的實際營業時間
#   parking 從評論萃取出來的「好停車」標籤
SUPPORTED_FILTERS = ('pet', 'night', 'parking')

# 店家的標籤與營業時間很少變動，快取一段時間就好（後台改完最多等這麼久）
_CACHE_TTL_SECONDS = 600

_cache = None
_cache_at = 0.0
_lock = threading.Lock()


def _query_pools():
    from models.cafe import Cafes, Tags, OperatingHours

    def by_tags(names):
        return {c.id for c in
                Cafes.query.join(Cafes.tags).filter(Tags.tag_name.in_(names)).all()}

    pet = by_tags(PET_TAG_NAMES)
    parking = by_tags(PARKING_TAG_NAMES)

    night = set()
    for row in OperatingHours.query.all():
        if row.is_closed or not row.close_time:
            continue
        # 關店時間比開店早 = 營業到隔天凌晨，這種當然算晚間營業
        crosses_midnight = row.open_time and row.close_time < row.open_time
        if crosses_midnight or row.close_time >= NIGHT_CLOSE_AFTER:
            night.add(row.cafe_id)

    return {'pet': pet, 'night': night, 'parking': parking}


def filter_pools(force_refresh: bool = False) -> dict:
    """
    回傳 {'pet': {cafe_id...}, 'night': {...}, 'parking': {...}}。

    查不到資料庫時回傳空字典 —— 呼叫端會當成「沒有可用的硬條件」，
    推薦照常進行，不會因此整個失敗。
    """
    global _cache, _cache_at
    now = _time.monotonic()
    if not force_refresh and _cache is not None and now - _cache_at < _CACHE_TTL_SECONDS:
        return _cache

    with _lock:
        if not force_refresh and _cache is not None and now - _cache_at < _CACHE_TTL_SECONDS:
            return _cache
        try:
            _cache = _query_pools()
            _cache_at = now
        except Exception:                                        # noqa: BLE001
            import logging
            logging.warning('[cafe_facts] 讀取硬條件資料失敗，這次推薦不套用硬條件',
                            exc_info=True)
            return {}
    return _cache


def unsupported(hard_filters: dict) -> list:
    """使用者提了、但系統沒有資料可以判斷的條件（例如「好停車」）。"""
    return [flag for flag, wanted in (hard_filters or {}).items()
            if wanted and flag not in SUPPORTED_FILTERS]
