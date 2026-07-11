# 推薦狀態
ALREADY_RECOMMENDED_INSTRUCTION = "【任務】你已經推薦過咖啡廳了。請回答使用者關於推薦店家的問題，若使用者不滿意或想換口味，可以再推薦其他家。"

# 確認需求
def get_confirmation_instruction(summary, missing_labels, question_count, max_questions, example=""):
    """
    產生「確認使用者需求」的引導指令。

    使用者需求還不夠明確時，讓 AI 用一個簡短自然的問題，
    確認最重要的不確定面向；確認後的偏好會回流到狀態機決定何時推薦。
    """
    focus = "、".join(missing_labels[:2])
    instruction = (
        f"【任務】使用者的需求還不夠明確，這一輪請先跟他確認需求，不要推薦店家。\n"
        f"目前已知的偏好：{summary}。\n"
        f"還不確定的部分：{focus}。\n"
        f"【目前進度】已提問次數：{question_count} / 最大上限：{max_questions}。\n"
        f"請以朋友般的自然口吻，只問「一個」簡短的問題來確認上面不確定的部分即可；"
        f"不要逐項盤問、不要列清單、不要一次問一大串，問完就停，等使用者回覆。"
    )
    if example:
        instruction += (
            f"\n\n【重要禁止事項】\n"
            f"絕對不可以原封不動照抄這句話：「{example}」。\n"
            f"請你一定要發揮創意、換句話說，讓每次的問法都不一樣！"
        )
    return instruction

# 偏好萃取
PREFERENCE_EXTRACTION_TASK = "你是一個精準的語意分析工具。你的任務是從以下對話紀錄中，萃取出使用者的咖啡廳偏好維度（如 purpose, vibe, taste, budget, special 等）。"
PREFERENCE_EXTRACTION_RULES = "【嚴格限制】這是一個純粹的資料萃取任務。你絕對不可以生成任何推薦結果、咖啡廳名稱或與使用者聊天的句子。"
