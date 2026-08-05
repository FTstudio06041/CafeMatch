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
    ANSWER_USER_QUESTION_INSTRUCTION,
    CHAT_AFTER_INVITE_INSTRUCTION,
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

def analyze_and_guide(history: list, extracted_data: dict = None,
                      has_quiz: bool = True) -> str | None:
    """
    對話引導的唯一入口。

    分析對話歷史，決定 AI 這一輪應該確認需求，還是邀請使用者按「直接推薦」按鈕。

    注意：推薦只能由使用者按下「直接推薦咖啡廳」按鈕觸發
    （pipeline 收到 force_recommend 時會跳過本函式）；
    本狀態機永遠不會主動回傳「直接推薦」的決策。

    參數:
        history: list[dict] — 對話歷史
        extracted_data: dict — 透過 LLM 萃取出來的偏好
        has_quiz: bool — 是否有心理測驗基礎分數；沒有時要多問幾題才夠

    回傳:
        str — 注入給 AI 的引導指令
    """
    config = _load_config()
    dimensions = config["dimensions"]
    strategy = config["strategy"]

    extracted_data = extracted_data or {}
    # 「都可以／沒特別需求」等明確回答也計入維度（冪等，pipeline 可能已套用過）
    collected = apply_no_preference_answers(history, extracted_data.get("preferences", {}))

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

    latest_user_msg = next(
        (m.get("content", "") for m in reversed(history) if m.get("role") == "user"), ""
    )

    # 使用者在提問而不是回答 → 先正面回答他，這一輪不追問。
    # （防鬼打牆：原本一律當成答案來萃取，使用者反問時仍被硬推下一題。）
    if is_user_question(latest_user_msg):
        return ANSWER_USER_QUESTION_INSTRUCTION

    # 使用者對測驗結果的回饋 → 三級確認門檻：
    #   覺得準       → 基本門檻
    #   有點落差     → 提高門檻，多問幾題
    #   完全不像我   → 測驗資料作廢，幾乎重建輪廓，問最多
    accuracy = detect_accuracy_feedback(history)
    # 沒做過測驗＝完全沒有基礎資料，比照「測驗完全不像我」用最高門檻，
    # 才會跟進度條的目標維度數一致（否則問到一半就停，100% 又變成達不到）
    if not has_quiz or accuracy == 'inaccurate':
        max_questions = strategy.get("inaccurate_max_questions", 6)
        min_dimensions = strategy.get("inaccurate_min_dimensions", 5)
        max_rounds = strategy.get("inaccurate_recommend_after_rounds", 10)
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

    # 找出「還沒問過、也還沒掌握」的維度。
    # 只看 collected 不夠 —— 使用者可能回答了但沒被萃取到（例如講了很含糊的話），
    # 這時若只依賴 collected，同一個維度會被反覆追問。
    asked_keys = get_asked_dimensions(history)
    missing = [
        d for d in dimensions
        if d["key"] not in collected_keys and d["key"] not in asked_keys
    ]

    if (
        question_count >= max_questions        # AI 已問太多次
        or user_rounds >= max_rounds           # 對話輪數已夠多
        or collected_count >= min_dimensions   # 已蒐集到足夠維度
        or not missing                         # 所有維度都已蒐集
    ):
        # 上一輪已經邀請過就別再重複同一句，改成自然聊天
        # （否則使用者每講一句都收到一模一樣的「請按按鈕」）
        if _already_invited(history):
            return CHAT_AFTER_INVITE_INSTRUCTION
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


# 「明確表示沒有偏好」的訊號：這也是一種明確回答，該維度視為已確認
_NO_PREFERENCE_SIGNALS = ('都可以', '沒有', '沒特別', '隨便', '不限', '沒差', '皆可', '不用', 'ok', '可以')


