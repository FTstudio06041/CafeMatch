import json
import re
import logging
from config.prompts import (
    PREFERENCE_EXTRACTION_FORMAT,
    PREFERENCE_EXTRACTION_TASK,
    PREFERENCE_EXTRACTION_RULES
)
from config.ai_constants import PREFERENCE_HISTORY_LIMIT, PREFERENCE_EXTRACTION_TIMEOUT
from services.ollama_client import OllamaClient

# LLM 偶爾會憑空生出的泛用詞／佔位詞，不可視為有效偏好
_GENERIC_STOPWORDS = {
    '咖啡', '咖啡廳', '咖啡店', '推薦', '未知', '不確定', '沒有', '無',
    '都可以', '隨便', '不限', '普通', '一般', 'null', 'none', 'n/a'
}


def _sanitize_preferences(prefs, user_text, ai_text):
    """
    驗證 LLM 萃取出的偏好關鍵字，防止憑空捏造或錯誤歸因：
      - 過濾泛用詞／佔位詞
      - 保留「使用者自己說過」的關鍵字
      - 已知維度詞彙若「只出現在 AI 的話裡」（例如 AI 覆述測驗人格描述），
        不可視為使用者偏好——寧可多問一題確認，也不要替使用者作答
    """
    from services.conversation_guide import get_known_keywords
    known = get_known_keywords()

    clean = {}
    for dim, values in (prefs or {}).items():
        if not isinstance(values, list):
            continue
        kept = []
        for v in values:
            if not isinstance(v, str):
                continue
            v = v.strip()
            if not v or v.lower() in _GENERIC_STOPWORDS:
                continue
            if v in user_text or (v in known and v not in ai_text):
                kept.append(v)
        if kept:
            clean[dim] = kept
    return clean


def _rule_extract(user_message: str) -> dict:
    """用維度關鍵字表直接萃取偏好（不呼叫 LLM）。"""
    from services.conversation_guide import get_keyword_dimension_map

    text = (user_message or '').strip()
    prefs = {}
    for kw, dim in get_keyword_dimension_map().items():
        if kw in text and kw.lower() not in _GENERIC_STOPWORDS:
            vals = prefs.setdefault(dim, [])
            # 已被更長的關鍵字涵蓋就不重複收（例如「早午餐」已收則跳過「餐」）
            if not any(kw in existing for existing in vals):
                vals.append(kw)
    return prefs


def extract_preferences(history, user_message, model_name):
    """
    偏好萃取：短訊息走關鍵字快篩（零 LLM 呼叫），其餘交給 LLM。
    這是一個純粹的萃取服務，嚴禁生成推薦結果或使用 RAG。
    """
    # === 快篩路徑 ===
    # 萃取結果本來就會被驗證層限縮成「使用者說過或已知維度詞彙」，
    # 因此關鍵字命中時 LLM 幾乎沒有加值 —— 直接省下一次 LLM 呼叫（每輪數秒）。
    # 只有規則完全落空時，才付錢請 LLM 解讀使用者的自創說法。
    fast = _rule_extract(user_message)
    if fast:
        logging.info(f"[Extraction] 快篩命中，跳過 LLM：{fast}")
        return {"preferences": fast}

    # 組裝供萃取的歷史字串（同時分開累積使用者／AI 的話，供結果驗證）
    history_text = ""
    user_text = ""
    ai_text = ""
    for msg in history[-PREFERENCE_HISTORY_LIMIT:]:
        content = msg.get('content', '')
        if msg.get("role") == "user":
            history_text += f"使用者：{content}\n"
            user_text += content + "\n"
        else:
            history_text += f"助手：{content}\n"
            ai_text += content + "\n"
    history_text += f"使用者：{user_message}\n"
    user_text += user_message + "\n"

    # 組裝 Prompt：將任務指令與輸出格式合併
    prompt = f"{PREFERENCE_EXTRACTION_TASK}\n\n{PREFERENCE_EXTRACTION_RULES}\n\n{PREFERENCE_EXTRACTION_FORMAT}\n\n【對話紀錄】\n{history_text}"

    fallback_result = {
        "preferences": {}
    }

    client = OllamaClient()
    try:
        data = client.generate(model=model_name, prompt=prompt, stream=False, timeout=PREFERENCE_EXTRACTION_TIMEOUT, format="json")
        response_text = data.get("response", "")
        logging.debug(f"[LLM Extraction] Response: {response_text}")

        result = client.extract_json_from_response(response_text)
        if result:
            return {
                "preferences": _sanitize_preferences(result.get("preferences", {}), user_text, ai_text)
            }
        else:
            return fallback_result

    except Exception as e:
        logging.error(f"[LLM Extraction Error]: {e}")
        return fallback_result
