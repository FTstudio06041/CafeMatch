import json
import re
import logging
from copy import deepcopy
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

PREFERENCE_DIMS = ('purpose', 'vibe', 'taste', 'budget', 'special')

_EXTRACTION_SCHEMA = {
    'type': 'object',
    'properties': {
        'remove_preferences': {
            'type': 'object',
            'properties': {dim: {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 6}
                           for dim in PREFERENCE_DIMS},
            'required': list(PREFERENCE_DIMS), 'additionalProperties': False,
        },
        'evidence': {
            'type': 'object', 'properties': {dim: {'type': 'string'} for dim in PREFERENCE_DIMS},
            'required': list(PREFERENCE_DIMS), 'additionalProperties': False,
        },
        'preferences': {
            'type': 'object',
            'properties': {dim: {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 6}
                           for dim in PREFERENCE_DIMS},
            'required': list(PREFERENCE_DIMS), 'additionalProperties': False,
        },
        'dialogue_act': {'type': 'string', 'enum': ['preferences', 'question', 'chat', 'recommend']},
        'next_dimension': {'enum': [*PREFERENCE_DIMS, None]},
    },
    'required': ['remove_preferences', 'evidence', 'preferences', 'dialogue_act', 'next_dimension'],
    'additionalProperties': False,
}


def is_negative_preference(value):
    """完整的否定條件保留給對話，但不能當成正向標籤加分。"""
    return bool(re.search(
        r'不(?!限|拘|錯)|沒(?:有)?(?:要|想|帶|喝|吃|需要)|無需|避免|排除|怕|過敏',
        value,
    ))


def positive_keywords(preferences):
    values = list(dict.fromkeys(
        value for values in (preferences or {}).values() for value in values
        if isinstance(value, str) and value != '不限' and not is_negative_preference(value)
    ))
    # 完整條件留給對話；標籤比對仍需「安靜」「插座」等可匹配的詞。
    from services.conversation_guide import get_known_keywords
    keywords = get_known_keywords()
    return list(dict.fromkeys(values + [
        keyword for keyword in sorted(keywords)
        if len(keyword) > 1 and any(keyword in value for value in values)
    ]))


def _clause_dimensions(text):
    """以明確詞彙校驗維度歸屬，不丟掉原句中的否定、數字或程度。"""
    from services.conversation_guide import _load_config
    hits = [
        (word, dim['key']) for dim in _load_config()['dimensions']
        for word in dim['detect_keywords'] if word.lower() in text.lower()
    ]
    dims = {
        dim for word, dim in hits
        if not any(word != longer and word in longer for longer, _ in hits)
    }
    if re.search(r'\d+\s*(?:元|塊)', text):
        dims.add('budget')
    return dims


def _sanitize_preferences(prefs, user_text, ai_text, evidence=None, base=None):
    """
    驗證 LLM 萃取出的偏好關鍵字，防止憑空捏造或錯誤歸因：
      - 過濾泛用詞／佔位詞
      - 有本輪原文佐證時，接受語意正規化及仍有效的舊條件
      - 沒有佐證時只接受使用者原文或已確認偏好，不採用助手的推測
    """
    clean = {}
    if not isinstance(prefs, dict):
        return clean
    evidence = evidence if isinstance(evidence, dict) else {}
    for dim, values in (prefs or {}).items():
        if dim not in PREFERENCE_DIMS or not isinstance(values, list):
            continue
        quote = evidence.get(dim)
        grounded = isinstance(quote, str) and bool(quote.strip()) and quote in user_text
        quote_dims = _clause_dimensions(quote) if grounded else set()
        if quote_dims and dim not in quote_dims:
            continue
        kept = []
        for v in values:
            if not isinstance(v, str):
                continue
            v = v.strip()
            if not v or len(v) > 100:
                continue
            if v.lower() in _GENERIC_STOPWORDS and not (grounded and v == '不限'):
                continue
            if grounded or v in user_text:
                kept.append(v)
        if kept:
            clean[dim] = list(dict.fromkeys(kept))[:6]
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


