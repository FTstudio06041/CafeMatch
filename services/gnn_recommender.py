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


def _tiered_sample(candidates: list) -> list:
    """分層抽樣：精選（≥4.7）抽 3 + 優質（4.0~4.7）抽 2，不足時互補。"""
    tier1 = sorted(
        [c for c in candidates if c['avg_score'] >= TIER1_THRESHOLD],
        key=lambda c: c['gnn_score'], reverse=True
    )
    tier2 = sorted(
        [c for c in candidates if TIER2_MIN <= c['avg_score'] < TIER1_THRESHOLD],
        key=lambda c: c['gnn_score'], reverse=True
    )

    chosen = random.sample(tier1[:TIER1_POOL_SIZE], min(TIER1_PICK, len(tier1[:TIER1_POOL_SIZE])))
    chosen += random.sample(tier2[:TIER2_POOL_SIZE], min(TIER2_PICK, len(tier2[:TIER2_POOL_SIZE])))

    if len(chosen) < TIER1_PICK + TIER2_PICK:
        chosen_ids = {c['cafe_id'] for c in chosen}
        extra = [c for c in tier1 + tier2 if c['cafe_id'] not in chosen_ids]
        need = TIER1_PICK + TIER2_PICK - len(chosen)
        chosen += extra[:need]

    return sorted(chosen, key=lambda c: c['gnn_score'], reverse=True)


def recommend_by_scores(scores: dict, hard_filters: dict | None = None,
                        exclude_ids: set | None = None) -> list:
    """
    以（調整後的）五維分數執行 GNN 推薦。

    參數:
        scores:       {work, env, social, taste, cp} 調整後分數
        hard_filters: {'pet': bool, 'parking': bool, 'night': bool}
        exclude_ids:  要排除的 DB cafe id（例如已推薦過的）

    回傳:
        [{'cafe_id', 'gnn_score', 'avg_score', 'review_count'}]（依 gnn_score 排序，最多 5 家）

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

    return _tiered_sample(filtered)
