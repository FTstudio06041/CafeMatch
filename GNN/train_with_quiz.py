import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

"""
投影層 + GNN 聯合訓練
目標：讓五維偏好向量投影後，能和對應使用者的 BERT 向量對齊
流程：
  1. 用 LLM/關鍵字從評論推算每位使用者的五維偏好分數（模擬心理測驗）
  2. 訓練投影層（5→384→hidden）讓投影結果靠近真實 BERT embedding
  3. 聯合訓練 GNN，讓整條路徑端對端最佳化
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
from torch_geometric.nn import HGTConv, Linear
from torch_geometric.utils import negative_sampling
from sklearn.model_selection import train_test_split

DEVICE     = torch.device("cuda" if torch.cuda.is_available() else "cpu")
HIDDEN_DIM = 128
NUM_HEADS  = 4
NUM_LAYERS = 2
EPOCHS     = 300
LR         = 0.0005
print(f"使用裝置: {DEVICE}")

# ══════════════════════════════════════════════════════════
# 1. 從評論文字推算使用者的五維偏好分數
#    （模擬「如果這位使用者做了心理測驗，大概會得到什麼分數」）
# ══════════════════════════════════════════════════════════
# 關鍵字對應表：出現在評論裡 → 對應維度加分
KEYWORD_MAP = {
    "work":   ["安靜", "專注", "讀書", "工作", "插座", "wifi", "不限時", "久坐", "筆電"],
    "env":    ["裝潢", "美", "拍照", "採光", "設計", "氛圍", "質感", "老宅", "植栽", "文青"],
    "social": ["熱鬧", "聊天", "朋友", "溫暖", "人情", "老闆", "親切", "活潑", "隨性"],
    "taste":  ["好喝", "手沖", "單品", "烘焙", "風味", "甜點", "職人", "精品", "香"],
    "cp":     ["便宜", "實惠", "划算", "cp", "cp值", "平價", "份量", "飽足", "低消"],
}

def infer_scores_from_reviews(text: str) -> dict:
    """從評論文字關鍵字推算五維分數"""
    scores = {"work": 0, "env": 0, "social": 0, "taste": 0, "cp": 0}
    text_lower = text.lower()
    for dim, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            scores[dim] += text_lower.count(kw)
    # 歸一化到 0~1
    total = sum(scores.values())
    if total > 0:
        scores = {k: v / total for k, v in scores.items()}
    else:
        scores = {k: 0.2 for k in scores}  # 無關鍵字時均分
    return scores

# 讀取使用者評論文字
print("推算使用者偏好分數...")
user_texts = pd.read_csv("user_texts.csv").sort_values("user_idx").reset_index(drop=True)

dims = ["work", "env", "social", "taste", "cp"]
user_quiz_scores = []
for _, row in user_texts.iterrows():
    s = infer_scores_from_reviews(str(row["combined_text"]))
    user_quiz_scores.append([s[d] for d in dims])

# (n_users, 5) 的偏好矩陣
quiz_tensor = torch.tensor(user_quiz_scores, dtype=torch.float).to(DEVICE)
print(f"使用者偏好矩陣 shape: {quiz_tensor.shape}")

# ══════════════════════════════════════════════════════════
# 2. 載入圖與 BERT 向量
# ══════════════════════════════════════════════════════════
print("載入圖...")
data = torch.load("hetero_graph.pt", map_location=DEVICE)

user_bert = data["user"].x  # (n_users, 384) 原始 BERT 向量
cafe_bert = data["cafe"].x  # (n_cafes, 384)

# 切分訓練/驗證/測試邊
edge_index = data["user", "reviews", "cafe"].edge_index
indices    = np.arange(edge_index.shape[1])
train_idx, temp_idx = train_test_split(indices, test_size=0.3, random_state=42)
val_idx,  test_idx  = train_test_split(temp_idx, test_size=0.5, random_state=42)
train_edges = edge_index[:, train_idx]
val_edges   = edge_index[:, val_idx]
test_edges  = edge_index[:, test_idx]

# ══════════════════════════════════════════════════════════
# 3. 定義模型（投影層 + HGT）
# ══════════════════════════════════════════════════════════
class QuizProjector(nn.Module):
    """五維偏好向量 → 384 維（對齊 BERT 空間）"""
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(5, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 384),
        )

    def forward(self, x):
        return self.net(x)


class HGTWithQuiz(nn.Module):
    """
    投影層 + HGT 聯合模型
    使用者輸入：五維偏好向量（而非 BERT 向量）
    咖啡廳輸入：BERT 向量（不變）
    """
    def __init__(self):
        super().__init__()
        # 投影層：把 5 維偏好向量投影到 384 維
        self.quiz_projector = QuizProjector()

        # 輸入投影：384 → hidden_dim
        self.user_proj = Linear(384, HIDDEN_DIM)
        self.cafe_proj = Linear(384, HIDDEN_DIM)

        # HGT 卷積層
        self.convs = nn.ModuleList([
            HGTConv(HIDDEN_DIM, HIDDEN_DIM, data.metadata(), NUM_HEADS)
            for _ in range(NUM_LAYERS)
        ])

        # 預測層
        self.predictor = nn.Sequential(
            nn.Linear(HIDDEN_DIM * 2, HIDDEN_DIM),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(HIDDEN_DIM, 1),
        )

    def get_user_input(self, use_quiz=False, quiz_scores=None):
        """
        use_quiz=False：訓練時用 BERT 向量（有真實評論的使用者）
        use_quiz=True ：推薦時用心理測驗向量（新使用者）
        """
        if use_quiz and quiz_scores is not None:
            return self.quiz_projector(quiz_scores)  # (n, 384)
        else:
            return data["user"].x                    # (n_users, 384)

    def encode(self, user_input):
        x_dict = {
            "user": self.user_proj(user_input),
            "cafe": self.cafe_proj(data["cafe"].x),
        }
        for conv in self.convs:
            x_dict = {k: F.relu(v) for k, v in conv(x_dict, data.edge_index_dict).items()}
        return x_dict

    def decode(self, z, ei):
        u = z["user"][ei[0]]
        c = z["cafe"][ei[1]]
        return self.predictor(torch.cat([u, c], dim=-1)).squeeze(-1)

    def forward(self, ei, use_quiz=False, quiz_scores=None):
        user_input = self.get_user_input(use_quiz, quiz_scores)
        z = self.encode(user_input)
        return self.decode(z, ei)


model     = HGTWithQuiz().to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode="max", patience=20, factor=0.5
)

# ══════════════════════════════════════════════════════════
# 4. 訓練（兩個 loss 聯合優化）
# ══════════════════════════════════════════════════════════
def compute_losses(ei):
    """
    Loss 1 - Link prediction loss：
        預測 user-cafe 的連結是否存在（主要任務）
    Loss 2 - Alignment loss：
        投影層投影結果 ≈ 真實 BERT 向量（讓投影層學會對齊）
    """
    # ── Loss 1：Link Prediction ────────────────────────────
    neg_edge = negative_sampling(
        edge_index=data["user", "reviews", "cafe"].edge_index,
        num_nodes=(data["user"].num_nodes, data["cafe"].num_nodes),
        num_neg_samples=ei.shape[1], method="sparse",
    ).to(DEVICE)

    all_ei  = torch.cat([ei, neg_edge], dim=1)
    labels  = torch.cat([torch.ones(ei.shape[1]),
                         torch.zeros(neg_edge.shape[1])]).to(DEVICE)
    pred    = model(all_ei, use_quiz=False)
    loss_lp = F.binary_cross_entropy_with_logits(pred, labels)

    # ── Loss 2：Alignment（投影向量對齊 BERT 向量）─────────
    projected = model.quiz_projector(quiz_tensor)  # (n_users, 384)
    target    = user_bert                           # (n_users, 384)
    # cosine similarity loss：讓投影方向和 BERT 方向一致
    loss_align = 1 - F.cosine_similarity(projected, target, dim=-1).mean()

    # 總 loss：link prediction 為主，alignment 為輔（權重 0.3）
    total_loss = loss_lp + 0.3 * loss_align
    return total_loss, loss_lp.item(), loss_align.item()


@torch.no_grad()
def evaluate(edges):
    model.eval()
    neg_edge = negative_sampling(
        edge_index=data["user", "reviews", "cafe"].edge_index,
        num_nodes=(data["user"].num_nodes, data["cafe"].num_nodes),
        num_neg_samples=edges.shape[1], method="sparse",
    ).to(DEVICE)
    pos_pred  = torch.sigmoid(model(edges, use_quiz=False))
    neg_pred  = torch.sigmoid(model(neg_edge, use_quiz=False))
    all_pred  = torch.cat([pos_pred, neg_pred])
    all_label = torch.cat([torch.ones(pos_pred.shape[0]),
                           torch.zeros(neg_pred.shape[0])]).to(DEVICE)
    acc = ((all_pred > 0.5) == all_label).float().mean().item()
    return acc, pos_pred.mean().item(), neg_pred.mean().item()


# ── 訓練迴圈 ──────────────────────────────────────────────
print("\n開始聯合訓練...")
best_val_acc = 0

for epoch in range(1, EPOCHS + 1):
    model.train()
    optimizer.zero_grad()
    loss, loss_lp, loss_align = compute_losses(train_edges)
    loss.backward()
    optimizer.step()

    if epoch % 50 == 0:
        val_acc, vp, vn = evaluate(val_edges)
        scheduler.step(val_acc)
        print(f"Epoch {epoch:3d} | Loss {loss.item():.4f} "
              f"(LP:{loss_lp:.4f} Align:{loss_align:.4f}) | "
              f"Val Acc {val_acc:.4f} | Pos {vp:.3f} | Neg {vn:.3f}")
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), "best_model_with_quiz.pt")

# 測試集評估
model.load_state_dict(torch.load("best_model_with_quiz.pt"))
test_acc, tp, tn = evaluate(test_edges)
print(f"\n測試集 Acc: {test_acc:.4f} | Pos: {tp:.3f} | Neg: {tn:.3f}")

# ══════════════════════════════════════════════════════════
# 5. 儲存投影層（推薦時用）
# ══════════════════════════════════════════════════════════
torch.save(model.quiz_projector.state_dict(), "quiz_projector.pt")
torch.save(model.state_dict(), "best_model_with_quiz.pt")
print("\n✅ 已儲存：")
print("  - best_model_with_quiz.pt  （完整模型）")
print("  - quiz_projector.pt        （投影層，推薦時用）")