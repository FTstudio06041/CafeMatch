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

    # === 心理測驗邏輯 ===
    quiz_consent = extracted_data.get("quiz_consent")
    quiz_refused = extracted_data.get("quiz_refused", False)
    
    # 如果使用者剛剛同意做測驗
    if quiz_consent is True:
        return "【任務】使用者已同意進行測驗。請在您的回覆中，確切包含字串：「[SHOW_QUIZ_CARD]」，並可附帶一句簡短自然的引導（例如：太好了！那請點擊下方卡片，我們馬上開始囉～）。絕不要推薦店家，也不要再問其他問題。"
    
    # 如果是第一輪對話，且尚未做過測驗、也沒有拒絕，且收集到的偏好還不足以推薦
    # (如果第一句話就把條件給滿了，就直接推薦，不一定要強迫做測驗)
    if user_rounds == 1 and not quiz_refused and collected_count < strategy["min_dimensions_to_recommend"]:
        return "【任務】請詢問使用者：「為了給您更精準的推薦，您願意先花 1 分鐘做個心理測驗小遊戲嗎？」請用語氣自然的方式發問。"

    # === 停止條件（硬性，不靠 AI 判斷） ===

    # 若已經推薦過，進入推薦後階段
    if has_recommended:
        return "【任務】你已經推薦過咖啡廳了。請回答使用者關於推薦店家的問題，若使用者不滿意或想換口味，可以再推薦其他家。"

    # 條件 1：AI 已問太多次 → 直接推薦
    if question_count >= strategy["max_questions"]:
        return None

    # 條件 2：對話輪數已夠多 → 直接推薦
    if user_rounds >= strategy["recommend_after_rounds"]:
        return None

    # 條件 3：已蒐集到足夠維度 → 直接推薦 (短路條件)
    # 取消了必須 question_count >= 1 的限制
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
    import random
    if next_dim.get("example_prompts"):
        example = random.choice(next_dim["example_prompts"])
    else:
        example = ""

    instruction = (
        f"【任務】使用者目前已透露的偏好：{summary}。\n"
        f"【目前進度】已提問次數：{question_count} / 最大上限：{strategy['max_questions']}。\n"
        f"接下來，你需要幫忙釐清使用者的「{next_dim['label']}」。\n"
        f"請以朋友般的自然口吻，順著聊天的感覺問出這個重點。"
    )

    if example:
        instruction += (
            f"\n\n【重要禁止事項】\n"
            f"絕對不可以原封不動照抄這句話：「{example}」。\n"
            f"請你一定要發揮創意、換句話說，讓每次的問法都不一樣！"
        )

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
