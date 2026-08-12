"""
gnn_recommender.py — GNN 推薦接口（後半段）

載入 GNN/ 目錄的訓練產物（HGT + quiz_projector），提供：
    recommend_by_scores(五維分數, hard_filters) → [{'cafe_id', 'gnn_score', ...}]

推薦路徑（與 GNN/new_step5_recommend.py 的新用戶路徑一致）：
    五維分數 → quiz_projector(5→384)
             → 和 2286 個既有使用者算 cosine 相似度，取最像的前 K 名
             → 把這位新使用者插進圖、補上 user↔user 雙向邊
             → 用「含新使用者的臨時圖」跑 HGT 卷積
             → 取新使用者的 128 維 embedding 與 cafe embedding 配對 → predictor 打分
             → 分層抽樣（精選 ≥4.7 抽 3、優質 4.0~4.7 抽 2）

為什麼要動態接邊：
  舊版把新使用者停在 user_proj 就直接打分，等於他從來沒進過圖、
  收不到任何鄰居訊息。實測那樣做「偏工作／偏社交／偏口味／偏CP值」
  四種需求算出來的前五名是同一組店，只是順序不同 —— 圖等於白建了。
  接邊之後前五名才真的隨需求改變（兩兩重疊從 3.4/5 降到 2.1/5）。
  代價是每次推薦要重跑一次 HGT，實測 19ms，可以接受。

設計：
  - 模型與圖只載入一次（module-level cache + lock）
  - cafe embedding 不能預先算：接了新邊之後整張圖的卷積結果都會變，
    必須和新使用者在同一次 encode 裡算出來
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

# 新使用者接邊參數（與 GNN/new_step5_recommend.py 一致）
NEW_USER_TOP_K = 50
# 相似度下限：低於這個值的「相似使用者」其實不相似，接了只會灌雜訊進來。
# 實測正常的測驗結果落在 0.84~0.92，這條線平常不會擋到人。
NEW_USER_MIN_SIM = 0.5

# 標籤匹配在最終排序的權重（0 = 純 GNN、1 = 純標籤匹配）。
# 接邊之前 GNN 對需求沒反應，得靠標籤扛（當時是 0.4）；
# 現在 GNN 自己會動了，標籤退回輔助角色。
TAG_BLEND_WEIGHT = 0.35
# 有明確偏好時，保證最匹配的前幾家一定入選（其餘名額仍隨機，維持變化性）
GUARANTEED_TOP_MATCHES = 2

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
            from torch_geometric.data import HeteroData
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

            _state = {
                'torch': torch, 'F': F, 'HeteroData': HeteroData,
                'model': model, 'data': data,
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


def _insert_new_user(projected_384, state, top_k: int = NEW_USER_TOP_K):
    """
    把這位新使用者插進圖，並接上和他最像的 K 位既有使用者。

    只有 user↔user 邊要動（新使用者沒有評論，本來就不該有 user→cafe 邊）。
    原圖完全不改：新 tensor 用 torch.cat 另建，其餘欄位是參考沿用。

    回傳 (臨時圖, 新使用者的節點索引, 鄰居相似度 list)
    """
    torch, F = state['torch'], state['F']
    data = state['data']
    HeteroData = state['HeteroData']

    existing = data['user'].x                      # (n_users, 384)
    n_users = existing.shape[0]
    new_idx = n_users
    device = existing.device

    sim = (F.normalize(existing, dim=-1)
           @ F.normalize(projected_384, dim=-1).T).squeeze(-1)   # (n_users,)
    vals, idxs = torch.topk(sim, min(top_k, n_users))

    keep = vals >= NEW_USER_MIN_SIM
    if keep.any():
        vals, idxs = vals[keep], idxs[keep]
    else:
        # 一個夠像的都沒有 → 至少接最相近的那一位。
        # 完全不接邊會讓新使用者變成孤立節點，HGT 傳不到任何訊息，
        # 等於退回舊版那條「沒進過圖」的路徑。
        vals, idxs = vals[:1], idxs[:1]
    k = idxs.shape[0]

    new_x = torch.cat([existing, projected_384.squeeze(0).unsqueeze(0)], dim=0)

    src = torch.full((k,), new_idx, dtype=torch.long, device=device)
    dst = idxs.to(device)
    # 雙向：新→舊 和 舊→新
    added = torch.stack([torch.cat([src, dst]), torch.cat([dst, src])], dim=0)

    tmp = HeteroData()
    tmp['user'].x = new_x
    tmp['user'].num_nodes = n_users + 1
    tmp['cafe'].x = data['cafe'].x
    tmp['cafe'].num_nodes = data['cafe'].num_nodes
    # 掃過所有邊型別而不是逐一列舉：圖以後多一種邊時，
    # 逐一列舉會靜默漏掉，HGTConv 拿不到那型別的邊也不會報錯。
    for edge_type in data.edge_types:
        orig = data[edge_type].edge_index
        if edge_type == ('user', 'similar_to', 'user'):
            tmp[edge_type].edge_index = torch.cat([orig, added], dim=1)
        else:
            tmp[edge_type].edge_index = orig

    return tmp, new_idx, vals.cpu().tolist()


def _passes_hard_filters(cafe_id: int, hard_filters: dict, id2tags: dict) -> bool:
    tags_text = ' '.join(id2tags.get(cafe_id, []))
    for flag, keywords in _HARD_FILTER_TAGS.items():
        if hard_filters.get(flag) and not any(kw in tags_text for kw in keywords):
            return False
    return True


def _tag_match_score(cafe_id: int, keywords: list, id2tags: dict) -> float:
    """
    使用者已表達的偏好關鍵字，與店家 review_tags 的匹配比例（0~1）。

    GNN 認得的是「和你相似的人喜歡什麼」，認不得「你這一句話說了什麼」——
    測驗五維是粗粒度的，講到「甜點」「插座」這種具體需求時，
    店家標籤才是直接證據。兩者互補，不是誰取代誰。
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
    就地寫入 blended_score = (1-w)·GNN名次分數 + w·標籤匹配。

    GNN 這一側用「名次」而不是分數本身正規化：
    logit 的值域是 +17 ~ -59，最低的那幾家離群值極遠，
    做 min-max 會把前二十名全部壓進 0.98~1.00 的窄帶，等於沒有區別。
    改成第一名 1.0、最後一名 0.0 均勻遞減，混合時兩側的尺度才對得起來。
    """
    if not candidates:
        return
    ranked = sorted(candidates, key=lambda c: c['gnn_logit'], reverse=True)
    last = max(1, len(ranked) - 1)
    for rank, c in enumerate(ranked):
        c['gnn_rank_score'] = 1.0 - rank / last

    for c in candidates:
        tag = _tag_match_score(c['cafe_id'], keywords, id2tags)
        c['tag_score'] = tag
        c['blended_score'] = (
            (1 - weight) * c['gnn_rank_score'] + weight * tag
            if keywords else c['gnn_rank_score']
        )


def _tiered_sample(candidates: list, guaranteed: int = 0) -> list:
    """
    分層抽樣：精選（≥4.7）抽 3 + 優質（4.0~4.7）抽 2，不足時互補。

    guaranteed > 0 時，先把整體分數最高的前 N 家「保證入選」，
    避免使用者明講的需求（例如寵物友善）被隨機抽樣洗掉；
    其餘名額仍隨機，維持每次推薦的變化性。
    """
    # 一律用 blended_score；退而求其次也要用 logit 而不是 gnn_score，
    # 後者飽和成 1.0 的家數很多，拿來排序等於沒排
    rank_key = lambda c: c.get('blended_score', c.get('gnn_logit', c['gnn_score']))

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
    model = state['model']

    max_s = max(scores.values()) if scores and max(scores.values()) > 0 else 1
    vec = torch.tensor([[float(scores.get(d, 0)) / max_s for d in DIMS]], dtype=torch.float)

    with torch.no_grad():
        projected = model.quiz_projector(vec)                     # (1, 384)
        # 接邊後跑 HGT：新使用者與 cafe 的 embedding 必須來自同一次 encode，
        # cafe 那邊的卷積結果也會因為多了這些邊而改變
        tmp_data, new_idx, _sims = _insert_new_user(projected, state)
        z = model.encode(tmp_data['user'].x, tmp_data)
        user_vec = z['user'][new_idx]                             # (128,)
        z_cafe = z['cafe']                                        # (n_cafes, 128)
        n_cafes = z_cafe.shape[0]
        u_rep = user_vec.unsqueeze(0).expand(n_cafes, -1)
        # 排序用 logit（sigmoid 之前）。predictor 的 logit 落在 +17 ~ -59，
        # 接邊之後 56 家有 43 家的 sigmoid 直接飽和成 1.0 —— 前十名 logit
        # 只差 0.2，套完 sigmoid 全都變成同一個數字，名次資訊整個消失。
        # sigmoid 是單調的，用 logit 排序名次一樣，但解析度留得住。
        logits = model.predictor(
            torch.cat([u_rep, z_cafe], dim=-1)
        ).squeeze(-1).numpy()
        raw = torch.sigmoid(torch.from_numpy(logits)).numpy()

    hard_filters = hard_filters or {}
    exclude_ids = exclude_ids or set()

    candidates = []
    for idx, cafe_id in state['idx2cafe_id'].items():
        if cafe_id in exclude_ids:
            continue
        avg_score, review_count = state['cafe_stats'].get(idx, (0.0, 0))
        candidates.append({
            'cafe_id': cafe_id,
            'gnn_score': float(raw[idx]),     # 顯示用（0~1，好讀）
            'gnn_logit': float(logits[idx]),  # 排序用（保留解析度）
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
