"""
Step 2: 產生 BERT 向量
- 使用 sentence-transformers 的多語言模型（支援繁體中文）
- 為每個使用者和每間咖啡廳產生向量
- 儲存成 .npy 檔案給 GNN 用

安裝指令（只需執行一次）：
    pip install sentence-transformers
"""

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

# ── 1. 載入模型 ───────────────────────────────────────────
# paraphrase-multilingual-MiniLM-L12-v2：
#   - 支援繁體中文
#   - 輸出 384 維向量
#   - 速度快、效果好，適合專題規模
print("載入 BERT 模型...")
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# ── 2. 讀取文字資料 ───────────────────────────────────────
user_texts = pd.read_csv("user_texts.csv")
cafe_texts = pd.read_csv("cafe_texts.csv")

# 確保照 idx 排序（順序很重要，之後建圖時 idx 對應要正確）
user_texts = user_texts.sort_values("user_idx").reset_index(drop=True)
cafe_texts = cafe_texts.sort_values("cafe_idx").reset_index(drop=True)

print(f"使用者數: {len(user_texts)}")
print(f"咖啡廳數: {len(cafe_texts)}")

# ── 3. 產生使用者向量 ─────────────────────────────────────
print("\n產生使用者 BERT 向量...")
user_embeddings = model.encode(
    user_texts["combined_text"].tolist(),
    batch_size=64,          # 一次處理 64 筆，視記憶體調整
    show_progress_bar=True,
    convert_to_numpy=True,
)
print(f"使用者向量 shape: {user_embeddings.shape}")  # (使用者數, 384)

# ── 4. 產生咖啡廳向量 ─────────────────────────────────────
print("\n產生咖啡廳 BERT 向量...")
cafe_embeddings = model.encode(
    cafe_texts["combined_text"].tolist(),
    batch_size=64,
    show_progress_bar=True,
    convert_to_numpy=True,
)
print(f"咖啡廳向量 shape: {cafe_embeddings.shape}")  # (咖啡廳數, 384)

# ── 5. 儲存向量 ───────────────────────────────────────────
np.save("user_embeddings.npy", user_embeddings)
np.save("cafe_embeddings.npy", cafe_embeddings)

print("\n✅ 完成！已儲存：")
print("  - user_embeddings.npy  （使用者向量，shape: 使用者數 × 384）")
print("  - cafe_embeddings.npy  （咖啡廳向量，shape: 咖啡廳數 × 384）")