def extract_preferences(history, user_message, model_name, base_preferences=None):
    """
    只有完整命中已知選項才快篩；自由輸入用語意理解更新累積偏好。
    這是一個純粹的萃取服務，嚴禁生成推薦結果或使用 RAG。
    """
    from services.conversation_guide import _load_config, get_known_keywords
    base_preferences = base_preferences or {}
    text = (user_message or '').strip()
    options = {
        option: dim['key'] for dim in _load_config()['dimensions']
        for option in dim.get('quick_options', [])
    }
    fast = {}
    if text in options and text != '沒特別需求':
        dim = options[text]
        fast = {dim: ['不限' if text == '價格不拘' else text]}
    elif text in get_known_keywords() and len(text) > 1:
        fast = _rule_extract(text)
    if fast and not any(base_preferences.get(dim) for dim in fast):
        return {"preferences": fast, "fast_path": True, "dialogue_act": "preferences"}

    # 歷史只提供語境，更新依據必須來自最新訊息。
    history_text = ""
    ai_text = ""
    for msg in history[-min(PREFERENCE_HISTORY_LIMIT, 2):]:
        content = msg.get('content', '')
        if msg.get("role") == "user":
            history_text += f"使用者：{content}\n"
        else:
            history_text += f"助手：{content}\n"
            ai_text += content + "\n"
    history_text += f"使用者：{user_message}\n"

    # 組裝 Prompt：將任務指令與輸出格式合併
    prompt = (
        f"{PREFERENCE_EXTRACTION_TASK}\n\n{PREFERENCE_EXTRACTION_RULES}\n\n"
        f"{PREFERENCE_EXTRACTION_FORMAT}\n\n"
        f"【目前有效偏好】\n{json.dumps(base_preferences, ensure_ascii=False)}\n"
        f"【對話紀錄（僅作參考）】\n{history_text}\n"
        f"【最新使用者訊息】\n{user_message}"
    )

    fallback_result = {
        "preferences": {}, "extraction_failed": True
    }

    client = OllamaClient()
    try:
        # 將佐證限制在本輪原文，避免小模型把改寫後的偏好錯當成引用。
        schema = deepcopy(_EXTRACTION_SCHEMA)
        quotes = list(dict.fromkeys(['', user_message] + [
            part.strip() for part in re.split(r'[，,。！？!?；;\n]', user_message) if part.strip()
        ]))
        for dim in PREFERENCE_DIMS:
            schema['properties']['evidence']['properties'][dim]['enum'] = quotes
            schema['properties']['remove_preferences']['properties'][dim]['items']['enum'] = (
                base_preferences.get(dim) or ['']
            )
        data = client.generate(
            model=model_name, prompt=prompt, stream=False,
            timeout=PREFERENCE_EXTRACTION_TIMEOUT, format=schema,
            options={"temperature": 0},
        )
        response_text = data.get("response", "")
        logging.debug(f"[LLM Extraction] Response: {response_text}")

        result = client.extract_json_from_response(response_text)
        if isinstance(result, dict) and isinstance(result.get('preferences'), dict):
            evidence = result.get('evidence')
            evidence = evidence if isinstance(evidence, dict) else {}
            prefs = _sanitize_preferences(
                result['preferences'], user_message, ai_text, evidence, base_preferences
            )
            act = result.get('dialogue_act')
            if act in ('question', 'chat'):
                return {
                    'preferences': {}, 'remove_preferences': {},
                    'replace_dimensions': [], 'dialogue_act': act, 'next_dimension': None,
                }
            if act in ('preferences', 'recommend'):
                literal = {}
                for clause in re.split(r'[，,。！？!?；;\n]', user_message):
                    clause = clause.strip()
                    dims = _clause_dimensions(clause)
                    if len(dims) == 1 and len(clause) <= 100:
                        dim = next(iter(dims))
                        literal.setdefault(dim, []).append(clause)
                        evidence[dim] = user_message
                # 清楚屬於單一維度的子句以原文為準，避免小模型把「太酸」縮成「酸」。
                for dim, clauses in literal.items():
                    if prefs.get(dim) != ['不限']:
                        prefs[dim] = clauses[:6]
            removals = result.get('remove_preferences')
            removals = removals if isinstance(removals, dict) else {}
            removals = {
                dim: [value for value in values if value in base_preferences.get(dim, [])]
                for dim, values in removals.items()
                if dim in PREFERENCE_DIMS and isinstance(values, list)
                and isinstance(evidence.get(dim), str) and evidence[dim].strip()
                and evidence[dim] in user_message
                and (not _clause_dimensions(evidence[dim]) or dim in _clause_dimensions(evidence[dim]))
            }
            # 預算改口及明確取消整個維度可直接取代；其他條件逐筆增刪。
            replace_dims = [
                dim for dim in prefs
                if isinstance(evidence.get(dim), str) and evidence[dim].strip()
                and evidence[dim] in user_message
                and (dim == 'budget' or prefs[dim] == ['不限'])
            ]
            return {
                "preferences": prefs,
                "replace_dimensions": replace_dims,
                "remove_preferences": removals,
                "dialogue_act": act if act in ('preferences', 'question', 'chat', 'recommend') else None,
                "next_dimension": result.get('next_dimension') if result.get('next_dimension') in PREFERENCE_DIMS else None,
            }
        else:
            return fallback_result

    except Exception as e:
        logging.error(f"[LLM Extraction Error]: {e}")
        return fallback_result
