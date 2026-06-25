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
