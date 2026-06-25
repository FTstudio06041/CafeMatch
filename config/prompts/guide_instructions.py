# 心理測驗引導
QUIZ_CONSENT_INSTRUCTION = "【任務】使用者已同意進行測驗。請在您的回覆中，確切包含字串：「[SHOW_QUIZ_CARD]」，並可附帶一句簡短自然的引導（例如：太好了！那請點擊下方卡片，我們馬上開始囉～）。絕不要推薦店家，也不要再問其他問題。"
QUIZ_INVITATION_INSTRUCTION = "【任務】請詢問使用者：「為了給您更精準的推薦，您願意先花 1 分鐘做個心理測驗小遊戲嗎？」請用語氣自然的方式發問。"

# 推薦狀態
ALREADY_RECOMMENDED_INSTRUCTION = "【任務】你已經推薦過咖啡廳了。請回答使用者關於推薦店家的問題，若使用者不滿意或想換口味，可以再推薦其他家。"

# 釐清需求
def get_clarification_instruction(summary, question_count, max_questions, next_dim_label, example=""):
    instruction = (
        f"【任務】使用者目前已透露的偏好：{summary}。\n"
        f"【目前進度】已提問次數：{question_count} / 最大上限：{max_questions}。\n"
        f"接下來，你需要幫忙釐清使用者的「{next_dim_label}」。\n"
        f"請以朋友般的自然口吻，順著聊天的感覺問出這個重點。"
    )
    if example:
        instruction += (
            f"\n\n【重要禁止事項】\n"
            f"絕對不可以原封不動照抄這句話：「{example}」。\n"
            f"請你一定要發揮創意、換句話說，讓每次的問法都不一樣！"
        )
    return instruction

# 偏好萃取
PREFERENCE_EXTRACTION_TASK = "你是一個精準的語意分析工具。你的任務是從以下對話紀錄中，萃取出使用者的咖啡廳偏好維度（如 purpose, vibe, taste, budget, special 等），並判斷使用者是否同意進行心理測驗。"
PREFERENCE_EXTRACTION_RULES = "【嚴格限制】這是一個純粹的資料萃取任務。你絕對不可以生成任何推薦結果、咖啡廳名稱或與使用者聊天的句子。"