def apply_no_preference_answers(history: list, preferences: dict) -> dict:
    """
    掃描對話中的「AI 提問 → 使用者回答」配對：
    若 AI 針對某維度發問（訊息帶有該維度的快速選項），而使用者明確回答
    「都可以／沒特別需求」等，該維度標記為已確認（值 '不限'）。

    這讓百分比照實反映使用者已明確回答的內容，狀態機也不會重複追問。
    """
    config = _load_config()
    dimensions = config.get("dimensions", [])
    preferences = dict(preferences or {})

    for i in range(len(history) - 1):
        ai_msg = history[i]
        user_msg = history[i + 1]
        if ai_msg.get("role") not in ("ai", "assistant") or user_msg.get("role") != "user":
            continue
        ai_content = ai_msg.get("content", "")
        reply = (user_msg.get("content", "") or "").strip()

        # 使用者的回答必須是簡短且明確的「沒偏好」表述
        if len(reply) > 12 or not any(sig in reply.lower() for sig in _NO_PREFERENCE_SIGNALS):
            continue

        # 比對 AI 這一題問的是哪個維度（訊息中帶有該維度的快速選項）
        for d in dimensions:
            opts = d.get("quick_options") or []
            if len(opts) >= 2 and opts[0] in ai_content and opts[1] in ai_content:
                if not preferences.get(d["key"]):
                    preferences[d["key"]] = ['不限']
                break

    return preferences


# 使用者「在提問／表達意見」而不是在回答的訊號
_QUESTION_MARKS = ('？', '?')
_QUESTION_WORDS = (
    '為什麼', '為何', '幹嘛', '幹嗎', '怎麼', '如何', '哪家', '哪間', '哪一',
    '幾家', '幾間', '多少', '什麼是', '是不是', '可以嗎', '好嗎', '有沒有',
    '能不能', '要問', '問這麼多', '還要問',
)
# 使用者明確要求「直接推薦」：等同按下推薦按鈕
_RECOMMEND_REQUESTS = (
    '直接推薦', '快點推薦', '推薦給我', '先推薦', '給我推薦', '不要問了',
    '別問了', '跳過', '直接給我', '馬上推薦',
)


def _already_invited(history: list) -> bool:
    """
    AI 是否已經請使用者按過推薦按鈕。

    不比對完整按鈕名稱 —— AI 的措辭每次不同（「按下方按鈕」「按下推薦鈕」…），
    只要同時提到「按」和「按鈕／推薦」就算邀請過。
    """
    for m in history or []:
        if m.get("role") not in ("ai", "assistant"):
            continue
        content = m.get("content", "")
        if '按' in content and ('按鈕' in content or '推薦鈕' in content):
            return True
    return False


def wants_recommendation(user_message: str) -> bool:
    """使用者是否明確要求現在就推薦（口頭版的「直接推薦」按鈕）。"""
    text = (user_message or '').strip()
    return any(sig in text for sig in _RECOMMEND_REQUESTS)


def is_user_question(user_message: str) -> bool:
    """
    判斷使用者這句是「提問／表達意見」而不是「回答上一題」。

    這是防鬼打牆的關鍵：原本系統一律把使用者的話當答案來萃取，
    使用者反問時仍被追問下一題，才會出現一直繞圈的感覺。

    判斷順序（先排除確定是回答的情況，再看疑問訊號）：
      1. 就是我們自己給的快速選項 → 回答
      2. 「都可以」這類明確表示沒偏好 → 回答
      3. 極短的附和（好、嗯、ok）→ 回答
      4. 句尾問號、或含疑問詞 → 提問
    """
    text = (user_message or '').strip()
    if not text:
        return False

    config = _load_config()
    known_options = {
        o for d in config.get("dimensions", []) for o in (d.get("quick_options") or [])
    }
    if text in known_options:
        return False
    if text in _NO_PREFERENCE_SIGNALS:
        return False
    if len(text) <= 2:
        return False

    if text.endswith(_QUESTION_MARKS):
        return True
    return any(w in text for w in _QUESTION_WORDS)


def get_target_dimensions(history: list, has_quiz: bool = True) -> int:
    """
    這次對話「打算問到幾個維度」——即偏好掌握度 100% 的目標值。

    依系統對使用者的了解程度分級，越不了解、要確認的維度越多：
      沒做過測驗       → 最高門檻（完全沒有基礎資料，全靠對話）
      說測驗完全不像我 → 最高門檻（測驗資料作廢）
      說有點落差       → 中門檻
      說準／沒表態     → 基本門檻

    前端用這個數字當分母，問完該問的就是 100%，
    而不是固定除以 5（那樣狀態機提早停止時永遠到不了 100%）。
    """
    strategy = _load_config().get("strategy", {})
    if not has_quiz:
        return int(strategy.get("inaccurate_min_dimensions", 5))

    accuracy = detect_accuracy_feedback(history)
    if accuracy == 'inaccurate':
        return int(strategy.get("inaccurate_min_dimensions", 5))
    if accuracy == 'partial':
        return int(strategy.get("doubt_min_dimensions", 4))
    return int(strategy.get("min_dimensions_to_recommend", 3))


