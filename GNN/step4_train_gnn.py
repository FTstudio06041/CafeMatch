"""
Step 4: GNN 訓練（Link Prediction）
- 模型：HGT（Heterogeneous Graph Transformer）
- 任務：預測 user 會不會喜歡某間 cafe（link prediction）
- 訓練目標：正樣本（有評論的 user-cafe pair）vs 負樣本（隨機沒評論的 pair）
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from torch_geometric.data import HeteroData
from torch_geometric.nn import HGTConv, Linear
from torch_geometric.utils import negative_sampling
from sklearn.model_selection import train_test_split

# ── 設定 ──────────────────────────────────────────────────
HIDDEN_DIM = 128       # GNN 隱藏層維度
NUM_HEADS = 4          # HGT attention heads 數
NUM_LAYERS = 2         # GNN 層數
EPOCHS = 300        # 訓練回合數
LR = 0.0005          # 學習率
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"使用裝置: {DEVICE}")

# ── 1. 載入圖 ─────────────────────────────────────────────
print("載入圖...")
data = torch.load("hetero_graph.pt")
data = data.to(DEVICE)

# ── 2. 切分訓練/驗證/測試邊 ──────────────────────────────
# 取出 user→cafe 的邊（這是我們要預測的邊）
edge_index = data["user", "reviews", "cafe"].edge_index  # (2, E)
num_edges = edge_index.shape[1]

# 切分成 train 70% / val 15% / test 15%
indices = np.arange(num_edges)
train_idx, temp_idx = train_test_split(indices, test_size=0.3, random_state=42)
val_idx, test_idx = train_test_split(temp_idx, test_size=0.5, random_state=42)

train_edges = edge_index[:, train_idx]
val_edges   = edge_index[:, val_idx]
test_edges  = edge_index[:, test_idx]

print(f"訓練邊: {train_idx.shape[0]}, 驗證邊: {val_idx.shape[0]}, 測試邊: {test_idx.shape[0]}")

# ── 3. 定義 HGT 模型 ──────────────────────────────────────
class HGTRecommender(nn.Module):
    def __init__(self, hidden_dim, num_heads, num_layers, metadata):
        super().__init__()

        # 輸入投影層：把各節點的 BERT 向量（384維）壓縮到 hidden_dim
        self.user_proj = Linear(384, hidden_dim)
        self.cafe_proj = Linear(384, hidden_dim)

        # HGT 卷積層（多層）
        self.convs = nn.ModuleList([
            HGTConv(hidden_dim, hidden_dim, metadata, num_heads)
            for _ in range(num_layers)
        ])

        # 預測層：把 user 和 cafe 的向量串接後預測分數
        self.predictor = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, 1),
        )

    def encode(self, x_dict, edge_index_dict):
        """訊息傳遞，產生每個節點的 embedding"""
        # 投影輸入特徵
        x_dict = {
            "user": self.user_proj(x_dict["user"]),
            "cafe": self.cafe_proj(x_dict["cafe"]),
        }
        # 套用 HGT 卷積層
        for conv in self.convs:
            x_dict = conv(x_dict, edge_index_dict)
            # 對每種節點做 ReLU
            x_dict = {k: F.relu(v) for k, v in x_dict.items()}
        return x_dict

    def decode(self, z_dict, edge_index):
        """給定 user-cafe 邊，預測分數（0~1）"""
        user_emb = z_dict["user"][edge_index[0]]  # (E, hidden)
        cafe_emb = z_dict["cafe"][edge_index[1]]  # (E, hidden)
        combined = torch.cat([user_emb, cafe_emb], dim=-1)  # (E, hidden*2)
        return self.predictor(combined).squeeze(-1)           # (E,)

    def forward(self, data, edge_index):
        z_dict = self.encode(data.x_dict, data.edge_index_dict)
        return self.decode(z_dict, edge_index)


# ── 4. 初始化模型與優化器 ─────────────────────────────────
model = HGTRecommender(
    hidden_dim=HIDDEN_DIM,
    num_heads=NUM_HEADS,
    num_layers=NUM_LAYERS,
    metadata=data.metadata(),
).to(DEVICE)

optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode="max", patience=20, factor=0.5, verbose=True
)
# ── 5. 訓練函數 ───────────────────────────────────────────
def train():
    model.train()
    optimizer.zero_grad()

    # 正樣本：真實存在的 user-cafe 評論邊
    pos_edge = train_edges  # (2, E_train)

    # 負樣本：隨機抽樣不存在的 user-cafe pair（數量和正樣本一樣）
    neg_edge = negative_sampling(
        edge_index=data["user", "reviews", "cafe"].edge_index,
        num_nodes=(data["user"].num_nodes, data["cafe"].num_nodes),
        num_neg_samples=pos_edge.shape[1],
        method="sparse",
    ).to(DEVICE)

    # 合併正負樣本
    edge_label_index = torch.cat([pos_edge, neg_edge], dim=1)
    labels = torch.cat([
        torch.ones(pos_edge.shape[1]),
        torch.zeros(neg_edge.shape[1]),
    ]).to(DEVICE)

    # 前向傳播
    pred = model(data, edge_label_index)

    # Binary Cross Entropy Loss
    loss = F.binary_cross_entropy_with_logits(pred, labels)
    loss.backward()
    optimizer.step()

    return loss.item()


@torch.no_grad()
def evaluate(edges):
    model.eval()

    # 正樣本
    pos_pred = torch.sigmoid(model(data, edges))

    # 負樣本（和正樣本數量相同）
    neg_edge = negative_sampling(
        edge_index=data["user", "reviews", "cafe"].edge_index,
        num_nodes=(data["user"].num_nodes, data["cafe"].num_nodes),
        num_neg_samples=edges.shape[1],
        method="sparse",
    ).to(DEVICE)
    neg_pred = torch.sigmoid(model(data, neg_edge))

    # AUC 計算（正樣本分數 > 負樣本分數的比例）
    # 簡單版：正樣本平均分數 vs 負樣本平均分數
    pos_mean = pos_pred.mean().item()
    neg_mean = neg_pred.mean().item()

    # 用 threshold=0.5 計算 accuracy
    all_pred = torch.cat([pos_pred, neg_pred])
    all_label = torch.cat([
        torch.ones(pos_pred.shape[0]),
        torch.zeros(neg_pred.shape[0]),
    ]).to(DEVICE)
    acc = ((all_pred > 0.5) == all_label).float().mean().item()

    return acc, pos_mean, neg_mean


# ── 6. 訓練迴圈 ───────────────────────────────────────────
print("\n開始訓練...")
best_val_acc = 0
best_epoch = 0

for epoch in range(1, EPOCHS + 1):
    loss = train()

    if epoch % 10 == 0:
        val_acc, val_pos, val_neg = evaluate(val_edges)
        print(
            f"Epoch {epoch:3d} | Loss: {loss:.4f} | "
            f"Val Acc: {val_acc:.4f} | "
            f"Pos score: {val_pos:.3f} | Neg score: {val_neg:.3f}"
        )
        scheduler.step(val_acc)  # 讓 scheduler 根據 val_acc 調整 lr
        # 儲存最好的模型
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch
            torch.save(model.state_dict(), "best_model.pt")

# ── 7. 測試集評估 ─────────────────────────────────────────
print(f"\n最佳模型來自 Epoch {best_epoch}（Val Acc: {best_val_acc:.4f}）")
model.load_state_dict(torch.load("best_model.pt"))
test_acc, test_pos, test_neg = evaluate(test_edges)
print(f"測試集 Acc: {test_acc:.4f} | Pos score: {test_pos:.3f} | Neg score: {test_neg:.3f}")

# ── 8. 儲存最終 embedding（推薦時用）─────────────────────
print("\n儲存節點 embedding...")
model.eval()
with torch.no_grad():
    z_dict = model.encode(data.x_dict, data.edge_index_dict)
    torch.save(z_dict, "node_embeddings.pt")

print("\n✅ 訓練完成！已儲存：")
print("  - best_model.pt        （最佳模型權重）")
print("  - node_embeddings.pt   （訓練後的節點向量，推薦時用）")
