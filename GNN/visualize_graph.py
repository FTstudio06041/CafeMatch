import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import torch
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import networkx as nx
import random

# ── 修正 Windows 中文字型 ─────────────────────────────────
def get_chinese_font():
    candidates = ["Microsoft JhengHei", "Microsoft YaHei", "DFKai-SB", "MingLiU"]
    for name in candidates:
        for font in fm.fontManager.ttflist:
            if name.lower() in font.name.lower():
                return font.name
    return None

chinese_font = get_chinese_font()
if chinese_font:
    plt.rcParams["font.family"] = chinese_font
    print(f"使用字型: {chinese_font}")
else:
    print("⚠️ 找不到中文字型，標題改用英文")

# ── 設定 ──────────────────────────────────────────────────
SAMPLE_USERS = 40
SAMPLE_CAFES = 20
RANDOM_SEED  = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# ── 1. 載入圖 ─────────────────────────────────────────────
print("載入圖...")
data = torch.load("hetero_graph.pt", map_location="cpu")

n_users = data["user"].num_nodes
n_cafes = data["cafe"].num_nodes
print(f"總使用者數: {n_users}, 總咖啡廳數: {n_cafes}")

# ── 2. 抽樣節點（先抽咖啡廳，再找有連結的使用者）────────
edge_index_uc = data["user", "reviews", "cafe"].edge_index.numpy()
edge_index_uu = data["user", "similar_to", "user"].edge_index.numpy()
edge_index_cc = data["cafe", "similar_to", "cafe"].edge_index.numpy()

# 先抽咖啡廳
sampled_cafes = sorted(random.sample(range(n_cafes), SAMPLE_CAFES))
sampled_cafe_set = set(sampled_cafes)

# 找出評論過這些咖啡廳的使用者，確保圖是連通的
connected_users = set(
    int(edge_index_uc[0, i])
    for i in range(edge_index_uc.shape[1])
    if int(edge_index_uc[1, i]) in sampled_cafe_set
)
sample_size = min(SAMPLE_USERS, len(connected_users))
sampled_users = sorted(random.sample(list(connected_users), sample_size))
sampled_user_set = set(sampled_users)

print(f"抽樣使用者: {len(sampled_users)} 個（皆與抽樣咖啡廳有連結）")
print(f"抽樣咖啡廳: {len(sampled_cafes)} 間")

# ── 3. 建立 NetworkX 圖 ───────────────────────────────────
G = nx.Graph()
for u in sampled_users:
    G.add_node(f"u{u}", node_type="user")
for c in sampled_cafes:
    G.add_node(f"c{c}", node_type="cafe")

# ── 4. 加入邊 ─────────────────────────────────────────────
# user→cafe
uc_edges = []
for i in range(edge_index_uc.shape[1]):
    u, c = int(edge_index_uc[0, i]), int(edge_index_uc[1, i])
    if u in sampled_user_set and c in sampled_cafe_set:
        G.add_edge(f"u{u}", f"c{c}", edge_type="reviews")
        uc_edges.append((f"u{u}", f"c{c}"))

# user↔user
uu_edges = []
seen_uu = set()
for i in range(edge_index_uu.shape[1]):
    u1, u2 = int(edge_index_uu[0, i]), int(edge_index_uu[1, i])
    if u1 in sampled_user_set and u2 in sampled_user_set:
        key = (min(u1, u2), max(u1, u2))
        if key not in seen_uu:
            seen_uu.add(key)
            G.add_edge(f"u{u1}", f"u{u2}", edge_type="user_sim")
            uu_edges.append((f"u{u1}", f"u{u2}"))

# cafe↔cafe
cc_edges = []
seen_cc = set()
for i in range(edge_index_cc.shape[1]):
    c1, c2 = int(edge_index_cc[0, i]), int(edge_index_cc[1, i])
    if c1 in sampled_cafe_set and c2 in sampled_cafe_set:
        key = (min(c1, c2), max(c1, c2))
        if key not in seen_cc:
            seen_cc.add(key)
            G.add_edge(f"c{c1}", f"c{c2}", edge_type="cafe_sim")
            cc_edges.append((f"c{c1}", f"c{c2}"))

