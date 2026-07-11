# 推薦狀態
ALREADY_RECOMMENDED_INSTRUCTION = "【任務】你已經推薦過咖啡廳了。請回答使用者關於推薦店家的問題，若使用者不滿意或想換口味，可以再推薦其他家。"

# 確認完成：邀請使用者按下「直接推薦咖啡廳」按鈕（推薦只能由按鈕觸發）
READY_TO_RECOMMEND_INSTRUCTION = (
    "【任務】你已經大致掌握使用者的偏好了，但這一輪絕對不要推薦店家、不要提及任何店名。\n"
    "請先簡短自然地回應使用者剛剛說的話，然後告訴他：你已經掌握得差不多了，"
    "準備好的話可以按下方的「直接推薦咖啡廳」按鈕讓你立刻推薦；"
    "當然也歡迎他繼續補充需求，掌握度越高、推薦會越準。\n"
    "只要說這些就好，不要再問新的問題。"
)

# 快速選項標記：AI 在確認需求時附上，前端解析為可點選按鈕
QUICK_OPTIONS_FORMAT = (
    "【選項格式】請在回覆的最後另起一行，用以下格式提供 2~4 個快速回覆選項，"
    "讓使用者可以直接點選作答（每個選項 2~8 個字、必須能直接當作使用者的回答、要對應你問的問題）：\n"
    "[QUICK_OPTIONS] 選項一 | 選項二 | 選項三"
)

# 測驗結果進場：先問結果準不準，不直接推薦
QUIZ_RESULT_CONFIRMATION_INSTRUCTION = (
    "【任務】使用者剛完成心理測驗，訊息中附上了他的測驗結果。這一輪絕對不要推薦店家。\n"
    "請先用一兩句親切的話總結他的咖啡人格特質，"
    "然後問他覺得這個測驗結果「準不準、像不像自己」（請用自然的口吻換句話說）；"
    "只問這一個問題，不要順便問其他需求、不要列清單，問完就停，等使用者回覆。\n"
    "【選項格式】請在回覆的最後另起一行，用以下格式提供快速回覆選項：\n"
    "[QUICK_OPTIONS] 蠻準的！ | 有點落差 | 完全不像我"
)

# 確認需求
def get_confirmation_instruction(summary, next_dim_label, question_count, max_questions, example="", quick_options=None):
    """
    產生「確認使用者需求」的引導指令。

    使用者需求還不夠明確時，讓 AI 針對下一個不確定的維度，
    用一個簡短自然的問題確認；確認後的偏好會回流到狀態機決定何時推薦。
    """
    instruction = (
        f"【任務】使用者的需求還不夠明確，這一輪請先跟他確認需求，不要推薦店家。\n"
        f"目前已知的偏好：{summary}。\n"
        f"這一輪請針對「{next_dim_label}」，以朋友般的自然口吻問「一個」簡短的問題；"
        f"不要逐項盤問、不要列清單、不要一次問一大串，問完就停，等使用者回覆。\n"
        f"【目前進度】已提問次數：{question_count} / 最大上限：{max_questions}。\n"
    )
    if quick_options:
        opts = " | ".join(quick_options[:4])
        instruction += (
            f"【選項格式】回覆的最後請另起一行，原封不動加上這一行：\n"
            f"[QUICK_OPTIONS] {opts}"
        )
    else:
        instruction += QUICK_OPTIONS_FORMAT
    if example:
        instruction += (
            f"\n\n【重要禁止事項】\n"
            f"絕對不可以原封不動照抄這句話：「{example}」。\n"
            f"請你一定要發揮創意、換句話說，讓每次的問法都不一樣！"
        )
    return instruction

# 偏好萃取
PREFERENCE_EXTRACTION_TASK = "你是一個精準的語意分析工具。你的任務是從以下對話紀錄中，萃取出使用者的咖啡廳偏好維度（如 purpose, vibe, taste, budget, special 等）。"
PREFERENCE_EXTRACTION_RULES = (
    "【嚴格限制】這是一個純粹的資料萃取任務。你絕對不可以生成任何推薦結果、咖啡廳名稱或與使用者聊天的句子。\n"
    "只能萃取「使用者」自己說過或明確附和的偏好；"
    "助手訊息中的推測、人格測驗描述，除非使用者本人附和，否則一律不算使用者偏好。"
)
