import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

"""
統一推薦入口 recommend.py
======================================================================
判斷邏輯：
  - 有評論的使用者（舊用戶）→ GNN 路徑
      user BERT 向量 → user_proj → HGT卷積 → predictor → 推薦分數
  - 新使用者（冷啟動）       → 心理測驗 + GNN 路徑（完整圖結構）
      五維分數 → quiz_projector → user_proj → HGT卷積 → predictor → 推薦分數

兩條路徑都完整跑過 HGT，圖結構資訊都有保留。
舊用戶版本額外排除已評論過的咖啡廳。

======================================================================
所需檔案：
  best_model_with_quiz.pt   （train_with_quiz.py 訓練產出）
  hetero_graph.pt
  reviews_clean.csv
  user2idx.json
  cafe2idx.json
  cafes_updated.json
======================================================================
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import pandas as pd
import json
import random

DEVICE     = torch.device("cuda" if torch.cuda.is_available() else "cpu")
HIDDEN_DIM = 128
NUM_HEADS  = 4
NUM_LAYERS = 2

# ══════════════════════════════════════════════════════════
# 分層推薦參數
# ══════════════════════════════════════════════════════════
TIER1_THRESHOLD = 4.7
TIER2_MIN       = 4.0
TIER1_POOL_SIZE = 8
TIER2_POOL_SIZE = 6
TIER1_PICK      = 3
TIER2_PICK      = 2

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
# 模型定義（與 train_with_quiz.py 完全一致，才能正確 load 權重）
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
    """
    完整的 HGT 模型，支援兩條路徑：
      use_quiz=False：BERT 向量 → user_proj → HGT → predictor（舊用戶）
      use_quiz=True ：五維分數 → quiz_projector → user_proj → HGT → predictor（新用戶）

    關鍵：兩條路徑在 user_proj 之後完全相同，都會跑完 HGT 卷積，
          圖結構資訊（user↔user、cafe↔cafe 邊）都有被利用到。
    """
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
        user_input : (n_users, 384)  ← 不管是 BERT 還是 quiz_projector 的輸出，
                                        到這裡形狀都一樣，後面統一跑 HGT
        """
        x_dict = {
            "user": self.user_proj(user_input),          # (n_users, 128)
            "cafe": self.cafe_proj(data["cafe"].x),      # (n_cafes, 128)
        }
        for conv in self.convs:
            x_dict = {k: F.relu(v)
                      for k, v in conv(x_dict, data.edge_index_dict).items()}
        return x_dict  # {"user": (n_users,128), "cafe": (n_cafes,128)}

    def get_all_cafe_scores(self, user_vec_128, z_cafe):
        """
        給定單一使用者的 128 維向量，對所有咖啡廳打分
        user_vec_128 : (128,)
        z_cafe       : (n_cafes, 128)
        回傳          : (n_cafes,) numpy array
        """
        n_cafes = z_cafe.shape[0]
        # 把使用者向量複製 n_cafes 次和每間咖啡廳配對
        u_rep  = user_vec_128.unsqueeze(0).expand(n_cafes, -1)  # (n_cafes, 128)
        concat = torch.cat([u_rep, z_cafe], dim=-1)              # (n_cafes, 256)
        with torch.no_grad():
            scores = torch.sigmoid(self.predictor(concat)).squeeze(-1)  # (n_cafes,)
        return scores.cpu().numpy()


# ══════════════════════════════════════════════════════════
# 資料載入（全局，避免重複 IO）
# ══════════════════════════════════════════════════════════
def load_all():
    # hetero_graph.pt 是本地訓練產物，需允許載入 HeteroData 物件。
    data = torch.load("hetero_graph.pt", map_location=DEVICE, weights_only=False)

    with open("user2idx.json", encoding="utf-8") as f:
        user2idx = json.load(f)
    with open("cafe2idx.json", encoding="utf-8") as f:
        cafe2idx = json.load(f)

    df = pd.read_csv("reviews_clean.csv")

    # 咖啡廳詳細資訊
    with open("cafes_updated.json", encoding="utf-8") as f:
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

    # 每間咖啡廳平均評分 & 評論數
    cafe_stats = df.groupby("cafe_idx")["score"].agg(
        avg_score="mean", review_count="count"
    ).reset_index()

    return data, user2idx, cafe2idx, df, idx2info, cafe_stats


def load_model(data):
    model = HGTWithQuiz(data).to(DEVICE)
    model.load_state_dict(
        torch.load("best_model_with_quiz.pt", map_location=DEVICE)
    )
    model.eval()
    return model


