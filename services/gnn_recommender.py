"""
gnn_recommender.py — GNN 推薦接口（後半段）

載入 GNN/ 目錄的訓練產物（HGT + quiz_projector），提供：
    recommend_by_scores(五維分數, hard_filters) → [{'cafe_id', 'gnn_score', ...}]

推薦路徑（與 GNN/new_step5_recommend.py 的新用戶路徑一致）：
    五維分數 → quiz_projector(5→384) → user_proj(384→128)
             → 與 HGT 卷積後的 cafe embedding 配對 → predictor 打分
             → 分層抽樣（精選 ≥4.7 抽 3、優質 4.0~4.7 抽 2）

設計：
  - 模型與圖只載入一次（module-level cache + lock），cafe embedding 預先算好
  - torch 未安裝或檔案缺失時拋 GnnUnavailable，呼叫端回退關鍵字檢索
"""

import os
import json
import logging
import random
import threading

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

GNN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'GNN')

DIMS = ["work", "env", "social", "taste", "cp"]
HIDDEN_DIM = 128
NUM_HEADS = 4
NUM_LAYERS = 2

# 分層抽樣參數（與 GNN/new_step5_recommend.py 一致）
TIER1_THRESHOLD = 4.7
TIER2_MIN = 4.0
TIER1_POOL_SIZE = 8
TIER2_POOL_SIZE = 6
TIER1_PICK = 3
TIER2_PICK = 2

# 標籤匹配在最終排序的權重（0 = 純 GNN、1 = 純標籤匹配）
TAG_BLEND_WEIGHT = 0.4
# 有明確偏好時，保證最匹配的前幾家一定入選（其餘名額仍隨機，維持變化性）
GUARANTEED_TOP_MATCHES = 2
# GNN 分數正規化的最小跨距，避免微小差異被放大成決定性差距
MIN_GNN_SPAN = 0.15

# 硬過濾條件 → review_tags 關鍵字
_HARD_FILTER_TAGS = {
    'pet': ('寵物',),
    'parking': ('停車',),
    'night': ('深夜', '晚', '夜'),
}


class GnnUnavailable(Exception):
    """GNN 推薦不可用（缺套件／缺檔案／載入失敗），呼叫端應回退關鍵字檢索。"""


_state = None
_load_lock = threading.Lock()


def _load():
    """載入模型與資料（只執行一次），回傳快取狀態。"""
    global _state
    if _state is not None:
        return _state
    with _load_lock:
        if _state is not None:
            return _state

        try:
            import torch
            import torch.nn as nn
            import torch.nn.functional as F
            import pandas as pd
            from torch_geometric.nn import HGTConv, Linear as PyGLinear
        except ImportError as e:
            raise GnnUnavailable(f"缺少 GNN 依賴套件：{e}")

        required = [
            'best_model_with_quiz.pt', 'hetero_graph.pt',
            'reviews_clean.csv', 'cafe2idx.json', 'cafes_updated.json',
        ]
        for fname in required:
            if not os.path.exists(os.path.join(GNN_DIR, fname)):
                raise GnnUnavailable(f"缺少 GNN 檔案：{fname}")

        class QuizProjector(nn.Module):
            def __init__(self):
                super().__init__()
                self.net = nn.Sequential(
                    nn.Linear(5, 64), nn.ReLU(), nn.Dropout(0.2), nn.Linear(64, 384),
                )

            def forward(self, x):
                return self.net(x)

        class HGTWithQuiz(nn.Module):
            def __init__(self, data):
                super().__init__()
                self.quiz_projector = QuizProjector()
                self.user_proj = PyGLinear(384, HIDDEN_DIM)
                self.cafe_proj = PyGLinear(384, HIDDEN_DIM)
                self.convs = nn.ModuleList([
                    HGTConv(HIDDEN_DIM, HIDDEN_DIM, data.metadata(), NUM_HEADS)
                    for _ in range(NUM_LAYERS)
                ])
                self.predictor = nn.Sequential(
                    nn.Linear(HIDDEN_DIM * 2, HIDDEN_DIM), nn.ReLU(),
                    nn.Dropout(0.3), nn.Linear(HIDDEN_DIM, 1),
                )

            def encode(self, user_input, data):
                x_dict = {
                    "user": self.user_proj(user_input),
                    "cafe": self.cafe_proj(data["cafe"].x),
                }
                for conv in self.convs:
                    x_dict = {k: F.relu(v)
                              for k, v in conv(x_dict, data.edge_index_dict).items()}
                return x_dict

        try:
            # hetero_graph.pt 是本地訓練產物（HeteroData 物件），需允許完整反序列化
            data = torch.load(
                os.path.join(GNN_DIR, 'hetero_graph.pt'),
                map_location='cpu', weights_only=False
            )
            model = HGTWithQuiz(data)
            model.load_state_dict(torch.load(
                os.path.join(GNN_DIR, 'best_model_with_quiz.pt'), map_location='cpu'
            ))
            model.eval()

            with open(os.path.join(GNN_DIR, 'cafe2idx.json'), encoding='utf-8') as f:
                cafe2idx = json.load(f)
            idx2cafe_id = {v: int(k) for k, v in cafe2idx.items()}

            with open(os.path.join(GNN_DIR, 'cafes_updated.json'), encoding='utf-8') as f:
                cafes_raw = json.load(f)
            id2tags = {int(c['id']): c.get('review_tags', []) or [] for c in cafes_raw}

            df = pd.read_csv(os.path.join(GNN_DIR, 'reviews_clean.csv'))
            stats = df.groupby('cafe_idx')['score'].agg(
                avg_score='mean', review_count='count'
            ).reset_index()
            cafe_stats = {
                int(row['cafe_idx']): (float(row['avg_score']), int(row['review_count']))
                for _, row in stats.iterrows()
            }

            # cafe embedding 只需算一次（圖結構固定）
            with torch.no_grad():
                z_cafe = model.encode(data['user'].x, data)['cafe']  # (n_cafes, 128)

            _state = {
                'torch': torch, 'F': F,
                'model': model, 'z_cafe': z_cafe,
                'idx2cafe_id': idx2cafe_id, 'id2tags': id2tags,
                'cafe_stats': cafe_stats,
            }
            logging.info("[GNN] 模型載入完成（%d 家咖啡廳）", len(idx2cafe_id))
            return _state
        except GnnUnavailable:
            raise
        except Exception as e:
            raise GnnUnavailable(f"GNN 載入失敗：{e}")


