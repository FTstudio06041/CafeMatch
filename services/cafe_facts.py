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


# ==========================================
# 需求可行性檢查
# ==========================================
#
# 使用者講得出口的條件，遠多於系統認得的條件。「水菸」「包廂」「不限時」
# 這類需求既不在 tags 表、也不在五維加分表裡，於是一路靜靜穿過整條管線：
# 硬過濾不認得它、GNN 標籤比對拿不到分、放寬機制再把候選補滿，
# 最後推出來的就是一批與該需求無關的熱門店。
#
# 這裡把每個條件分成三類，讓上層知道哪些需求真的有資料撐著：
#   verifiable  資料查得到（tags 表的標籤，或 pet/night/parking 的合格名單）
#   soft        系統認得、但只能影響排序（五維加分詞、引導設定檔的偵測關鍵字）
#   uncovered   三者皆無 —— 系統對這個需求毫無資料，不能假裝考慮過
#
# 單字標籤（「香」「杯」「烤」）不參與「條件包含標籤」方向的比對：
# 292 個標籤裡有不少這種評論碎片，放進去幾乎任何句子都會誤判成可驗證。

_MIN_TAG_LEN_FOR_SUBSTRING = 2

# 標籤要佔條件的一半以上，才算「這個條件講的就是這個標籤」。
# 「無麩質甜點」含有標籤「甜點」，但關鍵需求是「無麩質」——
# 用 2/5 的重疊就宣告可驗證，等於拿甜點店去回答無麩質的問題。
_MIN_TAG_COVERAGE = 0.5

_vocab_cache = None
_vocab_at = 0.0


def _query_vocabulary():
    from models.cafe import Cafes

    counts = {}
    total = 0
    for cafe in Cafes.query.all():
        total += 1
        for tag in cafe.tags:
            counts[tag.tag_name] = counts.get(tag.tag_name, 0) + 1
    return {'tags': counts, 'total_cafes': total}


def tag_vocabulary(force_refresh: bool = False) -> dict:
    """
    回傳 {'tags': {標籤名: 幾家店有}, 'total_cafes': 店家總數}。

    查不到資料庫時回傳空詞彙表 —— 呼叫端會因此判不出 uncovered，
    寧可少報也不要誤報「我們沒有這個」。
    """
    global _vocab_cache, _vocab_at
    now = _time.monotonic()
    if not force_refresh and _vocab_cache is not None and now - _vocab_at < _CACHE_TTL_SECONDS:
        return _vocab_cache

    with _lock:
        if not force_refresh and _vocab_cache is not None and now - _vocab_at < _CACHE_TTL_SECONDS:
            return _vocab_cache
        try:
            _vocab_cache = _query_vocabulary()
            _vocab_at = now
        except Exception:                                        # noqa: BLE001
            import logging
            logging.warning('[cafe_facts] 讀取標籤詞彙表失敗，這次不做可行性檢查',
                            exc_info=True)
            return {'tags': {}, 'total_cafes': 0}
    return _vocab_cache


def _soft_vocabulary():
    """
    只能影響排序、但系統確實有在處理的詞 —— 就是五維加分表。

    這裡刻意不收 guide_dimensions.json 的 detect_keywords：那份名單代表
    「我聽得懂這個詞、知道它屬於哪個維度」，不代表推薦時使得上力。
    「包廂」正是這種詞 —— 引導設定檔認得它，但標籤表沒有、硬條件也沒有，
    推薦時它一點作用都起不了。把它算成 soft 就等於把這道檢查關掉，
    使用者又會拿到一批沒有包廂的店而完全不知情。
    """
    from services.preference_adjuster import _KEYWORD_BOOSTS

    return set(_KEYWORD_BOOSTS)


def _match_tag(text, tags):
    """
    條件對上了哪個標籤。回傳 (標籤名, 幾家店) 或 None。

    兩個方向都算命中，但門檻不同：
      標籤包含條件  「寵物」→「寵物友善」    條件本身要有兩個字以上
      條件包含標籤  「想吃肉桂捲」→「肉桂捲」 標籤要有兩個字以上（擋掉單字碎片）
    對上多個時取涵蓋店家最多的，那是最有代表性的說法。
    """
    hits = []
    for tag_name, count in tags.items():
        if len(text) >= _MIN_TAG_LEN_FOR_SUBSTRING and text in tag_name:
            hits.append((tag_name, count))
        elif (len(tag_name) >= _MIN_TAG_LEN_FOR_SUBSTRING and tag_name in text
                and len(tag_name) >= len(text) * _MIN_TAG_COVERAGE):
            hits.append((tag_name, count))
    if not hits:
        return None
    return max(hits, key=lambda h: h[1])


def classify_conditions(preferences: dict | None) -> dict:
    """
    核對使用者的每個條件，判斷資料庫到底有沒有東西可以支撐它。

    參數:
        preferences: {dim: [條件字串]}（preference_service 萃取的結果）

    回傳:
        {
          'verifiable': [{'text', 'evidence', 'count'}],   # 查得到資料
          'soft':       ['安靜', ...],                      # 只能影響排序
          'uncovered':  ['有水菸', ...],                    # 完全沒有資料
          'total_cafes': 56,
        }

    否定條件（「不要吵」）與「不限」不列入 —— 它們不是要系統去滿足的東西。
    詞彙表讀不到時一律回空結果，寧可不報也不要誤報。
    """
    from services.preference_service import is_negative_preference
    from services.preference_adjuster import _HARD_FILTER_KEYWORDS

    result = {'verifiable': [], 'soft': [], 'uncovered': [], 'total_cafes': 0}

    vocab = tag_vocabulary()
    tags = vocab.get('tags') or {}
    result['total_cafes'] = vocab.get('total_cafes') or 0
    if not tags:
        return result

    pools = filter_pools()
    soft_words = _soft_vocabulary()
    seen = set()

    for values in (preferences or {}).values():
        if not isinstance(values, list):
            continue
        for text in values:
            if not isinstance(text, str):
                continue
            text = text.strip()
            if not text or text == '不限' or text in seen:
                continue
            if is_negative_preference(text):
                continue
            seen.add(text)

            # 1) 硬條件：有合格名單才算數。名單是空的（例如「好停車」標籤
            #    還沒被 scripts/extract_parking_tag.py 寫進資料庫）代表
            #    系統其實判斷不了，那是 uncovered，不是可驗證。
            flag = next((f for f, signals in _HARD_FILTER_KEYWORDS.items()
                         if any(sig in text for sig in signals)), None)
            if flag:
                pool = pools.get(flag) or set()
                if pool:
                    result['verifiable'].append(
                        {'text': text, 'evidence': flag, 'count': len(pool)})
                else:
                    result['uncovered'].append(text)
                continue

            # 2) 標籤表查得到
            hit = _match_tag(text, tags)
            if hit:
                result['verifiable'].append(
                    {'text': text, 'evidence': hit[0], 'count': hit[1]})
                continue

            # 3) 系統認得，但只能影響排序
            if any(word in text for word in soft_words):
                result['soft'].append(text)
                continue

            # 4) 帶數字的條件講的多半是價格、時間或距離 —— cafes.cost 與
            #    operatinghours 都有資料，檢索時也真的會用到。實測「低於500」
            #    三層詞彙表全不中，差點就對使用者宣告「沒有任何一家符合」，
            #    而 500 元以下的店其實一大堆。這種條件一律不報。
            if any(ch.isdigit() for ch in text):
                result['soft'].append(text)
                continue

            # 5) 完全沒有資料
            result['uncovered'].append(text)

    return result
