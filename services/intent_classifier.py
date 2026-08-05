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

# 明確與咖啡廳無關的請求：這些一律直接婉拒並導回本系統的用途。
# 只列「明確的他用途請求」，不用「沒有咖啡關鍵字就算離題」——
# 那樣會誤傷使用者用自己的說法描述需求（例如「想要有大片落地窗的地方」）。
OFF_TOPIC_PATTERNS = [
    # 代寫、創作
    '寫一首', '寫首', '寫詩', '作詩', '寫一篇', '寫文章', '寫作文', '作文',
    '寫信', '寫一封', '寫報告', '寫履歷', '寫自傳', '寫企劃', '寫腳本',
    '幫我寫', '幫我翻譯', '翻譯成', '幫我算', '幫我查',
    # 技術、學術
    '程式', '程式碼', 'python', 'javascript', ' java', 'html', 'css', 'sql',
    '迴圈', '函式', '報錯', 'bug', '演算法', '數學', '微積分', '方程式',
    # 生活資訊（本系統沒有這些資料）
    '天氣', '氣溫', '下雨', '颱風', '股票', '股價', '匯率', '樂透', '彩券',
    '新聞', '時事', '選舉', '總統', '政治', '疫情',
    # 醫療、法律等專業意見
    '看醫生', '生病', '症狀', '吃什麼藥', '法律', '打官司', '報稅',
    # 純娛樂（用單詞比對，避免「講個笑話」這種中間插字的說法漏掉）
    '笑話', '說故事', '講故事', '陪我聊', '唱歌', '玩遊戲',
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

    命中時要明確婉拒並說明本系統的用途，而不是硬把話題拉回去
    （硬拉會讓人覺得答非所問），更不能真的去幫他寫詩或寫程式。

    回傳:
        (is_off_topic: bool, matched: str|None)
    """
    text = (user_message or '').lower()
    if not text.strip():
        return False, None

    for pattern in OFF_TOPIC_PATTERNS:
        if pattern in text:
            # 同時提到咖啡廳需求時不算離題（例如「幫我查有插座的咖啡廳」）
            if any(kw in text for kw in CAFE_KEYWORDS):
                return False, None
            return True, pattern.strip()
    return False, None
