import json
from flask import current_app, session
from database import db
from models import User, Cafes, Tags, AiQueryLog
from services import ai_service, conversation_guide, preference_service
from services.intent_classifier import classify_intent
from services.cafe_retriever import retrieve_cafe_data, format_cafe_context, serialize_cafe
from services.ollama_admin_service import check_health, get_default_model
from services.settings_service import get_selected_model
from config.ai_constants import CHAT_EXIT_KEYWORDS

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
                if not any(kw in lower_msg for kw in CHAT_EXIT_KEYWORDS):
                    is_cafe_related = True

            extracted_data = None
            guide_instruction = None

            if is_cafe_related:
                if is_quiz_result:
                    # 心理測驗結果：跳過確認需求，直接根據測驗內容推薦
                    yield json.dumps({"status": "processing_quiz_result"}, ensure_ascii=False) + "\n"
                    guide_instruction = None
                else:
                    yield json.dumps({"status": "extracting_preferences"}, ensure_ascii=False) + "\n"
                    model_name = get_selected_model() or get_default_model()
                    extracted_data = preference_service.extract_preferences(history, user_message, model_name)

                    all_keywords = []
                    if extracted_data and "preferences" in extracted_data:
                        for vals in extracted_data["preferences"].values():
                            all_keywords.extend(vals)
                    matched_keywords = list(set(matched_keywords + all_keywords))

                    # 確認需求 → 結果丟給狀態機：萃取出的偏好交由狀態機
                    # 決定「這一輪要先確認需求，還是直接推薦」
                    temp_history = history.copy()
                    temp_history.append({"role": "user", "content": user_message})
                    guide_instruction = conversation_guide.analyze_and_guide(temp_history, extracted_data)

            from config.prompts import ALREADY_RECOMMENDED_INSTRUCTION
            should_recommend = (guide_instruction is None) or (guide_instruction == ALREADY_RECOMMENDED_INSTRUCTION)

            cafe_context = ""
            cafes = []
            if is_cafe_related and should_recommend:
                yield json.dumps({"status": "retrieving_cafes"}, ensure_ascii=False) + "\n"
                cafes = retrieve_cafe_data(matched_keywords, Cafes, Tags)
                cafe_context = format_cafe_context(cafes)
                if cafes:
                    yield json.dumps({"cafes": [serialize_cafe(c) for c in cafes]}, ensure_ascii=False) + "\n"
            elif not is_cafe_related:
                yield json.dumps({"status": "general_chat"}, ensure_ascii=False) + "\n"

            # 有卡片時：店名交給卡片呈現，不把知識庫店名餵給 LLM，並改用「卡片模式」格式（不准講店名）
            has_cards = bool(cafes)
            extracted_prefs = extracted_data.get("preferences") if extracted_data else None
            model_name = get_selected_model() or get_default_model()
            prompt_text = ai_service.build_prompt(
                user_message=user_message,
                history=history,
                is_cafe_related=is_cafe_related,
                cafe_context=("" if has_cards else cafe_context),
                guide_instruction=guide_instruction,
                extracted_preferences=extracted_prefs,
                cards_mode=has_cards
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