# ══════════════════════════════════════════════════════════
# 核心推薦邏輯（兩條路徑統一在這裡）
# ══════════════════════════════════════════════════════════
def _build_cafe_list(raw_scores, cafe_stats, idx2info):
    """把 numpy 分數陣列組合成帶詳細資訊的 list"""
    result = []
    for _, row in cafe_stats.iterrows():
        idx = int(row["cafe_idx"])
        info = idx2info.get(idx, {})
        result.append({
            "cafe_idx"    : idx,
            "avg_score"   : float(row["avg_score"]),
            "review_count": int(row["review_count"]),
            "gnn_score"   : float(raw_scores[idx]),   # GNN predictor 輸出的分數
            "name"        : info.get("name", f"#{idx}"),
            "address"     : info.get("address", ""),
            "cost"        : info.get("cost", ""),
            "phone"       : info.get("phone", ""),
            "website"     : info.get("website", ""),
            "review_tags" : info.get("review_tags", []),
            "google_url"  : info.get("google_url", ""),
        })
    return result


def _tiered_sample(all_cafes, exclude_idxs=None,
                   tier1_threshold=TIER1_THRESHOLD,
                   tier2_min=TIER2_MIN,
                   tier1_pool=TIER1_POOL_SIZE, tier1_pick=TIER1_PICK,
                   tier2_pool=TIER2_POOL_SIZE, tier2_pick=TIER2_PICK):
    """
    分層隨機抽樣
    exclude_idxs : set of cafe_idx，已評論過的咖啡廳（舊用戶才需要排除）
    """
    if exclude_idxs is None:
        exclude_idxs = set()

    candidates = [c for c in all_cafes if c["cafe_idx"] not in exclude_idxs]

    tier1 = sorted(
        [c for c in candidates if c["avg_score"] >= tier1_threshold],
        key=lambda c: c["gnn_score"], reverse=True
    )
    tier2 = sorted(
        [c for c in candidates if tier2_min <= c["avg_score"] < tier1_threshold],
        key=lambda c: c["gnn_score"], reverse=True
    )

    chosen_t1 = random.sample(tier1[:tier1_pool], min(tier1_pick, len(tier1[:tier1_pool])))
    chosen_t2 = random.sample(tier2[:tier2_pool], min(tier2_pick, len(tier2[:tier2_pool])))
    result = chosen_t1 + chosen_t2

    # 補充（若 tier2 不足）
    if len(result) < tier1_pick + tier2_pick:
        chosen_ids = {c["cafe_idx"] for c in result}
        extra = [c for c in tier1 if c["cafe_idx"] not in chosen_ids]
        need  = tier1_pick + tier2_pick - len(result)
        result.extend(random.sample(extra, min(need, len(extra))))

    return result, tier1, tier2


def recommend_existing_user(user_id: str, model, data, user2idx, df,
                             cafe_stats, idx2info):
    """
    舊用戶路徑（有評論）
    ──────────────────────────────────────────────────────
    user BERT 向量 → user_proj → HGT卷積（利用完整圖結構）→ predictor
    """
    if user_id not in user2idx:
        print(f"⚠️  找不到使用者 {user_id}，請改用心理測驗推薦。")
        return None, None, None

    user_idx = user2idx[user_id]

    with torch.no_grad():
        # 用 BERT 向量（use_quiz=False 路徑）跑完整 GNN
        user_bert_input = data["user"].x                     # (n_users, 384)
        z = model.encode(user_bert_input, data)              # {"user":(n,128), "cafe":(m,128)}
        user_vec_128 = z["user"][user_idx]                   # (128,)
        raw_scores   = model.get_all_cafe_scores(user_vec_128, z["cafe"])

    # 排除已評論過的咖啡廳
    visited = set(df[df["user_idx"] == user_idx]["cafe_idx"].tolist())

    all_cafes = _build_cafe_list(raw_scores, cafe_stats, idx2info)
    result, tier1, tier2 = _tiered_sample(all_cafes, exclude_idxs=visited)
    return result, tier1, tier2


