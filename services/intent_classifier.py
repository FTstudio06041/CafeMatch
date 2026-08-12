# services/intent_classifier.py

CAFE_KEYWORDS = [
    '咖啡', '推薦', '咖啡廳', '咖啡店', 'café', 'cafe', '喝', '甜點',
    '花蓮', '安靜', '讀書', '工作', '約會', '聚會', '早午餐', '下午茶',
    '便宜', '平價', '好喝', '好吃', '哪裡', '哪家', '附近', '營業',
    '幾點', '開門', '關門', '休息', '地址', '電話', '價格', '消費',
    '文青', '氛圍', '氣氛', '環境', '貓', '寵物', '座位', 'wifi',
    '拿鐵', '手沖', '濾掛', '豆子', '烘焙', '評價', '評論', '打卡',
    '測驗', '配對', '結果', '適合', '口感', '風味', '酸', '苦', '甜',
    '司康', '蛋糕', '鬆餅', '可頌', '冰', '熱'
]

def classify_intent(user_message):
    """
    判斷使用者訊息是否與咖啡推薦相關。

    回傳:
        (is_cafe_related: bool, matched_keywords: list[str])
    """
    lower_msg = user_message.lower()
    matched = [kw for kw in CAFE_KEYWORDS if kw in lower_msg]
    return len(matched) > 0, matched


def is_off_topic(user_message):
    """
    判斷使用者是不是在要求「與咖啡廳推薦無關的事」。

    判斷本身已經搬到 services/off_topic_rag.py（關鍵字錨點 + 語意檢索），
    這裡只保留舊介面。要拿到該回的固定台詞請直接用 off_topic_rag.classify()。

    回傳:
        (is_off_topic: bool, matched: str|None)
    """
    from services import off_topic_rag
    is_off, cat_id, _response, detail = off_topic_rag.classify(user_message)
    return is_off, (detail.get('hit') or cat_id)
