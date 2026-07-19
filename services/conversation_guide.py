"""
conversation_guide.py — 對話引導狀態機

職責：分析對話歷史，判斷使用者已提供了哪些偏好資訊；
     需求不明確時產生「確認需求」指令，確認後的偏好
     回流至此狀態機，由停止條件決定何時直接推薦。

設計原則：
  - 不依賴 Flask、SQLAlchemy、Ollama（純 Python 邏輯）
  - 所有維度定義與策略參數皆從 guide_dimensions.json 讀取
  - 防迴圈機制由程式碼硬性控制，不依賴 AI 自行判斷
"""

import json
import os
import random

from config.prompts import (
    ALREADY_RECOMMENDED_INSTRUCTION,
    READY_TO_RECOMMEND_INSTRUCTION,
    get_confirmation_instruction
)
from services.preference_adjuster import detect_accuracy_feedback


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

def analyze_and_guide(history: list, extracted_data: dict = None) -> str | None:
    """
    對話引導的唯一入口。

    分析對話歷史，決定 AI 這一輪應該確認需求，還是邀請使用者按「直接推薦」按鈕。

    注意：推薦只能由使用者按下「直接推薦咖啡廳」按鈕觸發
    （pipeline 收到 force_recommend 時會跳過本函式）；
    本狀態機永遠不會主動回傳「直接推薦」的決策。

    參數:
        history: list[dict] — 對話歷史
        extracted_data: dict — 透過 LLM 萃取出來的偏好

    回傳:
        str — 注入給 AI 的引導指令
    """
    config = _load_config()
    dimensions = config["dimensions"]
    strategy = config["strategy"]

    extracted_data = extracted_data or {}
    collected = extracted_data.get("preferences", {})

    # 計算收集到的總維度數量
    collected_keys = [k for k, v in collected.items() if v]
    collected_count = len(collected_keys)

    question_count = _count_ai_questions(history)
    user_rounds = sum(1 for m in history if m.get("role") == "user")

    # 檢查是否已經推薦過了（前端會在附有推薦卡片的 AI 歷史訊息加上標記）
    has_recommended = False
    for msg in history:
        if msg.get("role") in ("ai", "assistant"):
            content = msg.get("content", "")
            if "[已推薦店家卡片]" in content or ("推薦" in content and "地址" in content):
                has_recommended = True
                break

    # 已經推薦過 → 進入推薦後階段
    if has_recommended:
        return ALREADY_RECOMMENDED_INSTRUCTION

    # 使用者對測驗結果的回饋 → 三級確認門檻：
    #   覺得準       → 基本門檻
    #   有點落差     → 提高門檻，多問幾題
    #   完全不像我   → 測驗資料作廢，幾乎重建輪廓，問最多
    accuracy = detect_accuracy_feedback(history)
    if accuracy == 'inaccurate':
        max_questions = strategy.get("inaccurate_max_questions", 6)
        min_dimensions = strategy.get("inaccurate_min_dimensions", 4)
        max_rounds = strategy.get("inaccurate_recommend_after_rounds", 9)
    elif accuracy == 'partial':
        max_questions = strategy.get("doubt_max_questions", 5)
        min_dimensions = strategy.get("doubt_min_dimensions", 3)
        max_rounds = strategy.get("doubt_recommend_after_rounds", 7)
    else:
        max_questions = strategy["max_questions"]
        min_dimensions = strategy["min_dimensions_to_recommend"]
        max_rounds = strategy["recommend_after_rounds"]

    # === 確認完成條件（硬性，不靠 AI 判斷）===
    # 達標後不會自動推薦，而是邀請使用者按下「直接推薦咖啡廳」按鈕。

    # 找出尚未確認的維度
    missing = [d for d in dimensions if d["key"] not in collected_keys]

    if (
        question_count >= max_questions        # AI 已問太多次
        or user_rounds >= max_rounds           # 對話輪數已夠多
        or collected_count >= min_dimensions   # 已蒐集到足夠維度
        or not missing                         # 所有維度都已蒐集
    ):
        return READY_TO_RECOMMEND_INSTRUCTION

    # 組裝已知偏好摘要
    summary_parts = []
    for key in collected_keys:
        keywords = collected[key]
        dim_label = next(
            (d["label"] for d in dimensions if d["key"] == key), key
        )
        summary_parts.append(f"{dim_label}：{', '.join(keywords)}")

    summary = "；".join(summary_parts) if summary_parts else "尚無明確偏好"

    # 一次只針對下一個不確定的維度確認（不逐項盤問）
    next_dim = missing[0]
    example_prompts = next_dim.get("example_prompts") or []
    examples = random.sample(example_prompts, min(2, len(example_prompts)))

    # 使用者最後一句話：讓 AI 順著剛剛的回答接話、劇情式推進
    latest_user_msg = next(
        (m.get("content", "") for m in reversed(history) if m.get("role") == "user"), ""
    )

    return get_confirmation_instruction(
        summary=summary,
        next_dim_label=next_dim["label"],
        question_count=question_count,
        max_questions=max_questions,
        latest_user_msg=latest_user_msg[:80],
        examples=examples,
        quick_options=next_dim.get("quick_options")
    )


def get_known_keywords() -> set:
    """回傳所有維度的偵測關鍵字集合（供偏好萃取結果驗證用）。"""
    config = _load_config()
    keywords = set()
    for d in config.get("dimensions", []):
        keywords.update(d.get("detect_keywords", []))
    return keywords


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
        "recommend_after_rounds",
        "doubt_max_questions",
        "doubt_min_dimensions",
        "doubt_recommend_after_rounds",
        "inaccurate_max_questions",
        "inaccurate_min_dimensions",
        "inaccurate_recommend_after_rounds"
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
