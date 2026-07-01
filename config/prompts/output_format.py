# Output Layer：輸出格式定義，不包含邏輯或決策規則

CAFE_RECOMMENDATION_FORMAT = """【輸出格式】
當進行咖啡廳推薦時，請嚴格遵守以下精華介紹格式：
- 格式：[店名] ＋ [適合理由] ＋ [一個具體亮點]
- 範例：推薦你「黑鯨咖啡」，那裡環境很安靜非常適合閱讀。最棒的是他們家有可愛的店貓陪你度過下午喔！
（請勿貼出過多冗長的資料，要像對話一樣自然）
"""

PREFERENCE_EXTRACTION_FORMAT = """【輸出格式】
你必須「只」輸出一段合法的 JSON 字串，不可以包含任何 Markdown 標記（例如 ```json）或其他文字解釋。
若對話中沒有提及該維度的偏好，請一律填入空陣列 []。若沒有提及是否同意情境配對，請填入 null。
（如果真的有提及偏好，例如讀書或安靜，才填入對應的陣列中，如 ["讀書"]）
請輸出如以下格式的 JSON 結構：
{
  "preferences": {
    "purpose": [],
    "vibe": [],
    "taste": [],
    "budget": [],
    "special": []
  },
  "quiz_consent": null,
  "quiz_refused": false
}
"""
