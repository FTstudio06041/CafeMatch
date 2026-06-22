import uuid
import json
from datetime import datetime
from flask import Blueprint, jsonify, request, session, stream_with_context, current_app
from database import db
from models import User, ChatSession, ChatFeedback, AiQueryLog, Cafes, Tags
from services import ai_service, conversation_guide

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/api/chat/sessions', methods=['GET'])
def get_chat_sessions():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "請先登入"}), 401
    
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({"error": "使用者不存在"}), 404

    sessions = ChatSession.query.filter_by(user_id=user.id).order_by(ChatSession.updated_at.desc()).all()
    
    result = []
    for s in sessions:
        result.append({
            "id": s.id,
            "title": s.title,
            "updated_at": s.updated_at.strftime('%Y-%m-%d %H:%M:%S') if s.updated_at else None
        })
    return jsonify(result)

@chat_bp.route('/api/chat/sessions/<session_id>', methods=['GET'])
def get_chat_session_detail(session_id):
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "請先登入"}), 401
    
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({"error": "使用者不存在"}), 404

    chat_session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
    if not chat_session:
        return jsonify({"error": "找不到該對話"}), 404

    return jsonify({
        "id": chat_session.id,
        "title": chat_session.title,
        "messages": chat_session.messages,
        "updated_at": chat_session.updated_at.strftime('%Y-%m-%d %H:%M:%S') if chat_session.updated_at else None
    })

@chat_bp.route('/api/chat/sessions', methods=['POST'])
def save_chat_session():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "請先登入"}), 401
    
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({"error": "使用者不存在"}), 404

    data = request.json
    if len(json.dumps(data)) > 1024 * 1024:
        return jsonify({"error": "Payload 過大"}), 413

    session_id = data.get('id')
    title = data.get('title', '新對話')
    if len(title) > 100:
        title = title[:100]

    messages = data.get('messages', [])
    if len(messages) > 1000:
        return jsonify({"error": "訊息數量過多"}), 413

    allowed_roles = {'user', 'ai', 'system'}
    allowed_keys = {'role', 'content', 'feedback', 'debug_info', 'status'}
    cleaned_messages = []
    for msg in messages:
        if not isinstance(msg, dict):
            return jsonify({"error": "訊息格式錯誤"}), 400
        if msg.get('role') not in allowed_roles:
            return jsonify({"error": "包含不合法的角色"}), 400
        cleaned_msg = {k: v for k, v in msg.items() if k in allowed_keys}
        cleaned_messages.append(cleaned_msg)
    messages = cleaned_messages

    try:
        if session_id:
            chat_session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
            if not chat_session:
                return jsonify({"error": "找不到該對話"}), 404
            
            chat_session.title = title
            chat_session.messages = messages
            chat_session.updated_at = datetime.utcnow()
        else:
            new_id = str(uuid.uuid4())
            chat_session = ChatSession(
                id=new_id,
                user_id=user.id,
                title=title,
                messages=messages
            )
            db.session.add(chat_session)
        
        db.session.commit()
        return jsonify({"success": True, "id": chat_session.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "系統發生錯誤，請稍後再試"}), 500

@chat_bp.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
def delete_chat_session(session_id):
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "請先登入"}), 401
    
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({"error": "使用者不存在"}), 404

    try:
        chat_session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
        if not chat_session:
            return jsonify({"error": "找不到該對話"}), 404
        
        db.session.delete(chat_session)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "系統發生錯誤，請稍後再試"}), 500

def get_current_model():
    if 'OLLAMA_MODEL' not in current_app.config or not current_app.config['OLLAMA_MODEL']:
        current_app.config['OLLAMA_MODEL'] = ai_service.get_default_model()
    return current_app.config['OLLAMA_MODEL']

@chat_bp.route('/api/chat', methods=['POST'])
def chat_with_ai():
    def generate_pipeline():
        try:
            data = request.json
            user_message = data.get('message', '')
            history = data.get('history', [])
            is_quiz_result = data.get('is_quiz_result', False)
            is_debug_requested = data.get('debug', False)

            if not user_message:
                yield json.dumps({"error": "未提供訊息", "done": True}, ensure_ascii=False) + "\n"
                return

            if not ai_service.check_health():
                yield json.dumps({"error": "Ollama 連線失敗，請確認是否已啟動 Ollama。", "done": True}, ensure_ascii=False) + "\n"
                return

            yield json.dumps({"status": "analyzing_intent"}, ensure_ascii=False) + "\n"
            is_cafe_related, matched_keywords = ai_service.classify_intent(user_message)
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
                    model_name = get_current_model()
                    extracted_data = ai_service.extract_preferences_via_llm(history, user_message, model_name)
                    
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
                        yield json.dumps({"response": "太好了！那請點擊下方卡片，我們馬上開始囉～\n\n[SHOW_QUIZ_CARD]"}, ensure_ascii=False) + "\n"
                        yield json.dumps({"response": "", "done": True}, ensure_ascii=False) + "\n"
                        return

            cafe_context = ""
            if is_cafe_related:
                yield json.dumps({"status": "retrieving_cafes"}, ensure_ascii=False) + "\n"
                cafe_context = ai_service.retrieve_cafe_context(matched_keywords, Cafes, Tags)
            else:
                yield json.dumps({"status": "general_chat"}, ensure_ascii=False) + "\n"

            trimmed_history = history[-10:] if history else []
            model_name = get_current_model()
            prompt_text = ai_service.build_prompt(user_message, trimmed_history, is_cafe_related, cafe_context, guide_instruction)

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

    resp = current_app.response_class(stream_with_context(generate_pipeline()), mimetype='application/x-ndjson')
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp

@chat_bp.route('/api/chat/feedback', methods=['POST'])
def chat_feedback():
    data = request.json
    feedback_type = data.get('feedback_type')
    user_message = data.get('user_message', '')
    ai_response = data.get('ai_response', '')
    user_email = session.get('user_email')
    
    user_id = None
    if user_email:
        user = User.query.filter_by(email=user_email).first()
        if user:
            user_id = user.id

    if not feedback_type:
        return jsonify({"success": False, "error": "Missing feedback type"}), 400

    try:
        feedback = ChatFeedback(
            user_id=user_id,
            user_message=user_message,
            ai_response=ai_response,
            feedback_type=feedback_type
        )
        db.session.add(feedback)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": "系統發生錯誤，請稍後再試"}), 500