def is_available() -> bool:
    """檢查 GNN 推薦是否可用（會觸發首次載入）。"""
    try:
        _load()
        return True
    except GnnUnavailable:
        return False


def _passes_hard_filters(cafe_id: int, hard_filters: dict, id2tags: dict) -> bool:
    tags_text = ' '.join(id2tags.get(cafe_id, []))
    for flag, keywords in _HARD_FILTER_TAGS.items():
        if hard_filters.get(flag) and not any(kw in tags_text for kw in keywords):
            return False
    return True


def _tag_match_score(cafe_id: int, keywords: list, id2tags: dict) -> float:
    """
    使用者已表達的偏好關鍵字，與店家 review_tags 的匹配比例（0~1）。

    GNN 的 predictor 輸出擠在很窄的區間（實測多在 0.96~0.98），
    對「這一輪講了什麼」不夠敏感；標籤匹配補上這塊反應度。
    """
    if not keywords:
        return 0.0
    tags_text = ' '.join(id2tags.get(cafe_id, []))
    if not tags_text:
        return 0.0
    hit = sum(1 for kw in keywords if kw and kw in tags_text)
    return hit / len(keywords)


def _blend_scores(candidates: list, keywords: list, id2tags: dict, weight: float) -> None:
    """
    就地寫入 blended_score = (1-w)·正規化GNN + w·標籤匹配。

    GNN 原始分數先做 min-max 正規化，否則它的窄區間會被標籤分數淹沒。
    """
    if not candidates:
        return
    raw = [c['gnn_score'] for c in candidates]
    lo, hi = min(raw), max(raw)
    # 跨距下限：GNN 分數擠成一團時（常見），純 min-max 會把 0.01 的差距
    # 放大成滿分差距、壓過標籤匹配。設下限讓微小差異維持微小。
    span = max(hi - lo, MIN_GNN_SPAN)
    for c in candidates:
        norm_gnn = (c['gnn_score'] - lo) / span
        tag = _tag_match_score(c['cafe_id'], keywords, id2tags)
        c['tag_score'] = tag
        c['blended_score'] = (1 - weight) * norm_gnn + weight * tag if keywords else norm_gnn