# 有測驗基礎分數時，進度條的起始值（代表「測驗已經幫我們認識你一半」）
QUIZ_PROGRESS_BASE = 50


def dimensions_needed_to_recommend(history: list, has_quiz: bool = True) -> int:
    """
    至少要確認幾個維度才允許推薦。

    取目標維度數的一半（無條件進位）：資料太少就推薦，等於亂猜
    —— 實測完全沒有偏好時，模型對不同需求給出的結果幾乎一樣。
    """
    target = get_target_dimensions(history, has_quiz=has_quiz)
    return max(1, -(-target // 2))   # ceil(target / 2)


def is_ready_to_recommend(history: list, collected_dims: int,
                          has_quiz: bool = True) -> bool:
    """
    資料是否足夠推薦。

    兩種情況算足夠：
      1. 已確認的維度達到門檻
      2. 狀態機已經問完該問的（問太多次／輪數夠了），再問也問不出東西
    """
    if collected_dims >= dimensions_needed_to_recommend(history, has_quiz):
        return True

    strategy = _load_config().get("strategy", {})
    accuracy = detect_accuracy_feedback(history)
    if not has_quiz or accuracy == 'inaccurate':
        max_questions = strategy.get("inaccurate_max_questions", 6)
        max_rounds = strategy.get("inaccurate_recommend_after_rounds", 10)
    elif accuracy == 'partial':
        max_questions = strategy.get("doubt_max_questions", 5)
        max_rounds = strategy.get("doubt_recommend_after_rounds", 8)
    else:
        max_questions = strategy.get("max_questions", 4)
        max_rounds = strategy.get("recommend_after_rounds", 6)

    question_count = _count_ai_questions(history)
    user_rounds = sum(1 for m in history if m.get("role") == "user")
    return question_count >= max_questions or user_rounds >= max_rounds


def classify_instruction(instruction: str):
    """
    把引導指令歸類成 (決策類型, 針對的維度)。

    指令文案會為了調整語氣而變動，因此判讀邏輯集中在這裡；
    pipeline 的除錯輸出與測試都用這個函式，不各自解析字串。

    回傳的決策類型：'確認' | '邀請按鈕' | '推薦後' | '測驗確認' | '未知'
    """
    if not instruction:
        return '直接推薦', None
    if '確認「' in instruction:
        return '確認', instruction.split('確認「')[1].split('」')[0]
    if '你先前已推薦過店家' in instruction:
        return '推薦後', None
    if '偏好已大致掌握' in instruction:
        return '邀請按鈕', None
    if '剛完成心理測驗' in instruction:
        return '測驗確認', None
    if '不是在回答你的問題' in instruction:
        return '回答提問', None
    if '不要再重複那句邀請' in instruction:
        return '邀請後閒聊', None
    return '未知', None


def get_asked_dimensions(history: list) -> set:
    """
    從對話歷史找出「AI 已經問過哪些維度」。

    判斷依據是 AI 訊息裡的快速選項組（每個維度的選項是固定的），
    命中就代表那一題問過了 —— 不論使用者當時有沒有給出可萃取的答案，
    都不該再問第二次。
    """
    config = _load_config()
    asked = set()
    for m in history or []:
        if m.get("role") not in ("ai", "assistant"):
            continue
        content = m.get("content", "")
        if not content:
            continue
        for d in config.get("dimensions", []):
            if d["key"] in asked:
                continue
            opts = d.get("quick_options") or []
            # 兩個以上選項同時出現才算數，避免單一詞彙誤判
            if sum(1 for o in opts if o and o in content) >= 2:
                asked.add(d["key"])
    return asked


def get_keyword_dimension_map() -> dict:
    """
    回傳 {關鍵字: 維度 key} 對照表（供偏好萃取快篩使用）。
    長關鍵字優先比對，避免短詞先命中造成誤判。
    """
    config = _load_config()
    mapping = {}
    for d in config.get("dimensions", []):
        for kw in d.get("detect_keywords", []):
            if kw:
                mapping.setdefault(kw, d["key"])
    return dict(sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True))


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
