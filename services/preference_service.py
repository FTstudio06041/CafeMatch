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

def extract_preferences(history, user_message, model_name):
    """
    呼叫 LLM 進行意圖與偏好萃取，回傳 JSON。
    這是一個純粹的萃取服務，嚴禁生成推薦結果或使用 RAG。
    """
    # 組裝供萃取的歷史字串
    history_text = ""
    for msg in history[-PREFERENCE_HISTORY_LIMIT:]:
        role = "使用者" if msg.get("role") == "user" else "助手"
        history_text += f"{role}：{msg.get('content', '')}\n"
    history_text += f"使用者：{user_message}\n"

    # 組裝 Prompt：將任務指令與輸出格式合併
    prompt = f"{PREFERENCE_EXTRACTION_TASK}\n\n{PREFERENCE_EXTRACTION_RULES}\n\n{PREFERENCE_EXTRACTION_FORMAT}\n\n【對話紀錄】\n{history_text}"

    fallback_result = {
        "preferences": {},
        "quiz_consent": None,
        "quiz_refused": False
    }

    client = OllamaClient()
    try:
        data = client.generate(model=model_name, prompt=prompt, stream=False, timeout=PREFERENCE_EXTRACTION_TIMEOUT, format="json")
        response_text = data.get("response", "")
        logging.debug(f"[LLM Extraction] Response: {response_text}")

        result = client.extract_json_from_response(response_text)
        if result:
            return {
                "preferences": result.get("preferences", {}),
                "quiz_consent": result.get("quiz_consent"),
                "quiz_refused": result.get("quiz_refused", False)
            }
        else:
            return fallback_result

    except Exception as e:
        logging.error(f"[LLM Extraction Error]: {e}")
        return fallback_result
