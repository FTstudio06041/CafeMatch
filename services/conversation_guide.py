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
import random

from config.prompts import (
    QUIZ_CONSENT_INSTRUCTION,
    QUIZ_INVITATION_INSTRUCTION,
    ALREADY_RECOMMENDED_INSTRUCTION,
    get_clarification_instruction
)
from config.ai_constants import VAGUE_REQUEST_MAX_LEN


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

    分析對話歷史，決定 AI 這一輪應該繼續引導提問，還是直接推薦。

    參數:
        history: list[dict] — 對話歷史
        extracted_data: dict — 透過 LLM 萃取出來的偏好與狀態

    回傳:
        str  — 注入給 AI 的引導指令
        None — 不需引導，AI 應直接根據資料庫資料推薦店家
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
    ai_rounds = sum(1 for m in history if m.get("role") in ("ai", "assistant"))
    
    # 檢查是否已經推薦過了 (簡單檢查 AI 歷史訊息長度是否較長，或是否包含推薦關鍵字)
    has_recommended = False
    for msg in history:
        if msg.get("role") in ("ai", "assistant"):
            if "推薦" in msg.get("content", "") and "地址" in msg.get("content", ""):
                has_recommended = True
                break

    # === 情境配對 / 推薦決策 ===
    quiz_consent = extracted_data.get("quiz_consent")
    quiz_refused = extracted_data.get("quiz_refused", False)

    # 使用者剛剛同意做情境配對
    if quiz_consent is True:
        return QUIZ_CONSENT_INSTRUCTION

    # 已經推薦過 → 進入推薦後階段
    if has_recommended:
        return ALREADY_RECOMMENDED_INSTRUCTION

    # 判斷這則訊息是否「很籠統」（沒給具體需求）
    latest_user_msg = next(
        (m.get("content", "") for m in reversed(history) if m.get("role") == "user"), ""
    )
    is_vague = _is_vague_request(latest_user_msg, collected_count, dimensions)

    # 使用者已給具體需求（不籠統）→ 直接推薦，不邀請、也不追問
    if not is_vague:
        return None

    # 到這裡代表訊息很籠統：若還沒問過情境配對、也沒拒絕 → 邀請小卡
    quiz_has_been_asked = any(
        ("配對" in m.get("content", "")) or ("測驗" in m.get("content", ""))
        for m in history if m.get("role") in ("ai", "assistant")
    )
    if not quiz_has_been_asked and not quiz_refused:
        return QUIZ_INVITATION_INSTRUCTION

    # === 停止條件（硬性，不靠 AI 判斷） ===

    # 條件 1：AI 已問太多次 → 直接推薦
    if question_count >= strategy["max_questions"]:
        return None

    # 條件 2：對話輪數已夠多 → 直接推薦
    if user_rounds >= strategy["recommend_after_rounds"]:
        return None

    # 條件 3：已蒐集到足夠維度 → 直接推薦 (短路條件)
    if collected_count >= strategy["min_dimensions_to_recommend"]:
        return None

    # === 產生引導指令 ===

    # 找出尚未蒐集的維度
    missing = [d for d in dimensions if d["key"] not in collected_keys]

    if not missing:
        return None  # 所有維度都已蒐集，直接推薦

    # 組裝已知偏好摘要
    summary_parts = []
    for key in collected_keys:
        keywords = collected[key]
        dim_label = next(
            (d["label"] for d in dimensions if d["key"] == key), key
        )
        summary_parts.append(f"{dim_label}：{', '.join(keywords)}")

    summary = "；".join(summary_parts) if summary_parts else "尚無明確偏好"

    # 選取下一個要問的維度
    next_dim = missing[0]
    if next_dim.get("example_prompts"):
        example = random.choice(next_dim["example_prompts"])
    else:
        example = ""

    return get_clarification_instruction(
        summary=summary,
        question_count=question_count,
        max_questions=strategy['max_questions'],
        next_dim_label=next_dim['label'],
        example=example
    )


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





def _is_vague_request(user_message: str, collected_count: int, dimensions: list) -> bool:
    """
    判斷使用者這則訊息是否「很籠統」（沒有給出可據以推薦的具體需求）。
    只有很籠統時才邀請情境配對小卡；只要有任何具體訊號就直接推薦。

    以下任一成立即視為「有具體需求」（回傳 False）：
      1. LLM 已萃取到至少一個偏好維度
      2. 訊息長度超過門檻（長訊息通常帶有需求，即使關鍵字/LLM 沒抓到）
      3. 訊息含任何維度關鍵字（安靜、手沖、平價…）
    """
    if collected_count >= 1:
        return False
    text = (user_message or "").strip()
    if len(text) > VAGUE_REQUEST_MAX_LEN:
        return False
    for d in dimensions or []:
        for kw in d.get("detect_keywords", []):
            if kw and kw in text:
                return False
    return True


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
