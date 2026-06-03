"""
conversation_guide.py — 對話引導狀態機

職責：分析對話歷史，判斷使用者已提供了哪些偏好資訊，
     並產生引導指令告訴 AI「這一輪該做什麼」。

設計原則：
  - 不依賴 Flask、SQLAlchemy、Ollama（純 Python 邏輯）
  - 所有維度定義與策略參數皆從 guide_dimensions.json 讀取
  - 防迴圈機制由程式碼硬性控制，不依賴 AI 自行判斷
"""

import json
import os


# ==========================================
# 快取機制
# ==========================================

_config_cache = None
_config_mtime = 0

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data', 'guide_dimensions.json'
)


# ==========================================
# 公開介面
# ==========================================

def analyze_and_guide(history: list) -> str | None:
    """
    對話引導的唯一入口。

    分析對話歷史，決定 AI 這一輪應該繼續引導提問，還是直接推薦。

    參數:
        history: list[dict] — 對話歷史，格式為
                 [{"role": "user"|"ai", "content": "..."}, ...]

    回傳:
        str  — 注入給 AI 的引導指令（AI 應據此自然地提問）
        None — 不需引導，AI 應直接根據資料庫資料推薦店家
    """
    config = _load_config()
    dimensions = config["dimensions"]
    strategy = config["strategy"]

    collected = _extract_collected_dimensions(history, dimensions)
    question_count = _count_ai_questions(history)
    user_rounds = sum(1 for m in history if m.get("role") == "user")

    # === 停止條件（硬性，不靠 AI 判斷） ===

    # 條件 1：AI 已問太多次 → 直接推薦
    if question_count >= strategy["max_questions"]:
        return None

    # 條件 2：對話輪數已夠多 → 直接推薦
    if user_rounds >= strategy["recommend_after_rounds"]:
        return None

    # 條件 3：已蒐集到足夠維度，且 AI 已至少問過一次 → 直接推薦
    if (len(collected) >= strategy["min_dimensions_to_recommend"]
            and question_count >= 1):
        return None

    # === 產生引導指令 ===

    # 找出尚未蒐集的維度
    missing = [d for d in dimensions if d["key"] not in collected]

    if not missing:
        return None  # 所有維度都已蒐集，直接推薦

    # 組裝已知偏好摘要
    summary_parts = []
    for key, keywords in collected.items():
        dim_label = next(
            (d["label"] for d in dimensions if d["key"] == key), key
        )
        summary_parts.append(f"{dim_label}：{', '.join(keywords)}")

    summary = "；".join(summary_parts) if summary_parts else "尚無明確偏好"

    # 選取下一個要問的維度
    next_dim = missing[0]
    example = next_dim["example_prompts"][0] if next_dim.get("example_prompts") else ""

    instruction = (
        f"使用者目前已透露的偏好：{summary}。\n"
        f"你還不知道他的「{next_dim['label']}」。"
        f"請用自然聊天的口吻，順著對話脈絡問一個相關問題。"
    )

    if example:
        instruction += f"\n參考問法（不要照抄）：{example}"

    return instruction


# ==========================================
# 策略參數管理（供管理後台 API 使用）
# ==========================================

def get_strategy() -> dict:
    """取得當前策略參數"""
    config = _load_config()
    return config.get("strategy", {})


def update_strategy(new_strategy: dict) -> dict:
    """
    更新策略參數並寫回 JSON 檔案。

    只允許更新已知的策略欄位，避免任意寫入。

    參數:
        new_strategy: dict — 要更新的策略欄位與值

    回傳:
        dict — 更新後的完整策略參數
    """
    global _config_cache
    config = _load_config()

    # 只允許更新已知的策略欄位
    allowed_keys = {
        "max_questions",
        "min_dimensions_to_recommend",
        "recommend_after_rounds"
    }

    for key, value in new_strategy.items():
        if key in allowed_keys:
            config["strategy"][key] = int(value)

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    _config_cache = config
    return config["strategy"]


# ==========================================
# 內部輔助函式
# ==========================================

def _load_config() -> dict:
    """
    讀取 guide_dimensions.json 設定檔。

    帶有檔案修改時間快取機制：
    只有當檔案被修改過（或首次載入）時才重新讀取，
    避免每次 API 呼叫都做磁碟 I/O。
    """
    global _config_cache, _config_mtime

    try:
        mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        mtime = 0

    if _config_cache is None or mtime != _config_mtime:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            _config_cache = json.load(f)
        _config_mtime = mtime

    return _config_cache


def _extract_collected_dimensions(
    history: list, dimensions: list
) -> dict:
    """
    掃描所有 user 訊息，比對各維度的 detect_keywords。

    回傳:
        dict — { dimension_key: [matched_keywords] }
        例如 {"purpose": ["工作", "讀書"], "vibe": ["安靜"]}
    """
    collected = {}

    # 將所有使用者訊息合併為一個大字串以便搜尋
    user_texts = [
        m.get("content", "").lower()
        for m in history
        if m.get("role") == "user"
    ]
    combined_text = " ".join(user_texts)

    for dim in dimensions:
        matched = [
            kw for kw in dim.get("detect_keywords", [])
            if kw in combined_text
        ]
        if matched:
            collected[dim["key"]] = matched

    return collected


def _count_ai_questions(history: list) -> int:
    """
    計算 AI 回覆中包含問號的次數，
    作為「AI 已提問次數」的估算。

    同時計算中文問號（？）和英文問號（?）。
    """
    count = 0
    for m in history:
        if m.get("role") in ("ai", "assistant"):
            content = m.get("content", "")
            if "？" in content or "?" in content:
                count += 1
    return count