print(f"user→cafe 邊: {len(uc_edges)}")
print(f"user↔user 邊: {len(uu_edges)}")
print(f"cafe↔cafe 邊: {len(cc_edges)}")

# ── 5. 畫圖 ───────────────────────────────────────────────
print("畫圖中...")
fig, ax = plt.subplots(figsize=(16, 12))
fig.patch.set_facecolor("#1a1a2e")
ax.set_facecolor("#1a1a2e")

# Spring layout
pos = nx.spring_layout(G, k=1.2, seed=RANDOM_SEED, iterations=80)

# 畫邊
nx.draw_networkx_edges(
    G, pos, edgelist=uc_edges,
    edge_color="#aaaaaa", alpha=0.5, width=0.8, ax=ax
)
nx.draw_networkx_edges(
    G, pos, edgelist=uu_edges,
    edge_color="#4fc3f7", alpha=0.6, width=1.2, style="dashed", ax=ax
)
nx.draw_networkx_edges(
    G, pos, edgelist=cc_edges,
    edge_color="#ffb74d", alpha=0.6, width=1.2, style="dashed", ax=ax
)

# 畫節點
user_nodes = [f"u{u}" for u in sampled_users]
cafe_nodes  = [f"c{c}" for c in sampled_cafes]
nx.draw_networkx_nodes(
    G, pos, nodelist=user_nodes,
    node_color="#4fc3f7", node_size=300, alpha=0.9, ax=ax
)
nx.draw_networkx_nodes(
    G, pos, nodelist=cafe_nodes,
    node_color="#ffb74d", node_size=600, alpha=0.95, ax=ax
)

# 標籤
nx.draw_networkx_labels(
    G, pos,
    labels={f"u{u}": f"U{u}" for u in sampled_users},
    font_size=6, font_color="white", ax=ax
)
nx.draw_networkx_labels(
    G, pos,
    labels={f"c{c}": f"C{c}" for c in sampled_cafes},
    font_size=7, font_color="white", font_weight="bold", ax=ax
)

# 圖例（用英文避免亂碼風險）
legend_elements = [
    mpatches.Patch(color="#4fc3f7", label=f"User node  (n={len(sampled_users)})"),
    mpatches.Patch(color="#ffb74d", label=f"Cafe node  (n={len(sampled_cafes)})"),
    plt.Line2D([0], [0], color="#aaaaaa", linewidth=1.5,
               label=f"User-Cafe review edge  ({len(uc_edges)})"),
    plt.Line2D([0], [0], color="#4fc3f7", linewidth=1.5, linestyle="dashed",
               label=f"User-User similar edge  ({len(uu_edges)})"),
    plt.Line2D([0], [0], color="#ffb74d", linewidth=1.5, linestyle="dashed",
               label=f"Cafe-Cafe similar edge  ({len(cc_edges)})"),
]
ax.legend(
    handles=legend_elements, loc="upper left",
    framealpha=0.3, facecolor="#1a1a2e",
    edgecolor="#555555", labelcolor="white", fontsize=10,
)

# 標題
if chinese_font:
    title = f"啡你莫屬 — 異質圖結構視覺化\n（全圖共 {n_users} 使用者、{n_cafes} 咖啡廳，此處抽樣展示）"
else:
    title = f"Coffee Recommendation — Heterogeneous Graph\n(Total: {n_users} users, {n_cafes} cafes — sampled view)"

ax.set_title(title, color="white", fontsize=14, pad=15)
ax.axis("off")
plt.tight_layout()
plt.savefig("graph_visualization.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
plt.show()
print("✅ 已儲存：graph_visualization.png")