def _tiered_sample(candidates: list, guaranteed: int = 0) -> list:
    """
    分層抽樣：精選（≥4.7）抽 3 + 優質（4.0~4.7）抽 2，不足時互補。

    guaranteed > 0 時，先把整體分數最高的前 N 家「保證入選」，
    避免使用者明講的需求（例如寵物友善）被隨機抽樣洗掉；
    其餘名額仍隨機，維持每次推薦的變化性。
    """
    rank_key = lambda c: c.get('blended_score', c['gnn_score'])

    locked = []
    if guaranteed > 0:
        ranked_all = sorted(candidates, key=rank_key, reverse=True)
        locked = ranked_all[:guaranteed]
        locked_ids = {c['cafe_id'] for c in locked}
        candidates = [c for c in candidates if c['cafe_id'] not in locked_ids]
    tier1 = sorted(
        [c for c in candidates if c['avg_score'] >= TIER1_THRESHOLD],
        key=rank_key, reverse=True
    )
    tier2 = sorted(
        [c for c in candidates if TIER2_MIN <= c['avg_score'] < TIER1_THRESHOLD],
        key=rank_key, reverse=True
    )

    total = TIER1_PICK + TIER2_PICK
    remaining = max(0, total - len(locked))
    # 保證名額佔掉的份額，按比例從精選層先扣
    pick1 = max(0, min(TIER1_PICK, remaining))
    pick2 = max(0, remaining - pick1)

    chosen = random.sample(tier1[:TIER1_POOL_SIZE], min(pick1, len(tier1[:TIER1_POOL_SIZE])))
    chosen += random.sample(tier2[:TIER2_POOL_SIZE], min(pick2, len(tier2[:TIER2_POOL_SIZE])))

    if len(chosen) < remaining:
        chosen_ids = {c['cafe_id'] for c in chosen}
        extra = [c for c in tier1 + tier2 if c['cafe_id'] not in chosen_ids]
        chosen += extra[:remaining - len(chosen)]

    return sorted(locked + chosen, key=rank_key, reverse=True)


def recommend_by_scores(scores: dict, hard_filters: dict | None = None,
                        exclude_ids: set | None = None,
                        pref_keywords: list | None = None,
                        tag_weight: float = TAG_BLEND_WEIGHT) -> list:
    """
    以（調整後的）五維分數執行 GNN 推薦，並用已表達的偏好關鍵字微調排序。

    參數:
        scores:        {work, env, social, taste, cp} 調整後分數
        hard_filters:  {'pet': bool, 'parking': bool, 'night': bool}
        exclude_ids:   要排除的 DB cafe id（例如已推薦過的）
        pref_keywords: 對話中已表達的偏好關鍵字（與店家標籤混合排序）
        tag_weight:    標籤匹配在最終分數的權重（0 = 純 GNN）

    回傳:
        [{'cafe_id', 'gnn_score', 'tag_score', 'blended_score', 'avg_score', 'review_count'}]

    拋出:
        GnnUnavailable — 呼叫端應回退關鍵字檢索
    """
    state = _load()
    torch = state['torch']
    F = state['F']
    model = state['model']

    max_s = max(scores.values()) if scores and max(scores.values()) > 0 else 1
    vec = torch.tensor([[float(scores.get(d, 0)) / max_s for d in DIMS]], dtype=torch.float)

    with torch.no_grad():
        projected = model.quiz_projector(vec)                     # (1, 384)
        user_vec = F.relu(model.user_proj(projected)).squeeze(0)  # (128,)
        z_cafe = state['z_cafe']
        n_cafes = z_cafe.shape[0]
        u_rep = user_vec.unsqueeze(0).expand(n_cafes, -1)
        raw = torch.sigmoid(model.predictor(
            torch.cat([u_rep, z_cafe], dim=-1)
        )).squeeze(-1).numpy()

    hard_filters = hard_filters or {}
    exclude_ids = exclude_ids or set()

    candidates = []
    for idx, cafe_id in state['idx2cafe_id'].items():
        if cafe_id in exclude_ids:
            continue
        avg_score, review_count = state['cafe_stats'].get(idx, (0.0, 0))
        candidates.append({
            'cafe_id': cafe_id,
            'gnn_score': float(raw[idx]),
            'avg_score': avg_score,
            'review_count': review_count,
        })

    # 硬過濾（寵物／停車／深夜）；若過濾後不足 5 家則放寬
    filtered = [c for c in candidates
                if _passes_hard_filters(c['cafe_id'], hard_filters, state['id2tags'])]
    if len(filtered) < TIER1_PICK + TIER2_PICK:
        filtered = candidates

    # 混合排序：GNN 分數（正規化）＋ 這一輪講到的偏好與店家標籤的匹配度
    keywords = [k for k in (pref_keywords or []) if isinstance(k, str) and k and k != '不限']
    _blend_scores(filtered, keywords, state['id2tags'], tag_weight)

    # 有明確偏好且真的有店家對上時，保證最匹配的兩家入選（其餘仍隨機）
    has_match = any(c.get('tag_score', 0) > 0 for c in filtered)
    guaranteed = GUARANTEED_TOP_MATCHES if (keywords and has_match) else 0

    return _tiered_sample(filtered, guaranteed=guaranteed)