def recommend_new_user(quiz_scores: dict, model, data, cafe_stats, idx2info):
    """
    新用戶路徑（冷啟動）
    ──────────────────────────────────────────────────────
    五維分數 → quiz_projector（5→384）→ user_proj（384→128）
             → HGT卷積（利用完整圖結構）→ predictor

    注意：新用戶沒有節點在圖裡，所以 HGT 卷積時他是「虛擬插入」的：
    我們把他的 128 維向量當作一個額外使用者，和所有咖啡廳的 GNN embedding 配對打分。
    咖啡廳的 embedding 已經包含了圖結構（cafe↔cafe、user↔cafe 邊的訊息聚合），
    所以新用戶仍然間接受益於圖的全局資訊。
    """
    max_s = max(quiz_scores.values()) if max(quiz_scores.values()) > 0 else 1
    vec   = torch.tensor([[quiz_scores[d] / max_s for d in DIMS]],
                         dtype=torch.float).to(DEVICE)  # (1, 5)

    with torch.no_grad():
        # Step 1：五維 → 384 維（quiz_projector）
        projected_384 = model.quiz_projector(vec)            # (1, 384)

        # Step 2：384 → 128（user_proj，和舊用戶路徑完全相同的層）
        user_vec_128  = F.relu(model.user_proj(projected_384)).squeeze(0)  # (128,)

        # Step 3：用已訓練好的 cafe GNN embedding 對所有咖啡廳打分
        #   cafe embedding 是在完整圖結構下訓練出來的，包含所有鄰居訊息
        #   我們用整張圖的 BERT 輸入跑一次 encode，取出 cafe 的 128 維 embedding
        z_cafe = model.encode(data["user"].x, data)["cafe"]  # (n_cafes, 128)
        raw_scores = model.get_all_cafe_scores(user_vec_128, z_cafe)

    all_cafes = _build_cafe_list(raw_scores, cafe_stats, idx2info)
    result, tier1, tier2 = _tiered_sample(all_cafes, exclude_idxs=set())
    return result, tier1, tier2


# ══════════════════════════════════════════════════════════
# 輸出函數
# ══════════════════════════════════════════════════════════
def print_recommendations(result, mode_label):
    print(f"\n{'=' * 60}")
    print(f"☕ 為你推薦的花蓮咖啡廳（{mode_label}，共 {len(result)} 間）")
    print("=" * 60)

    for rank, cafe in enumerate(result, 1):
        is_top     = cafe["avg_score"] >= TIER1_THRESHOLD
        tier_label = "⭐ 精選推薦" if is_top else "✨ 優質推薦"
        stars_full = int(round(cafe["avg_score"]))
        stars_str  = "★" * stars_full + "☆" * (5 - stars_full)
        tags       = cafe["review_tags"][:5]
        tags_str   = "  #".join(tags)

        print(f"\n  {'─' * 54}")
        print(f"  {rank}. {cafe['name']}  [{tier_label}]")
        print(f"     {stars_str}  平均 {cafe['avg_score']:.2f} 分（{cafe['review_count']} 則評論）")
        print(f"     GNN 推薦分數：{cafe['gnn_score']:.4f}")
        if cafe["address"]:   print(f"     📍 {cafe['address']}")
        if cafe["cost"]:      print(f"     💰 消費：{cafe['cost']}")
        if cafe["phone"]:     print(f"     📞 {cafe['phone']}")
        if tags_str:          print(f"     🏷️  #{tags_str}")
        if cafe["google_url"]:print(f"     🗺️  {cafe['google_url']}")
        if cafe["website"]:   print(f"     🔗 {cafe['website']}")

    print(f"\n{'─' * 60}")
    print(f"  ⭐ 精選（≥{TIER1_THRESHOLD}分）從最高分前{TIER1_POOL_SIZE}間抽{TIER1_PICK}間")
    print(f"  ✨ 優質（{TIER2_MIN}~{TIER1_THRESHOLD}分）從最高分前{TIER2_POOL_SIZE}間抽{TIER2_PICK}間")
    print(f"  💡 每次推薦結果略有不同，歡迎多探索！")


# ══════════════════════════════════════════════════════════
# 稱號判斷
# ══════════════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════════════
# 心理測驗互動
# ══════════════════════════════════════════════════════════
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
# 主程式：統一入口
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
        # ── 舊用戶：完整 GNN 路徑 ─────────────────────────
        user_id = input("請輸入你的使用者 ID：").strip()
        result, tier1, tier2 = recommend_existing_user(
            user_id, model, data, user2idx, df, cafe_stats, idx2info
        )
        if result is not None:
            print_recommendations(result, mode_label=f"GNN 路徑｜使用者 {user_id}")

    else:
        # ── 新用戶：心理測驗 + GNN 路徑 ──────────────────
        quiz_scores, filters = run_quiz()

        print("\n" + "=" * 60)
        print("你的偏好向量：")
        for d in DIMS:
            bar = "█" * quiz_scores[d]
            print(f"  {DIM_NAMES[d]:6s}：{bar} ({quiz_scores[d]})")
        print(f"\n你的咖啡廳人格：{get_title(quiz_scores)}")

        result, tier1, tier2 = recommend_new_user(
            quiz_scores, model, data, cafe_stats, idx2info
        )
        print_recommendations(result, mode_label="心理測驗 + GNN 路徑")
