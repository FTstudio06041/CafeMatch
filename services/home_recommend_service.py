"""
home_recommend_service.py — 首頁「你可能會喜歡」

  有心理測驗五維分數 → GNN 個人化推薦（gnn_recommender.recommend_by_scores）
  沒有分數、或 GNN 不可用 → 熱門店家（Google 評價的貝氏平均）

GNN 每次會分層隨機抽樣，直接用的話首頁一重新整理整排就換掉，
點進一家店再回來卻找不到它。所以同一組分數的結果快取半天。

熱門的排序用貝氏平均：評論只有幾十則的 4.9 分，不該贏過上千則的 4.7 分。
前段名單每天輪替一次順序，讓沒做測驗的人每天看到的也有點變化。
"""

import logging
import random
from datetime import date

from services.cache_service import cache
from services.cafe_explore_service import google_review_stats

DIMS = ('work', 'env', 'social', 'taste', 'cp')
DEFAULT_LIMIT = 8
PERSONAL_CACHE_TTL = 6 * 3600
# 貝氏平均的先驗強度：相當於每家店先灌這麼多則「全體平均分」的評論
BAYES_PRIOR_COUNT = 100
# 熱門名單取前幾名來做每日輪替（太大會把普通的店輪進來）
POPULAR_POOL = 16


def parse_scores(raw):
    """
    驗證並正規化五維分數。五個維度都要是 0~100 的數字，否則回傳 None。
    （測驗分數實際落在 0~20 左右，上限放寬是為了不綁死計分方式。）
    """
    if not isinstance(raw, dict):
        return None
    scores = {}
    for dim in DIMS:
        try:
            value = float(raw.get(dim))
        except (TypeError, ValueError):
            return None
        if not 0 <= value <= 100:
            return None
        scores[dim] = value
    if not any(scores.values()):
        return None
    return scores


def popular_cafe_ids(cafe_ids, limit=DEFAULT_LIMIT, today=None):
    stats = google_review_stats()
    rated = {cid: stats[cid] for cid in cafe_ids if cid in stats}
    if not rated:
        # 沒有評論資料（例如測試資料庫）：維持 id 順序
        return list(cafe_ids)[:limit]

    total = sum(avg * cnt for avg, cnt in rated.values())
    count = sum(cnt for _, cnt in rated.values())
    prior = total / count

    def bayes(cid):
        avg, cnt = rated[cid]
        return (avg * cnt + prior * BAYES_PRIOR_COUNT) / (cnt + BAYES_PRIOR_COUNT)

    ranked = sorted(rated, key=bayes, reverse=True)
    unrated = [cid for cid in cafe_ids if cid not in rated]
    pool = ranked[:POPULAR_POOL]
    rng = random.Random((today or date.today()).toordinal())
    rng.shuffle(pool)
    return (pool + ranked[POPULAR_POOL:] + unrated)[:limit]


def _gnn_cafe_ids(scores, valid_ids):
    """GNN 推薦的店家 id（依推薦順序）；GNN 不可用時回傳空串列。"""
    key = 'home_gnn:' + ','.join(f'{scores[d]:g}' for d in DIMS)
    hit = cache.get(key)
    if hit is not None:
        return [cid for cid in hit if cid in valid_ids]

    try:
        from services import cafe_facts, gnn_recommender
        ranked = gnn_recommender.recommend_by_scores(scores, filter_pools=cafe_facts.filter_pools())
    except Exception as e:  # GnnUnavailable、torch 沒裝、模型檔缺失……都退回熱門
        logging.warning(f'首頁 GNN 推薦不可用，改用熱門店家：{e}')
        return []

    ids = [int(r['cafe_id']) for r in ranked if r.get('cafe_id') is not None]
    cache.set(key, ids, ttl=PERSONAL_CACHE_TTL)
    return [cid for cid in ids if cid in valid_ids]


def recommend_for_home(cafe_ids, scores=None, limit=DEFAULT_LIMIT):
    """
    回傳 {'basis': 'quiz' | 'popular', 'items': [{'cafe_id', 'reason'}]}。
    reason：'quiz' = 依測驗結果、'popular' = 熱門。GNN 不夠填滿時用熱門補。
    """
    valid = set(cafe_ids)
    items = []
    if scores:
        items = [{'cafe_id': cid, 'reason': 'quiz'} for cid in _gnn_cafe_ids(scores, valid)]

    taken = {i['cafe_id'] for i in items}
    for cid in popular_cafe_ids([c for c in cafe_ids if c not in taken], limit=limit):
        if len(items) >= limit:
            break
        items.append({'cafe_id': cid, 'reason': 'popular'})

    basis = 'quiz' if any(i['reason'] == 'quiz' for i in items) else 'popular'
    return {'basis': basis, 'items': items[:limit]}
