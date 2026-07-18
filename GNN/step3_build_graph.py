"""
Step 3: 建立異質圖（Heterogeneous Graph）
節點類型：
  - user（使用者）：BERT 向量作為特徵
  - cafe（咖啡廳）：BERT 向量作為特徵

邊類型：
  - (user, reviews, cafe)：使用者評論過咖啡廳，權重 = 評分
  - (user, similar_to, user)：兩人共同評論過同間店，權重 = 共同店家數
  - (cafe, similar_to, cafe)：BERT 相似度高的咖啡廳，閾值 = 0.7

安裝指令（只需執行一次）：
    pip install torch torch-geometric scikit-learn
"""

import numpy as np
import pandas as pd
import torch
from torch_geometric.data import HeteroData
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import csr_matrix
import json

# ── 1. 讀取資料 ───────────────────────────────────────────
print("讀取資料...")
df = pd.read_csv("reviews_clean.csv")
user_emb = np.load("user_embeddings.npy")  # (n_users, 384)
cafe_emb = np.load("cafe_embeddings.npy")  # (n_cafes, 384)

n_users = user_emb.shape[0]
n_cafes = cafe_emb.shape[0]
print(f"使用者數: {n_users}, 咖啡廳數: {n_cafes}")

# ── 2. 建立 HeteroData 物件 ───────────────────────────────
data = HeteroData()

# 節點特徵（BERT 向量）
data["user"].x = torch.tensor(user_emb, dtype=torch.float)
data["cafe"].x = torch.tensor(cafe_emb, dtype=torch.float)
data["user"].num_nodes = n_users
data["cafe"].num_nodes = n_cafes

# ── 3. 邊一：user → cafe（評論過）────────────────────────
print("\n建立 user→cafe 邊...")

# 每個 (user, cafe) 取平均評分（同一對可能有多筆評論）
edge_df = df.groupby(["user_idx", "cafe_idx"])["score"].mean().reset_index()

src = torch.tensor(edge_df["user_idx"].values, dtype=torch.long)
dst = torch.tensor(edge_df["cafe_idx"].values, dtype=torch.long)
weights = torch.tensor(edge_df["score"].values, dtype=torch.float)

data["user", "reviews", "cafe"].edge_index = torch.stack([src, dst])
data["user", "reviews", "cafe"].edge_attr = weights.unsqueeze(1)  # (E, 1)

# 反向邊：cafe → user（GNN 訊息傳遞需要）
data["cafe", "reviewed_by", "user"].edge_index = torch.stack([dst, src])
data["cafe", "reviewed_by", "user"].edge_attr = weights.unsqueeze(1)

print(f"  user→cafe 邊數: {src.shape[0]}")

# ── 4. 邊二：user ↔ user（共同評論過同間店）───────────────
print("\n建立 user↔user 邊...")

# 建立 user-cafe 矩陣（稀疏）
user_ids = df["user_idx"].values
cafe_ids = df["cafe_idx"].values
ones = np.ones(len(user_ids))
user_cafe_matrix = csr_matrix(
    (ones, (user_ids, cafe_ids)), shape=(n_users, n_cafes)
)

# 共同評論數 = 矩陣相乘
co_review = (user_cafe_matrix @ user_cafe_matrix.T).toarray()
np.fill_diagonal(co_review, 0)  # 自己和自己不算

# 只保留共同評論 >= 3 間的 user pair（太少共同點意義不大）
threshold = 3
uu_src, uu_dst = np.where(co_review >= threshold)

# 避免重複（只取上三角）
mask = uu_src < uu_dst
uu_src = uu_src[mask]
uu_dst = uu_dst[mask]
uu_weights = co_review[uu_src, uu_dst]

# 雙向邊
all_uu_src = np.concatenate([uu_src, uu_dst])
all_uu_dst = np.concatenate([uu_dst, uu_src])
all_uu_w = np.concatenate([uu_weights, uu_weights])

data["user", "similar_to", "user"].edge_index = torch.tensor(
    np.stack([all_uu_src, all_uu_dst]), dtype=torch.long
)
data["user", "similar_to", "user"].edge_attr = torch.tensor(
    all_uu_w, dtype=torch.float
).unsqueeze(1)

print(f"  user↔user 邊數: {len(all_uu_src)}")

# ── 5. 邊三：cafe ↔ cafe（BERT 語意相似度）────────────────
print("\n建立 cafe↔cafe 邊（計算 cosine similarity，可能需要幾秒）...")

# 計算所有咖啡廳之間的 cosine similarity
sim_matrix = cosine_similarity(cafe_emb)  # (n_cafes, n_cafes)
np.fill_diagonal(sim_matrix, 0)

# 只保留相似度 >= 0.7 的邊
CAFE_SIM_THRESHOLD = 0.7
cc_src, cc_dst = np.where(sim_matrix >= CAFE_SIM_THRESHOLD)
mask = cc_src < cc_dst  # 上三角避免重複
cc_src = cc_src[mask]
cc_dst = cc_dst[mask]
cc_weights = sim_matrix[cc_src, cc_dst]

# 雙向邊
all_cc_src = np.concatenate([cc_src, cc_dst])
all_cc_dst = np.concatenate([cc_dst, cc_src])
all_cc_w = np.concatenate([cc_weights, cc_weights])

data["cafe", "similar_to", "cafe"].edge_index = torch.tensor(
    np.stack([all_cc_src, all_cc_dst]), dtype=torch.long
)
data["cafe", "similar_to", "cafe"].edge_attr = torch.tensor(
    all_cc_w, dtype=torch.float
).unsqueeze(1)

print(f"  cafe↔cafe 邊數: {len(all_cc_src)}")

# ── 6. 儲存圖 ─────────────────────────────────────────────
torch.save(data, "hetero_graph.pt")

print("\n✅ 完成！已儲存：")
print("  - hetero_graph.pt（異質圖）")
print(f"\n圖結構摘要：")
print(data)
