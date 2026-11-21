# -*- coding: utf-8 -*-
"""
service_area.py — 服務範圍檢查

資料庫只有花蓮的店。使用者問「台北信義區有什麼咖啡廳」時，模型會順著講，
偏好萃取也會把地名記成條件，最後推出一批花蓮的店，使用者完全不會察覺。
這裡在進模型之前先攔下來，回一段固定說明（資料與台詞見 data/service_area.json）。
"""

import json
import os

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'data', 'service_area.json')
_cache = None


def _load():
    global _cache
    if _cache is None:
        with open(_PATH, 'r', encoding='utf-8') as f:
            _cache = json.load(f)
    return _cache


def outside_area(user_message: str):
    """
    使用者指定了服務範圍以外的地點 → 回傳該說的固定台詞，否則 None。

    同一句也提到花蓮的地名就放行（「從台北來花蓮玩」是在講花蓮）；
    地名只是出發地或身分（「我從台北過來」「台北人」）也放行。
    """
    text = user_message or ''
    cfg = _load()
    if any(term in text for term in cfg['home_terms']):
        return None
    for term in cfg['outside_terms']:
        start = text.find(term)
        while start != -1:
            before = text[:start]
            after = text[start + len(term):]
            is_origin = (any(before.endswith(p) for p in cfg['origin_prefixes'])
                         or any(after.startswith(s) for s in cfg['origin_suffixes']))
            if not is_origin:
                return cfg['response']
            start = text.find(term, start + 1)
    return None
