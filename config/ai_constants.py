# HTTP Client and Service Timeouts
OLLAMA_CLIENT_TIMEOUT = 300      # 串流生成超時
OLLAMA_HEALTH_TIMEOUT = 3        # 健康檢查超時
PREFERENCE_EXTRACTION_TIMEOUT = 60 # 包含本機模型冷啟動與完整語意萃取

# 出卡片那一輪的額外停止序列：店家資訊已由前端卡片呈現，
# 提示詞再三禁止，模型仍會在說明後面自己演一份「圖文卡片」
# （分隔線、假圖片網址、改寫過的地址）。一出現這些記號就截斷。
CARDS_MODE_STOP_SEQUENCES = [
    "***", "---", "【圖文卡片】", "[圖文卡片]", "![", "[圖片]",
    "📍", "地址：", "\n- **", "\n**", "\n1.", "\n- ",
    # 說明後面另起一段的括號旁白（「(圖文卡片)」「(由於目前尚未觸發推薦階段…)」）
    "\n(", "\n（",
]

# Database Search Limits
CAFE_TAG_MATCH_LIMIT = 5         # 標籤匹配最多取幾家
CAFE_NAME_MATCH_LIMIT = 3        # 名稱匹配最多取幾家
CAFE_TAGS_DISPLAY_LIMIT = 8      # 每家咖啡廳最多取幾個標籤

# Chat History Context Limits
AI_CHAT_HISTORY_LIMIT = 6        # 最近幾輪對話作為上下文
PREFERENCE_HISTORY_LIMIT = 10    # 偏好萃取時看最近幾筆對話

# Conversation Guide Keywords（對話引導關鍵字）
CHAT_EXIT_KEYWORDS = ['聊天', '笑話', '說故事', '別提咖啡', '不想找', '隨便聊', '其他事']  # 使用者想跳出「找咖啡」主題
