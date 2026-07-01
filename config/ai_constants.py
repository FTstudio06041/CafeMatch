# HTTP Client and Service Timeouts
OLLAMA_CLIENT_TIMEOUT = 300      # 串流生成超時
OLLAMA_HEALTH_TIMEOUT = 3        # 健康檢查超時
PREFERENCE_EXTRACTION_TIMEOUT = 10 # 偏好萃取超時

# Database Search Limits
CAFE_TAG_MATCH_LIMIT = 5         # 標籤匹配最多取幾家
CAFE_NAME_MATCH_LIMIT = 3        # 名稱匹配最多取幾家
CAFE_TAGS_DISPLAY_LIMIT = 8      # 每家咖啡廳最多取幾個標籤

# Chat History Context Limits
AI_CHAT_HISTORY_LIMIT = 6        # 最近幾輪對話作為上下文
PREFERENCE_HISTORY_LIMIT = 10    # 偏好萃取時看最近幾筆對話

# Conversation Guide Keywords（對話引導關鍵字）
CHAT_EXIT_KEYWORDS = ['聊天', '笑話', '說故事', '別提咖啡', '不想找', '隨便聊', '其他事']  # 使用者想跳出「找咖啡」主題
QUIZ_CONSENT_KEYWORDS = ['好', 'ok', '可以', '願意', '要', '來吧', '行', '沒問題', '恩', '嗯']  # 同意進行測驗

# 情境配對邀請門檻：使用者訊息長度 <= 此值、且無具體偏好訊號時，才視為「很籠統」而邀請小卡
VAGUE_REQUEST_MAX_LEN = 12
