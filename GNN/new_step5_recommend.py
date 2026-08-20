import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

"""
統一推薦入口 recommend.py
======================================================================
判斷邏輯：
  - 舊用戶（有評論）→ GNN 路徑
      user BERT 向量 → user_proj → HGT卷積 → predictor → 推薦分數

  - 新用戶（冷啟動）→ 心理測驗 + 動態接邊 + GNN 路徑
      五維分數 → quiz_projector → projected_384
      projected_384 和 2286 個 BERT 向量做 cosine sim → 取 top-K 接 user↔user 邊
      把新用戶插入圖（idx = n_users）→ HGT卷積 → predictor → 推薦分數

======================================================================
所需檔案：
  best_model_with_quiz.pt / hetero_graph.pt / reviews_clean.csv
  user2idx.json / cafe2idx.json / cafes_updated.json
======================================================================
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import pandas as pd
import json
import random

# 資料檔一律以「這支腳本所在目錄」為準，不是行程的工作目錄
# —— 否則從專案根目錄執行會找不到 hetero_graph.pt
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _path(fname):
    return os.path.join(BASE_DIR, fname)


DEVICE     = torch.device("cuda" if torch.cuda.is_available() else "cpu")
HIDDEN_DIM = 128
NUM_HEADS  = 4
NUM_LAYERS = 2

# ── 分層推薦參數 ──────────────────────────────────────────
TIER1_THRESHOLD = 4.7
TIER2_MIN       = 4.0
TIER1_POOL_SIZE = 8
TIER2_POOL_SIZE = 6
TIER1_PICK      = 3
TIER2_PICK      = 2

# ── 新用戶接邊參數 ────────────────────────────────────────
# 取前 5 名而不是 50：投影後的向量彼此 cosine 高達 0.97（BERT 空間本來就
# anisotropy，既有使用者彼此平均也有 0.53），對前 2.2% 的人做平均會把測驗訊號
# 洗掉。實測不同需求的前十名兩兩重疊 k=50 是 8.0/10、k=5 降到 5.1/10，
# 而抗噪性只從 9.4 微降到 9.2。詳見 services/gnn_recommender.py 的註解。
NEW_USER_TOP_K  = 5     # cosine similarity 取前幾名做連線
# 相似度下限：低於這個值的「相似使用者」其實不相似，接了只會把雜訊灌進來。
# 實測正常的測驗結果會落在 0.84~0.92，所以這條線平常不會擋到任何人，
# 是給「誰都不像」的極端測驗結果用的保險。
NEW_USER_MIN_SIM = 0.5

# ── 硬過濾條件（Q9）→ review_tags 關鍵字 ──────────────────
# 注意：review_tags 是從評論文字抽出來的詞，不是店家屬性，
# 56 家裡只有 2 家含「寵物」、0 家含「停車」與「夜」，所以這裡幾乎一定會放寬。
# 網站端（services/cafe_facts.py）改從資料庫的 tags 表與營業時間取，
# 寵物友善有 20 家、晚間營業有 12 家。這支離線腳本不連資料庫，維持現狀。
HARD_FILTER_TAGS = {
    "pet"    : ("寵物",),
    "parking": ("停車",),
    "night"  : ("深夜", "晚", "夜"),
}

DIMS      = ["work", "env", "social", "taste", "cp"]
DIM_NAMES = {"work":"工作專注","env":"環境美感","social":"社交氛圍","taste":"口味品質","cp":"CP值"}

# ══════════════════════════════════════════════════════════
# 心理測驗題目
# ══════════════════════════════════════════════════════════
QUIZ = [
    {
        "q": "Q1【情境：出發的裝備】午後兩點的花蓮陽光正好。準備出門找間咖啡廳坐坐，你背包裡塞得最沉的那樣東西是什麼？",
        "options": [
            ("A", "微熱的筆電，和一本厚厚的原文書",          {"work":2,"env":1,"social":0,"taste":0,"cp":0}),
            ("B", "底片相機，還有精心搭配的墨鏡",             {"work":0,"env":2,"social":1,"taste":1,"cp":0}),
            ("C", "什麼都沒帶，只帶了想和朋友大聊特聊的心情", {"work":0,"env":0,"social":3,"taste":1,"cp":0}),
        ],
    },
    {
        "q": "Q2【情境：踏入店內的第一眼】推開沉重的木門，風鈴聲響起。當視線落下的那一刻，最先吸引你目光的是？",
        "options": [
            ("A", "吧台那台發亮的義式咖啡機，和手沖壺的熱氣",      {"work":0,"env":1,"social":0,"taste":3,"cp":0}),
            ("B", "角落那個靠窗、有陽光灑落的慵懶沙發座",           {"work":1,"env":2,"social":1,"taste":0,"cp":0}),
            ("C", "櫃檯上方的小黑板，看看有沒有今日特餐或低消規定", {"work":0,"env":0,"social":0,"taste":1,"cp":3}),
        ],
    },
    {
        "q": "Q3【情境：聲音的頻率】找好位置坐下，店內的背景聲音開始包圍你。你希望耳邊流淌著哪一種頻率？",
        "options": [
            ("A", "只有磨豆機的規律低鳴，大家都輕聲細語",             {"work":2,"env":2,"social":0,"taste":0,"cp":0}),
            ("B", "杯盤碰撞聲與陌生人的交談，揉成剛剛好的白噪音",     {"work":1,"env":0,"social":2,"taste":1,"cp":0}),
            ("C", "老闆正在跟熟客聊著豆子的產地，還有昨天花蓮的海浪", {"work":0,"env":1,"social":2,"taste":2,"cp":0}),
        ],
    },
    {
        "q": "Q4【情境：點餐時刻】翻開微微泛黃的菜單。最終，你選擇用哪一種組合來填滿這段午後的留白？",
        "options": [
            ("A", "招牌單品手沖 ＋ 限量手工甜點",                 {"work":0,"env":1,"social":0,"taste":3,"cp":0}),
            ("B", "一杯冰美式 ＋ 一份抹上奶油的烤吐司",            {"work":1,"env":0,"social":0,"taste":1,"cp":3}),
            ("C", "色澤浮誇的季節氣泡飲 ＋ 一塊長得怪可愛的蛋糕", {"work":0,"env":3,"social":1,"taste":1,"cp":0}),
        ],
    },
    {
        "q": "Q5【情境：空間的密度】隨著時間過去，店內的人漸漸多了起來。哪一種空間密度會讓你開始考慮離開？",
        "options": [
            ("A", "每張桌子都坐了人，甚至有人開始在等位，稍微有些擁擠", {"work":2,"env":1,"social":0,"taste":0,"cp":0}),
            ("B", "隔壁桌坐了家庭客或一群朋友，聊天聲音稍微大聲了一些",  {"work":0,"env":0,"social":3,"taste":0,"cp":1}),
            ("C", "就算人變多，大家依然很有默契地保持社交距離與低音量",   {"work":1,"env":2,"social":1,"taste":0,"cp":0}),
        ],
    },
    {
        "q": "Q6【情境：時間的流逝】如果沒有其他行程，你通常會如何在咖啡廳裡消耗你的時間？",
        "options": [
            ("A", "一口咖啡、一頁書，不知不覺就看到店內亮起黃昏的燈光",         {"work":2,"env":2,"social":0,"taste":0,"cp":1}),
            ("B", "和朋友從最近的生活聊到未來的計畫，每隔一陣子就點一份新點心", {"work":0,"env":1,"social":2,"taste":2,"cp":0}),
            ("C", "把咖啡喝完、甜點拍完照，回味一下剛才的美味就準備動身",       {"work":0,"env":2,"social":0,"taste":2,"cp":0}),
        ],
    },
    {
        "q": "Q7【情境：店家的個性】如果菜單上有一個區塊寫著「店主碎碎念」或「空間使用守則」，你的第一反應是？",
        "options": [
            ("A", "認真看完，覺得有這些堅持的店，咖啡或空間品質一定很有水準",  {"work":1,"env":1,"social":0,"taste":2,"cp":0}),
            ("B", "稍微掃過一眼，只要規定不要太嚴苛、能讓我放鬆聊天就好",      {"work":0,"env":0,"social":3,"taste":0,"cp":1}),
            ("C", "主要是看看有沒有最低消費、禁止外食這類基本的實用規定",       {"work":0,"env":0,"social":1,"taste":0,"cp":3}),
        ],
    },
    {
        "q": "Q8【情境：菜單的延伸】除了咖啡之外，如果這家店還提供其他品項，哪一種會特別讓你想要點點看？",
        "options": [
            ("A", "花蓮在地小農研發的茶飲，或是結合當地食材的手作鹹派", {"work":0,"env":1,"social":0,"taste":3,"cp":0}),
            ("B", "香氣撲鼻的咖哩飯或早午餐，份量看起來非常有誠意",       {"work":1,"env":0,"social":0,"taste":1,"cp":3}),
            ("C", "各種無咖啡因的精緻特調，或是非常適合拍照的特色聖代",   {"work":0,"env":3,"social":1,"taste":0,"cp":0}),
        ],
    },
]

Q9_OPTIONS = [
    ("1", "身旁還跟著一隻毛茸茸的靈魂（寵物友善）"),
    ("2", "我是駕著坐騎、御風而來的旅人（好停車）"),
    ("3", "我打算在這裡，一路坐到夜幕低垂（晚間營業）"),
]

# ══════════════════════════════════════════════════════════
# 模型定義（與 train_with_quiz.py 完全一致）
# ══════════════════════════════════════════════════════════
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
        from torch_geometric.nn import HGTConv, Linear as PyGLinear
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
        """
        user_input : (n_users 或 n_users+1, 384)
        data       : 原始圖 或 插入新用戶邊後的臨時圖
        """
        x_dict = {
            "user": self.user_proj(user_input),
            "cafe": self.cafe_proj(data["cafe"].x),
        }
        for conv in self.convs:
            x_dict = {k: F.relu(v)
                      for k, v in conv(x_dict, data.edge_index_dict).items()}
        return x_dict

    def get_all_cafe_scores(self, user_vec_128, z_cafe):
        """
        回傳 (sigmoid 分數, logit)。

        排序一定要用 logit：predictor 的 logit 落在 +17 ~ -59，
        56 家裡 33 家的 sigmoid 精確等於 1.0、16 家等於 0.0，
        只剩 9 種不同的值。拿 sigmoid 排序時前段全是同分，
        抽獎池會退化成「原始順序的前八家」而不是「最match的前八家」。
        sigmoid 單調遞增，用 logit 排名次結果一樣，但解析度留得住。
        """
        n_cafes = z_cafe.shape[0]
        u_rep   = user_vec_128.unsqueeze(0).expand(n_cafes, -1)
        concat  = torch.cat([u_rep, z_cafe], dim=-1)
        with torch.no_grad():
            logits = self.predictor(concat).squeeze(-1)
            scores = torch.sigmoid(logits)
        return scores.cpu().numpy(), logits.cpu().numpy()


# ══════════════════════════════════════════════════════════
# 核心：把新用戶插入圖並補邊
# ══════════════════════════════════════════════════════════
def insert_new_user_into_graph(projected_384: torch.Tensor,
                               data,
                               top_k: int = NEW_USER_TOP_K):
    """
    將新用戶插入圖中，步驟：
      1. 計算 projected_384 與所有 2286 個 user BERT 向量的 cosine similarity
      2. 取前 top_k 個相似使用者（低於 NEW_USER_MIN_SIM 的不接）
      3. 把新用戶的 384 維向量 append 到 data["user"].x 的最後一列
         → 新用戶的 idx = n_users（原本最後一個 idx + 1）
      4. 補上 user↔user 雙向邊：(new_idx → top_k_idx) 和 (top_k_idx → new_idx)
      5. 回傳「暫時修改過的圖」和「新用戶的 idx」

    原圖完全不動：新的 tensor 都用 torch.cat 另外建立，
    其餘欄位是參考沿用（不是複製），所以不必 deep copy 整張大圖。
    """
    from torch_geometric.data import HeteroData

    n_users    = data["user"].x.shape[0]   # 2286
    new_idx    = n_users                   # 新用戶的節點 idx
    device     = data["user"].x.device     # 跟著圖走，不要自己假設 DEVICE

    # ── Step 1：cosine similarity ─────────────────────────
    existing_bert = data["user"].x          # (n_users, 384)
    new_vec_norm  = F.normalize(projected_384, dim=-1)           # (1, 384)
    exist_norm    = F.normalize(existing_bert, dim=-1)            # (n_users, 384)
    sim_scores    = (exist_norm @ new_vec_norm.T).squeeze(-1)     # (n_users,)

    # ── Step 2：取前 top_k，並砍掉不夠相似的 ──────────────
    actual_k   = min(top_k, n_users)
    topk_vals, topk_idxs = torch.topk(sim_scores, actual_k)
    keep = topk_vals >= NEW_USER_MIN_SIM
    if keep.any():
        topk_vals, topk_idxs = topk_vals[keep], topk_idxs[keep]
    else:
        # 一個夠像的都沒有 → 至少接最相近的那一個，
        # 完全不接邊的話新用戶會是孤立節點，HGT 傳不到任何訊息
        topk_vals, topk_idxs = topk_vals[:1], topk_idxs[:1]
    actual_k = topk_idxs.shape[0]

    # ── Step 3：把新用戶向量 append 到 user 特徵矩陣 ───────
    # 注意：用 torch.cat 建立新 tensor，不修改原始 data
    new_user_feat = projected_384.squeeze(0).unsqueeze(0)         # (1, 384)
    new_user_x    = torch.cat([existing_bert, new_user_feat], dim=0)  # (n_users+1, 384)

    # ── Step 4：補上新的 user↔user 邊 ────────────────────
    # 新邊：new_idx → top_k_idx（雙向）
    new_src = torch.full((actual_k,), new_idx,
                         dtype=torch.long, device=device)         # (k,) 全是 new_idx
    new_dst = topk_idxs.to(device)                                # (k,) top_k 的舊用戶

    # 雙向：new→old 和 old→new
    added_src = torch.cat([new_src, new_dst], dim=0)              # (2k,)
    added_dst = torch.cat([new_dst, new_src], dim=0)              # (2k,)
    added_edge = torch.stack([added_src, added_dst], dim=0)       # (2, 2k)

    # ── Step 5：組成臨時圖（不影響原始 data）─────────────
    tmp_data = HeteroData()

    # user 節點：換成包含新用戶的特徵矩陣
    tmp_data["user"].x         = new_user_x
    tmp_data["user"].num_nodes = n_users + 1

    # cafe 節點：直接沿用
    tmp_data["cafe"].x         = data["cafe"].x
    tmp_data["cafe"].num_nodes = data["cafe"].num_nodes

    # 邊：只有 user↔user 要加新邊，其餘原樣沿用。
    # 用迴圈掃過所有邊型別而不是逐一列舉 —— 圖以後多一種邊時，
    # 逐一列舉會靜默漏掉，HGTConv 拿不到那型別的邊也不會報錯。
    for edge_type in data.edge_types:
        orig = data[edge_type].edge_index
        if edge_type == ("user", "similar_to", "user"):
            tmp_data[edge_type].edge_index = torch.cat([orig, added_edge], dim=1)
        else:
            tmp_data[edge_type].edge_index = orig

    return tmp_data, new_idx, topk_idxs.cpu().tolist(), topk_vals.cpu().tolist()


# ══════════════════════════════════════════════════════════
# 資料載入
# ══════════════════════════════════════════════════════════
def load_all():
    # PyTorch 2.6+ 預設 weights_only=True，但 HeteroData 不是純權重物件，
    # 需要明確加入信任清單並設 weights_only=False
    from torch_geometric.data import HeteroData
    torch.serialization.add_safe_globals([HeteroData])
    data = torch.load(_path("hetero_graph.pt"), map_location=DEVICE, weights_only=False)

    with open(_path("user2idx.json"), encoding="utf-8") as f:
        user2idx = json.load(f)
    with open(_path("cafe2idx.json"), encoding="utf-8") as f:
        cafe2idx = json.load(f)

    df = pd.read_csv(_path("reviews_clean.csv"))

    with open(_path("cafes_updated.json"), encoding="utf-8") as f:
        cafes_raw = json.load(f)
    idx2cafe_id = {v: k for k, v in cafe2idx.items()}
    id2cafe     = {str(c["id"]): c for c in cafes_raw}
    idx2info = {}
    for idx, cafe_id_str in idx2cafe_id.items():
        raw  = id2cafe.get(cafe_id_str, {})
        addr = raw.get("address", "")
        if addr and addr[:3].isdigit():
            addr = addr[3:]
        url = raw.get("url", "")
        idx2info[idx] = {
            "name"        : raw.get("name", f"咖啡廳 {cafe_id_str}"),
            "address"     : addr,
            "cost"        : raw.get("cost", ""),
            "phone"       : raw.get("phone", ""),
            "website"     : raw.get("website", ""),
            "review_tags" : raw.get("review_tags", []),
            "google_url"  : f"https://maps.app.goo.gl/{url}" if url else "",
        }

    cafe_stats = df.groupby("cafe_idx")["score"].agg(
        avg_score="mean", review_count="count"
    ).reset_index()

    return data, user2idx, cafe2idx, df, idx2info, cafe_stats


def load_model(data):
    model = HGTWithQuiz(data).to(DEVICE)
    model.load_state_dict(
        torch.load(_path("best_model_with_quiz.pt"), map_location=DEVICE, weights_only=False)
    )
    model.eval()
    return model


# ══════════════════════════════════════════════════════════
# 推薦共用邏輯
# ══════════════════════════════════════════════════════════
def _build_cafe_list(raw_scores, logits, cafe_stats, idx2info):
    result = []
    for _, row in cafe_stats.iterrows():
        idx  = int(row["cafe_idx"])
        info = idx2info.get(idx, {})
        result.append({
            "cafe_idx"    : idx,
            "avg_score"   : float(row["avg_score"]),
            "review_count": int(row["review_count"]),
            "gnn_score"   : float(raw_scores[idx]),   # 顯示用（0~1，好讀）
            "gnn_logit"   : float(logits[idx]),       # 排序用（保留解析度）
            "name"        : info.get("name", f"#{idx}"),
            "address"     : info.get("address", ""),
            "cost"        : info.get("cost", ""),
            "phone"       : info.get("phone", ""),
            "website"     : info.get("website", ""),
            "review_tags" : info.get("review_tags", []),
            "google_url"  : info.get("google_url", ""),
        })
    return result


def _passes_hard_filters(cafe, filters):
    """Q9 勾選的條件（寵物友善／好停車／晚間營業）比對店家的 review_tags。"""
    if not filters:
        return True
    tags_text = " ".join(cafe.get("review_tags", []))
    for flag, keywords in HARD_FILTER_TAGS.items():
        if filters.get(flag) and not any(kw in tags_text for kw in keywords):
            return False
    return True


def _apply_hard_filters(all_cafes, filters):
    """
    套用 Q9 條件。回傳 (候選清單, 保證入選的 idx 集合, 是否放寬)。

    符合的店家湊不滿一次推薦時要放寬，但不是把條件整個丟掉——
    真的符合的那幾家仍然保證入選，只用其他好店把名額補滿。
    直接退回「完全不篩」等於無視使用者勾的條件。

    提醒：這支腳本比對的 review_tags 是從評論抽出來的詞，不是店家屬性
    （56 家裡只有 2 家含「寵物」、0 家含「停車」與「夜」），
    所以實務上幾乎一定會走到放寬那條路，Q9 的效果很有限。
    網站端改從資料庫取（services/cafe_facts.py），寵物友善有 20 家、晚間營業 12 家。
    """
    if not filters or not any(filters.values()):
        return all_cafes, set(), False
    kept = [c for c in all_cafes if _passes_hard_filters(c, filters)]
    if len(kept) < TIER1_PICK + TIER2_PICK:
        return all_cafes, {c["cafe_idx"] for c in kept}, True
    return kept, set(), False


def _tiered_sample(all_cafes, exclude_idxs=None, must_include=None):
    """
    分層抽樣：精選（>= TIER1_THRESHOLD）抽 3 + 優質抽 2，不足時互補。

    must_include — 硬條件真的符合的店家，一定入選。
    """
    exclude_idxs = exclude_idxs or set()
    must_include = must_include or set()

    candidates = [c for c in all_cafes if c["cafe_idx"] not in exclude_idxs]

    # 用 logit 排序而不是 gnn_score：後者飽和成 1.0 的家數太多，
    # 排出來的前段全是同分，抽獎池會退化成「原始順序的前八家」
    rank = lambda c: c["gnn_logit"]

    locked = sorted([c for c in candidates if c["cafe_idx"] in must_include],
                    key=rank, reverse=True)[:TIER1_PICK + TIER2_PICK]
    locked_ids = {c["cafe_idx"] for c in locked}
    candidates = [c for c in candidates if c["cafe_idx"] not in locked_ids]

    tier1 = sorted([c for c in candidates if c["avg_score"] >= TIER1_THRESHOLD],
                   key=rank, reverse=True)
    tier2 = sorted([c for c in candidates
                    if TIER2_MIN <= c["avg_score"] < TIER1_THRESHOLD],
                   key=rank, reverse=True)

    remaining = max(0, TIER1_PICK + TIER2_PICK - len(locked))
    pick1 = min(TIER1_PICK, remaining)
    pick2 = remaining - pick1

    result = list(locked)
    result += random.sample(tier1[:TIER1_POOL_SIZE],
                            min(pick1, len(tier1[:TIER1_POOL_SIZE])))
    result += random.sample(tier2[:TIER2_POOL_SIZE],
                            min(pick2, len(tier2[:TIER2_POOL_SIZE])))

    # 補位要把兩層都納入來源：只從 tier1 撈的話，
    # tier1 太少而 tier2 很多時會回傳不足 5 家（實測 tier1=1、tier2=9 只回 3 家）
    if len(result) < TIER1_PICK + TIER2_PICK:
        chosen_ids = {c["cafe_idx"] for c in result}
        extra = [c for c in tier1 + tier2 if c["cafe_idx"] not in chosen_ids]
        need  = TIER1_PICK + TIER2_PICK - len(result)
        result.extend(extra[:need])

    return sorted(result, key=rank, reverse=True), tier1, tier2


# ══════════════════════════════════════════════════════════
# 舊用戶路徑
# ══════════════════════════════════════════════════════════
def recommend_existing_user(user_id, model, data, user2idx, df, cafe_stats, idx2info):
    if user_id not in user2idx:
        print(f"找不到使用者 {user_id}")
        return None, None, None

    user_idx = user2idx[user_id]

    with torch.no_grad():
        z            = model.encode(data["user"].x, data)
        user_vec_128 = z["user"][user_idx]
        raw_scores, logits = model.get_all_cafe_scores(user_vec_128, z["cafe"])

    visited   = set(df[df["user_idx"] == user_idx]["cafe_idx"].tolist())
    all_cafes = _build_cafe_list(raw_scores, logits, cafe_stats, idx2info)
    return _tiered_sample(all_cafes, exclude_idxs=visited)


# ══════════════════════════════════════════════════════════
# 新用戶路徑（含動態接邊）
# ══════════════════════════════════════════════════════════
def recommend_new_user(quiz_scores, model, data, cafe_stats, idx2info,
                       filters=None, exclude_idxs=None,
                       top_k=NEW_USER_TOP_K, verbose=True):
    """
    新用戶完整路徑：
      1. 五維分數 → quiz_projector → projected_384
      2. projected_384 和全部 2286 個 BERT 向量做 cosine sim → 取 top_k 接邊
      3. 把新用戶（idx = n_users）插入圖，補上 user↔user 雙向邊
      4. 用「含新用戶的臨時圖」跑 HGT → 新用戶真正收到鄰居訊息
      5. 取新用戶的 128 維 embedding → predictor → 對 56 間店打分
      6. 套用 Q9 的硬條件（寵物／停車／晚間），再分層抽樣

    filters      — {'pet': bool, 'parking': bool, 'night': bool}，Q9 的勾選結果。
    exclude_idxs — 要排除的 cafe_idx（例如上一輪推過的，想「換一批」時用）。
    verbose      — 印接邊資訊；當成模組被匯入時傳 False，不要污染呼叫端的輸出。
    """
    max_s = max(quiz_scores.values()) if max(quiz_scores.values()) > 0 else 1
    vec   = torch.tensor([[quiz_scores[d] / max_s for d in DIMS]],
                         dtype=torch.float).to(DEVICE)  # (1, 5)

    with torch.no_grad():
        # Step 1：五維 → 384 維
        projected_384 = model.quiz_projector(vec)           # (1, 384)

    # Step 2+3：計算 cosine sim，補邊，建臨時圖
    tmp_data, new_idx, neighbor_idxs, neighbor_sims = insert_new_user_into_graph(
        projected_384, data, top_k=top_k
    )
    if verbose:
        print(f"  [接邊] 新用戶與 {len(neighbor_idxs)} 名相似使用者連線")
        print(f"         相似度範圍：{neighbor_sims[-1]:.4f} ~ {neighbor_sims[0]:.4f}")

    with torch.no_grad():
        # Step 4：用臨時圖跑 HGT
        #   new_user_x 已包含新用戶在最後一列，encode 會一起處理
        z = model.encode(tmp_data["user"].x, tmp_data)     # {"user":(n+1,128), "cafe":(m,128)}

        # Step 5：取新用戶的 embedding → 對所有咖啡廳打分
        new_user_128 = z["user"][new_idx]                   # (128,)
        raw_scores, logits = model.get_all_cafe_scores(new_user_128, z["cafe"])

    all_cafes = _build_cafe_list(raw_scores, logits, cafe_stats, idx2info)
    kept, must_include, relaxed = _apply_hard_filters(all_cafes, filters)
    if verbose and relaxed:
        print(f"  [條件] 完全符合 Q9 條件的只有 {len(must_include)} 家，"
              f"這幾家保證入選，其餘名額放寬")
    return _tiered_sample(kept, exclude_idxs=exclude_idxs,
                          must_include=must_include)


# ══════════════════════════════════════════════════════════
# 輸出
# ══════════════════════════════════════════════════════════
def print_recommendations(result, mode_label):
    print(f"\n{'=' * 60}")
    print(f"  為你推薦的花蓮咖啡廳（{mode_label}，共 {len(result)} 間）")
    print("=" * 60)

    for rank, cafe in enumerate(result, 1):
        is_top     = cafe["avg_score"] >= TIER1_THRESHOLD
        tier_label = "精選推薦" if is_top else "優質推薦"
        stars_full = int(round(cafe["avg_score"]))
        stars_str  = "★" * stars_full + "☆" * (5 - stars_full)
        tags       = cafe["review_tags"][:5]
        tags_str   = "  #".join(tags)

        print(f"\n  {'─' * 54}")
        print(f"  {rank}. {cafe['name']}  [{tier_label}]")
        print(f"     {stars_str}  平均 {cafe['avg_score']:.2f} 分（{cafe['review_count']} 則評論）")
        print(f"     GNN 推薦分數：{cafe['gnn_score']:.4f}")
        if cafe["address"]:    print(f"     地址：{cafe['address']}")
        if cafe["cost"]:       print(f"     消費：{cafe['cost']}")
        if cafe["phone"]:      print(f"     電話：{cafe['phone']}")
        if tags_str:           print(f"     標籤：#{tags_str}")
        if cafe["google_url"]: print(f"     地圖：{cafe['google_url']}")
        if cafe["website"]:    print(f"     網站：{cafe['website']}")

    print(f"\n{'─' * 60}")
    print(f"  精選（>= {TIER1_THRESHOLD} 分）從最高分前 {TIER1_POOL_SIZE} 間抽 {TIER1_PICK} 間")
    print(f"  優質（{TIER2_MIN}~{TIER1_THRESHOLD} 分）從最高分前 {TIER2_POOL_SIZE} 間抽 {TIER2_PICK} 間")


def get_title(scores):
    sorted_dims = sorted(DIMS, key=lambda d: scores[d], reverse=True)
    top1, top2  = sorted_dims[0], sorted_dims[1]
    t1, t2      = scores[top1], scores[top2]
    if abs(t1 - t2) <= 1 and t1 > 0:
        pair = tuple(sorted([top1, top2]))
        if pair == ("env", "work"): return "【在靈感邊界流浪的游牧創作者】"
        if pair == ("cp", "taste"): return "【生活防線背後的老饕精算師】"
    if t1 == 0 or (max(scores.values()) - min(scores.values()) <= 1):
        return "【隨遇而安的島嶼日常散策者】"
    return {
        "work":   "【時空邊界的精神築牆師】",
        "env":    "【日常碎片的視覺採集者】",
        "social": "【人間煙火的溫度敘事者】",
        "taste":  "【風味象限的靈魂品鑑家】",
        "cp":     "【生活分寸的實用主義哲學家】",
    }[top1]


def run_quiz():
    scores  = {d: 0 for d in DIMS}
    filters = {"pet": False, "parking": False, "night": False}

    print("\n" + "=" * 60)
    print("啡你莫屬 — 個人化咖啡廳偏好測驗")
    print("=" * 60)

    for q in QUIZ:
        print(f"\n{q['q']}\n")
        for key, text, _ in q["options"]:
            print(f"  [{key}] {text}")
        while True:
            ans = input("\n你的選擇（A/B/C）：").strip().upper()
            matched = [o for o in q["options"] if o[0] == ans]
            if matched:
                for k, v in matched[0][2].items():
                    scores[k] += v
                break
            print("  請輸入 A、B 或 C")

    print("\nQ9【最後的小細節】可複選，輸入數字（例如：1 3），不選請按 Enter\n")
    for key, text in Q9_OPTIONS:
        print(f"  [{key}] {text}")
    q9 = input("\n你的選擇：").strip()
    if "1" in q9: filters["pet"]     = True
    if "2" in q9: filters["parking"] = True
    if "3" in q9: filters["night"]   = True
    return scores, filters


# ══════════════════════════════════════════════════════════
# 主程式
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("載入資料與模型...")
    data, user2idx, cafe2idx, df, idx2info, cafe_stats = load_all()
    model = load_model(data)
    print("✅ 載入完成\n")

    print("=" * 60)
    print("請問你是第一次使用本系統嗎？")
    print("  [1] 是，我是新訪客（做心理測驗）")
    print("  [2] 我有帳號（輸入使用者 ID）")
    mode = input("\n請選擇（1/2）：").strip()

    if mode == "2":
        user_id = input("請輸入你的使用者 ID：").strip()
        result, _tier1, _tier2 = recommend_existing_user(
            user_id, model, data, user2idx, df, cafe_stats, idx2info
        )
        if result is not None:
            print_recommendations(result, mode_label=f"GNN 路徑｜使用者 {user_id}")
    else:
        quiz_scores, filters = run_quiz()

        print("\n" + "=" * 60)
        print("你的偏好向量：")
        for d in DIMS:
            bar = "█" * quiz_scores[d]
            print(f"  {DIM_NAMES[d]:6s}：{bar} ({quiz_scores[d]})")
        print(f"\n你的咖啡廳人格：{get_title(quiz_scores)}")

        chosen = [name for flag, name in
                  (("pet", "寵物友善"), ("parking", "好停車"), ("night", "晚間營業"))
                  if filters[flag]]
        if chosen:
            print(f"\n額外條件：{'、'.join(chosen)}")

        result, _tier1, _tier2 = recommend_new_user(
            quiz_scores, model, data, cafe_stats, idx2info, filters=filters
        )
        print_recommendations(result, mode_label=f"心理測驗 + GNN（接 top-{NEW_USER_TOP_K} 邊）")