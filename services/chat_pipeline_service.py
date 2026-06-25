import json
from flask import current_app, session
from database import db
from models import User, Cafes, Tags, AiQueryLog
from services import ai_service, conversation_guide, preference_service
from services.intent_classifier import classify_intent
from services.cafe_retriever import retrieve_cafe_context
from services.ollama_admin_service import check_health, get_default_model

class ChatPipelineService:
    @staticmethod
    def generate_pipeline(data, is_debug_requested):
        try:
            user_message = data.get('message', '')
            history = data.get('history', [])
            is_quiz_result = data.get('is_quiz_result', False)

            if not user_message:
                yield json.dumps({"error": "未提供訊息", "done": True}, ensure_ascii=False) + "\n"
                return

            if not check_health():
                yield json.dumps({"error": "Ollama 連線失敗，請確認是否已啟動 Ollama。", "done": True}, ensure_ascii=False) + "\n"
                return

            yield json.dumps({"status": "analyzing_intent"}, ensure_ascii=False) + "\n"
            is_cafe_related, matched_keywords = classify_intent(user_message)
            if not is_cafe_related and len(history) > 0:
                lower_msg = user_message.lower()
                exit_keywords = ['聊天', '笑話', '說故事', '別提咖啡', '不想找', '隨便聊', '其他事']
                if not any(kw in lower_msg for kw in exit_keywords):
                    is_cafe_related = True

            extracted_data = None
            guide_instruction = None

            if is_cafe_related:
                if is_quiz_result:
                    yield json.dumps({"status": "processing_quiz_result"}, ensure_ascii=False) + "\n"
                    extracted_data = {"quiz_consent": False, "quiz_refused": True}
                    guide_instruction = None
                else:
                    yield json.dumps({"status": "extracting_preferences"}, ensure_ascii=False) + "\n"
                    model_name = current_app.config.get('OLLAMA_MODEL') or get_default_model()
                    extracted_data = preference_service.extract_preferences(history, user_message, model_name)
                    
                    all_keywords = []
                    if extracted_data and "preferences" in extracted_data:
                        for vals in extracted_data["preferences"].values():
                            all_keywords.extend(vals)
                    matched_keywords = list(set(matched_keywords + all_keywords))

                    temp_history = history.copy()
                    temp_history.append({"role": "user", "content": user_message})
                    guide_instruction = conversation_guide.analyze_and_guide(temp_history, extracted_data)
                    
                    if extracted_data and extracted_data.get("quiz_consent") is True:
                        yield json.dumps({"status": "generating_response"}, ensure_ascii=False) + "\n"
                        # 修復：將 SHOW_QUIZ_CARD 的訊息放到回覆中，避免 hardcode 在路由裡
                        quiz_message = "太好了！那請點擊下方卡片，我們馬上開始囉～\n\n[SHOW_QUIZ_CARD]"
                        yield json.dumps({"response": quiz_message}, ensure_ascii=False) + "\n"
                        yield json.dumps({"response": "", "done": True}, ensure_ascii=False) + "\n"
                        return

            cafe_context = ""
            if is_cafe_related:
                yield json.dumps({"status": "retrieving_cafes"}, ensure_ascii=False) + "\n"
                cafe_context = retrieve_cafe_context(matched_keywords, Cafes, Tags)
            else:
                yield json.dumps({"status": "general_chat"}, ensure_ascii=False) + "\n"

            extracted_prefs = extracted_data.get("preferences") if extracted_data else None
            model_name = current_app.config.get('OLLAMA_MODEL') or get_default_model()
            prompt_text = ai_service.build_prompt(
                user_message=user_message, 
                history=history, 
                is_cafe_related=is_cafe_related, 
                cafe_context=cafe_context, 
                guide_instruction=guide_instruction,
                extracted_preferences=extracted_prefs
            )

            user_id = None
            is_admin = False
            user_email = session.get('user_email')
            if user_email:
                current_user = User.query.filter_by(email=user_email).first()
                if current_user:
                    user_id = current_user.id
                    is_admin = getattr(current_user, 'is_admin', False)

            show_debug = is_debug_requested and is_admin

            yield json.dumps({"status": "generating_response"}, ensure_ascii=False) + "\n"
            for chunk in ai_service.stream_generate(
                model_name=model_name,
                prompt_text=prompt_text,
                is_cafe_related=is_cafe_related,
                cafe_context=cafe_context,
                db=db,
                AiQueryLog=AiQueryLog,
                user_id=user_id,
                show_debug=show_debug
            ):
                yield chunk

        except Exception as e:
            current_app.logger.exception(f"Chat API Error: {e}")
            yield json.dumps({"error": "系統暫時無法處理，請稍後再試", "done": True}, ensure_ascii=False) + "\n"
