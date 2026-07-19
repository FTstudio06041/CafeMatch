"""
preference_adjuster.py — 心理測驗分數 × 對話確認結果 → GNN 輸入向量

流程定位（GNN 推薦接口的前半段）：
  1. 心理測驗五維分數 = 基礎資料
  2. 使用者對測驗結果的回饋（準不準）決定基礎分數的信任權重
  3. 對話中確認到的偏好關鍵字，映射到五維加分
  4. 輸出調整後的五維分數 + 硬過濾條件（寵物／停車／深夜）

設計原則：純 Python 規則，不依賴 torch / Flask，可獨立單元測試。
"""

DIMS = ["work", "env", "social", "taste", "cp"]

# 使用者對測驗結果的回饋 → 基礎分數信任權重
# （含「准」異體字，涵蓋使用者手打的變體）
_INACCURATE_SIGNALS = ('完全不像', '完全不準', '完全不准', '都不準', '都不准')
_PARTIAL_SIGNALS = ('有點落差', '不太準', '不太准', '有落差', '不準', '不准')

_ACCURACY_WEIGHTS = {
    'accurate': 1.0,    # 覺得準（或沒表態）→ 完全信任測驗分數
    'partial': 0.5,     # 有點落差 → 測驗分數減半，靠對話補足
    'inaccurate': 0.0,  # 完全不像我 → 拋棄測驗分數，只用對話確認結果
}

# 對話偏好關鍵字 → 五維加分（子字串比對，涵蓋「工作寫作業」這類選項文字）
_KEYWORD_BOOSTS = {
    # 造訪目的
    '工作': {'work': 3}, '讀書': {'work': 3}, '辦公': {'work': 3},
    '聚會': {'social': 3}, '朋友': {'social': 3}, '約會': {'social': 3},
    '放鬆': {'env': 2}, '放空': {'env': 2}, '發呆': {'env': 2},
    '一個人': {'work': 1, 'env': 1},
    # 氛圍
    '安靜': {'work': 2, 'env': 1}, '熱鬧': {'social': 2},
    '文青': {'env': 3}, '老宅': {'env': 3}, '日式': {'env': 3},
    '網美': {'env': 3}, '懷舊': {'env': 3}, '拍照': {'env': 2}, '打卡': {'env': 2},
    '氛圍': {'env': 2}, '環境': {'env': 2}, '舒服': {'env': 2}, '慵懶': {'env': 2},
    '綠意': {'env': 2}, '採光': {'env': 2},
    # 口味
    '手沖': {'taste': 3}, '單品': {'taste': 3}, '拿鐵': {'taste': 2},
    '特調': {'taste': 2}, '甜點': {'taste': 3}, '蛋糕': {'taste': 2},
    '早午餐': {'taste': 2}, '可頌': {'taste': 2}, '司康': {'taste': 2},
    '鬆餅': {'taste': 2}, '美式': {'taste': 2},
    # 預算
    '平價': {'cp': 3}, '便宜': {'cp': 3}, '百元': {'cp': 3}, 'CP值': {'cp': 3},
    '學生': {'cp': 2}, '預算': {'cp': 2}, '低消': {'cp': 2},
    # 特殊需求（利於工作型場域）
    '插座': {'work': 2}, '不限時': {'work': 2}, 'wifi': {'work': 1},
}

# 硬過濾條件（不加分，直接過濾候選店家）
_HARD_FILTER_KEYWORDS = {
    'pet': ('寵物', '貓', '狗', '毛孩'),
    'parking': ('停車',),
    'night': ('深夜', '晚間', '宵夜'),
}


def detect_accuracy_feedback(history: list) -> str:
    """
    從對話歷史找出使用者對測驗結果的回饋。

    回傳 'accurate' | 'partial' | 'inaccurate'（最強訊號優先）。
    """
    result = 'accurate'
    for m in history or []:
        if m.get('role') != 'user':
            continue
        content = m.get('content', '')
        if any(sig in content for sig in _INACCURATE_SIGNALS):
            return 'inaccurate'
        if any(sig in content for sig in _PARTIAL_SIGNALS):
            result = 'partial'
    return result


def build_gnn_input(quiz_scores: dict | None, history: list, preferences: dict | None):
    """
    融合測驗基礎分數與對話確認結果，產生 GNN 推薦輸入。

    參數:
        quiz_scores: 心理測驗五維分數 {work, env, social, taste, cp}，可為 None（沒做過測驗）
        history:     對話歷史（判斷準不準回饋）
        preferences: 對話萃取偏好 {purpose: [...], vibe: [...], ...}

    回傳:
        (adjusted_scores: dict, hard_filters: dict, accuracy: str)
          adjusted_scores — 調整後五維分數（float，供 GNN quiz 路徑正規化使用）
          hard_filters    — {'pet': bool, 'parking': bool, 'night': bool}
          accuracy        — 使用者對測驗的回饋分類（供除錯／記錄）
    """
    accuracy = detect_accuracy_feedback(history)
    weight = _ACCURACY_WEIGHTS[accuracy]

    base = quiz_scores or {}
    adjusted = {d: float(base.get(d, 0) or 0) * weight for d in DIMS}
    hard_filters = {'pet': False, 'parking': False, 'night': False}

    for values in (preferences or {}).values():
        if not isinstance(values, list):
            continue
        for kw in values:
            if not isinstance(kw, str):
                continue
            for flag, signals in _HARD_FILTER_KEYWORDS.items():
                if any(sig in kw for sig in signals):
                    hard_filters[flag] = True
            for boost_kw, boosts in _KEYWORD_BOOSTS.items():
                if boost_kw in kw:
                    for dim, val in boosts.items():
                        adjusted[dim] += val

    return adjusted, hard_filters, accuracy
