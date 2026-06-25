# Output Layer：輸出格式定義，不包含邏輯或決策規則

CAFE_RECOMMENDATION_FORMAT = """【輸出格式】
當進行咖啡廳推薦時，請嚴格遵守以下精華介紹格式：
- 格式：[店名] ＋ [適合理由] ＋ [一個具體亮點]
- 範例：推薦你「黑鯨咖啡」，那裡環境很安靜非常適合閱讀。最棒的是他們家有可愛的店貓陪你度過下午喔！
（請勿貼出過多冗長的資料，要像對話一樣自然）
"""

PREFERENCE_EXTRACTION_FORMAT = """【輸出格式】
你必須「只」輸出一段合法的 JSON 字串，不可以包含任何 Markdown 標記（例如 ```json）或其他文字解釋。
請輸出如以下格式的 JSON 結構：
{
  "preferences": {
    "purpose": ["讀書", "工作"],
    "vibe": ["安靜"]
  },
  "quiz_consent": true,
  "quiz_refused": false
}
"""
