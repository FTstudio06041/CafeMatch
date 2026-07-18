"""
Step 1: 資料預處理
- 讀取 CSV
- 過濾掉沒有文字評論的資料
- 只保留評論過 >= 2 間咖啡廳的使用者
- 將 user_id / cafe_id 重新編號（從 0 開始，給 GNN 用）
- 儲存清理後的資料
"""

import pandas as pd
import json

# ── 1. 讀取資料 ──────────────────────────────────────────
df = pd.read_csv(
    "Reviews(1).csv",
    names=["user_id", "cafe_id", "score", "txt"],  # 手動指定欄位名稱
    skiprows=1,                                      # 跳過 header 行
    dtype={"user_id": str, "cafe_id": str, "score": str, "txt": str},
)

print(f"原始資料筆數: {len(df)}")

# ── 2. 過濾空評論 ─────────────────────────────────────────
df = df.dropna(subset=["txt"])          # 移除 txt 是 NaN 的行
df = df[df["txt"].str.strip() != ""]   # 移除 txt 是空字串的行
df["score"] = pd.to_numeric(df["score"], errors="coerce")  # score 轉數字
df = df.dropna(subset=["score"])        # 移除 score 無法轉換的行

print(f"過濾空評論後筆數: {len(df)}")

# ── 3. 只保留評論過 >= 2 間咖啡廳的使用者 ──────────────────
cafe_per_user = df.groupby("user_id")["cafe_id"].nunique()
valid_users = cafe_per_user[cafe_per_user >= 2].index
df = df[df["user_id"].isin(valid_users)]

print(f"過濾後使用者數: {df['user_id'].nunique()}")
print(f"過濾後咖啡廳數: {df['cafe_id'].nunique()}")
print(f"過濾後總評論數: {len(df)}")

# ── 4. 重新編號 user_id / cafe_id（從 0 開始）──────────────
# GNN 需要連續整數 index 作為節點編號
unique_users = sorted(df["user_id"].unique())
unique_cafes = sorted(df["cafe_id"].unique())

user2idx = {uid: i for i, uid in enumerate(unique_users)}
cafe2idx = {cid: i for i, cid in enumerate(unique_cafes)}

df["user_idx"] = df["user_id"].map(user2idx)
df["cafe_idx"] = df["cafe_id"].map(cafe2idx)

print(f"\n使用者節點數: {len(unique_users)}")
print(f"咖啡廳節點數: {len(unique_cafes)}")

# ── 5. 每個使用者的評論合併（給 BERT 用）──────────────────
# 使用者節點特徵：把該使用者所有評論合成一段文字
user_texts = (
    df.groupby("user_idx")["txt"]
    .apply(lambda reviews: " ".join(reviews.tolist()))
    .reset_index()
    .rename(columns={"txt": "combined_text"})
)

# 咖啡廳節點特徵：把該咖啡廳所有評論合成一段文字
cafe_texts = (
    df.groupby("cafe_idx")["txt"]
    .apply(lambda reviews: " ".join(reviews.tolist()))
    .reset_index()
    .rename(columns={"txt": "combined_text"})
)

# ── 6. 儲存結果 ───────────────────────────────────────────
df.to_csv("reviews_clean.csv", index=False)
user_texts.to_csv("user_texts.csv", index=False)
cafe_texts.to_csv("cafe_texts.csv", index=False)

# 儲存 mapping（之後推薦時要把 idx 轉回原始 id）
with open("user2idx.json", "w") as f:
    json.dump(user2idx, f, ensure_ascii=False)
with open("cafe2idx.json", "w") as f:
    json.dump(cafe2idx, f, ensure_ascii=False)

print("\n✅ 完成！已儲存：")
print("  - reviews_clean.csv   （清理後的評論）")
print("  - user_texts.csv      （每位使用者的合併評論）")
print("  - cafe_texts.csv      （每間咖啡廳的合併評論）")
print("  - user2idx.json       （使用者 id → 節點編號）")
print("  - cafe2idx.json       （咖啡廳 id → 節點編號）")
