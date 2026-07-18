import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

"""
功能一：統計各類型邊的連線數
功能二：比較 HGT / GAT / GraphSAGE 三個模型效果
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
import time
from torch_geometric.data import HeteroData                        # 建立異質圖
from torch_geometric.nn import HGTConv, GATConv, SAGEConv          # 三種 GNN 層
from torch_geometric.nn import Linear, to_hetero, HeteroConv       # 工具函數
from torch_geometric.utils import negative_sampling                # 負樣本採樣
from sklearn.model_selection import train_test_split               # 切分資料集

# ══════════════════════════════════════════════════════════
# 功能一：統計各類型邊的連線數
# ══════════════════════════════════════════════════════════
print("=" * 60)
print("功能一：各類型邊的連線數統計")
print("=" * 60)

data = torch.load("hetero_graph.pt", map_location="cpu")

uc_count = data["user", "reviews",    "cafe"].edge_index.shape[1]
uu_count = data["user", "similar_to", "user"].edge_index.shape[1]
cc_count = data["cafe", "similar_to", "cafe"].edge_index.shape[1]

print(f"\n節點數")
print(f"  使用者節點：{data['user'].num_nodes} 個")
print(f"  咖啡廳節點：{data['cafe'].num_nodes} 個")

print(f"\n邊的連線數")
print(f"  使用者 → 咖啡廳（評論邊）：{uc_count} 條")
print(f"  使用者 ↔ 使用者（相似邊）：{uu_count} 條")
print(f"  咖啡廳 ↔ 咖啡廳（相似邊）：{cc_count} 條")
print(f"  總計：{uc_count + uu_count + cc_count} 條")

# ══════════════════════════════════════════════════════════
# 功能二：多模型比較
# ══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("功能二：多模型比較")
print("=" * 60)

# 各模型使用的 package 說明
package_info = {
    "HGT": {
        "package": "torch_geometric.nn.HGTConv",
        "特點": "專為異質圖設計，對每種邊類型學習獨立 attention 權重",
    },
    "GAT": {
        "package": "torch_geometric.nn.GATConv + to_hetero",
        "特點": "原本為同質圖設計，透過 to_hetero 轉成異質圖版本",
    },
    "GraphSAGE": {
        "package": "torch_geometric.nn.SAGEConv + to_hetero",
        "特點": "原本為同質圖設計，透過 to_hetero 轉成異質圖版本，以鄰居平均聚合",
    },
}

for name, info in package_info.items():
    print(f"\n  {name}")
    print(f"    套件：{info['package']}")
    print(f"    特點：{info['特點']}")

# ── 設定 ──────────────────────────────────────────────────
HIDDEN_DIM = 128
NUM_HEADS  = 4
NUM_LAYERS = 2
EPOCHS     = 300
LR         = 0.0005
DEVICE     = torch.device("cuda" if torch.cuda.is_available() else "cpu")
data       = data.to(DEVICE)
print(f"\n使用裝置: {DEVICE}")

# ── 切分資料集 ────────────────────────────────────────────
edge_index = data["user", "reviews", "cafe"].edge_index
indices    = np.arange(edge_index.shape[1])
train_idx, temp_idx = train_test_split(indices, test_size=0.3, random_state=42)
val_idx,  test_idx  = train_test_split(temp_idx, test_size=0.5, random_state=42)
train_edges = edge_index[:, train_idx]
val_edges   = edge_index[:, val_idx]
test_edges  = edge_index[:, test_idx]

# ── 定義三種模型 ──────────────────────────────────────────
class HGTModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.user_proj = Linear(384, HIDDEN_DIM)
        self.cafe_proj = Linear(384, HIDDEN_DIM)
        self.convs = nn.ModuleList([
            HGTConv(HIDDEN_DIM, HIDDEN_DIM, data.metadata(), NUM_HEADS)
            for _ in range(NUM_LAYERS)
        ])
        self.predictor = nn.Sequential(
            nn.Linear(HIDDEN_DIM * 2, HIDDEN_DIM), nn.ReLU(),
            nn.Dropout(0.3), nn.Linear(HIDDEN_DIM, 1),
        )

    def encode(self, x_dict, edge_index_dict):
        x_dict = {"user": self.user_proj(x_dict["user"]),
                  "cafe": self.cafe_proj(x_dict["cafe"])}
        for conv in self.convs:
            x_dict = {k: F.relu(v) for k, v in conv(x_dict, edge_index_dict).items()}
        return x_dict

    def decode(self, z, ei):
        return self.predictor(torch.cat([z["user"][ei[0]], z["cafe"][ei[1]]], dim=-1)).squeeze(-1)

    def forward(self, data, ei):
        return self.decode(self.encode(data.x_dict, data.edge_index_dict), ei)


class GATModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.user_proj = Linear(384, HIDDEN_DIM)
        self.cafe_proj = Linear(384, HIDDEN_DIM)
        # HeteroConv：對每種邊類型指定一個獨立的 conv
        self.convs = nn.ModuleList([
            HeteroConv({
                ("user", "reviews",    "cafe"): GATConv(HIDDEN_DIM, HIDDEN_DIM // NUM_HEADS, heads=NUM_HEADS, add_self_loops=False),
                ("cafe", "reviewed_by","user"): GATConv(HIDDEN_DIM, HIDDEN_DIM // NUM_HEADS, heads=NUM_HEADS, add_self_loops=False),
                ("user", "similar_to", "user"): GATConv(HIDDEN_DIM, HIDDEN_DIM // NUM_HEADS, heads=NUM_HEADS, add_self_loops=False),
                ("cafe", "similar_to", "cafe"): GATConv(HIDDEN_DIM, HIDDEN_DIM // NUM_HEADS, heads=NUM_HEADS, add_self_loops=False),
            }, aggr="sum")
            for _ in range(NUM_LAYERS)
        ])
        self.predictor = nn.Sequential(
            nn.Linear(HIDDEN_DIM * 2, HIDDEN_DIM), nn.ReLU(),
            nn.Dropout(0.3), nn.Linear(HIDDEN_DIM, 1),
        )

    def encode(self, x_dict, edge_index_dict):
        x_dict = {"user": self.user_proj(x_dict["user"]),
                  "cafe": self.cafe_proj(x_dict["cafe"])}
        for conv in self.convs:
            x_dict = {k: F.relu(v) for k, v in conv(x_dict, edge_index_dict).items()}
        return x_dict

    def decode(self, z, ei):
        return self.predictor(torch.cat([z["user"][ei[0]], z["cafe"][ei[1]]], dim=-1)).squeeze(-1)

    def forward(self, data, ei):
        return self.decode(self.encode(data.x_dict, data.edge_index_dict), ei)


class SAGEModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.user_proj = Linear(384, HIDDEN_DIM)
        self.cafe_proj = Linear(384, HIDDEN_DIM)
        self.convs = nn.ModuleList([
            HeteroConv({
                ("user", "reviews",    "cafe"): SAGEConv(HIDDEN_DIM, HIDDEN_DIM),
                ("cafe", "reviewed_by","user"): SAGEConv(HIDDEN_DIM, HIDDEN_DIM),
                ("user", "similar_to", "user"): SAGEConv(HIDDEN_DIM, HIDDEN_DIM),
                ("cafe", "similar_to", "cafe"): SAGEConv(HIDDEN_DIM, HIDDEN_DIM),
            }, aggr="sum")
            for _ in range(NUM_LAYERS)
        ])
        self.predictor = nn.Sequential(
            nn.Linear(HIDDEN_DIM * 2, HIDDEN_DIM), nn.ReLU(),
            nn.Dropout(0.3), nn.Linear(HIDDEN_DIM, 1),
        )

    def encode(self, x_dict, edge_index_dict):
        x_dict = {"user": self.user_proj(x_dict["user"]),
                  "cafe": self.cafe_proj(x_dict["cafe"])}
        for conv in self.convs:
            x_dict = {k: F.relu(v) for k, v in conv(x_dict, edge_index_dict).items()}
        return x_dict

    def decode(self, z, ei):
        return self.predictor(torch.cat([z["user"][ei[0]], z["cafe"][ei[1]]], dim=-1)).squeeze(-1)

    def forward(self, data, ei):
        return self.decode(self.encode(data.x_dict, data.edge_index_dict), ei)


# ── 訓練 & 評估函數 ───────────────────────────────────────
def train_one_epoch(model, optimizer):
    model.train()
    optimizer.zero_grad()
    neg_edge = negative_sampling(
        edge_index=data["user", "reviews", "cafe"].edge_index,
        num_nodes=(data["user"].num_nodes, data["cafe"].num_nodes),
        num_neg_samples=train_edges.shape[1], method="sparse",
    ).to(DEVICE)
    ei     = torch.cat([train_edges, neg_edge], dim=1)
    labels = torch.cat([torch.ones(train_edges.shape[1]),
                        torch.zeros(neg_edge.shape[1])]).to(DEVICE)
    loss   = F.binary_cross_entropy_with_logits(model(data, ei), labels)
    loss.backward()
    optimizer.step()
    return loss.item()


@torch.no_grad()
def evaluate(model, edges):
    model.eval()
    neg_edge = negative_sampling(
        edge_index=data["user", "reviews", "cafe"].edge_index,
        num_nodes=(data["user"].num_nodes, data["cafe"].num_nodes),
        num_neg_samples=edges.shape[1], method="sparse",
    ).to(DEVICE)
    pos_pred = torch.sigmoid(model(data, edges))
    neg_pred = torch.sigmoid(model(data, neg_edge))
    all_pred  = torch.cat([pos_pred, neg_pred])
    all_label = torch.cat([torch.ones(pos_pred.shape[0]),
                           torch.zeros(neg_pred.shape[0])]).to(DEVICE)
    acc = ((all_pred > 0.5) == all_label).float().mean().item()
    return acc, pos_pred.mean().item(), neg_pred.mean().item()


# ── 跑三個模型 ────────────────────────────────────────────
models_to_run = {
    "HGT":       HGTModel,
    "GAT":       GATModel,
    "GraphSAGE": SAGEModel,
}

results = {}

for name, ModelClass in models_to_run.items():
    print(f"\n{'=' * 60}")
    print(f"訓練：{name}  （{package_info[name]['package']}）")
    print("=" * 60)

    model     = ModelClass().to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", patience=20, factor=0.5)

    best_val_acc = 0
    t0 = time.time()

    for epoch in range(1, EPOCHS + 1):
        loss = train_one_epoch(model, optimizer)
        if epoch % 50 == 0:
            val_acc, vp, vn = evaluate(model, val_edges)
            scheduler.step(val_acc)
            print(f"  Epoch {epoch:3d} | Loss {loss:.4f} | "
                  f"Val Acc {val_acc:.4f} | Pos {vp:.3f} | Neg {vn:.3f}")
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                torch.save(model.state_dict(), f"best_{name}.pt")

    model.load_state_dict(torch.load(f"best_{name}.pt"))
    test_acc, tp, tn = evaluate(model, test_edges)
    elapsed = round(time.time() - t0, 1)

    results[name] = {
        "套件":      package_info[name]["package"],
        "Test Acc":  round(test_acc, 4),
        "Pos Score": round(tp, 4),
        "Neg Score": round(tn, 4),
        "訓練時間":  f"{elapsed}s",
    }
    print(f"\n  ✅ {name} | Test Acc: {test_acc:.4f} | "
          f"Pos: {tp:.3f} | Neg: {tn:.3f} | 耗時: {elapsed}s")

# ── 輸出比較表 ────────────────────────────────────────────
print(f"\n{'=' * 60}")
print("模型比較結果")
print("=" * 60)
df = pd.DataFrame(results).T
print(df.to_string())
df.to_csv("model_comparison.csv", encoding="utf-8-sig")
print("\n✅ 已儲存：model_comparison.csv")