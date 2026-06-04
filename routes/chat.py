import uuid
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
    session_id = data.get('id')
    title = data.get('title', '新對話')
    messages = data.get('messages', [])

    try:
        chat_session = None
        if session_id:
            chat_session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
        
        if chat_session:
            chat_session.title = title
            chat_session.messages = messages
            chat_session.updated_at = datetime.utcnow()
        else:
            new_id = session_id if session_id else str(uuid.uuid4())
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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

def get_current_model():
    if 'OLLAMA_MODEL' not in current_app.config or not current_app.config['OLLAMA_MODEL']:
        current_app.config['OLLAMA_MODEL'] = ai_service.get_default_model()
    return current_app.config['OLLAMA_MODEL']

@chat_bp.route('/api/chat', methods=['POST'])
def chat_with_ai():
    try:
        data = request.json
        user_message = data.get('message', '')
        history = data.get('history', [])

        if not user_message:
            return jsonify({"error": "未提供訊息"}), 400

        if not ai_service.check_health():
            return jsonify({"error": "Ollama 連線失敗，請確認是否已啟動 Ollama。"}), 503

        is_cafe_related, matched_keywords = ai_service.classify_intent(user_message)
        cafe_context = ""
        if is_cafe_related:
            cafe_context = ai_service.retrieve_cafe_context(matched_keywords, Cafes, Tags)

        guide_instruction = None
        if is_cafe_related:
            guide_instruction = conversation_guide.analyze_and_guide(history)

        model_name = get_current_model()
        prompt_text = ai_service.build_prompt(user_message, history, is_cafe_related, cafe_context, guide_instruction)

        user_id = None
        user_email = session.get('user_email')
        if user_email:
            current_user = User.query.filter_by(email=user_email).first()
            if current_user:
                user_id = current_user.id

        generator = ai_service.stream_generate(
            model_name=model_name,
            prompt_text=prompt_text,
            is_cafe_related=is_cafe_related,
            cafe_context=cafe_context,
            db=db,
            AiQueryLog=AiQueryLog,
            user_id=user_id
        )

        resp = current_app.response_class(stream_with_context(generator), mimetype='application/x-ndjson')
        resp.headers['Cache-Control'] = 'no-cache'
        resp.headers['X-Accel-Buffering'] = 'no'
        return resp

    except Exception as e:
        current_app.logger.error("Chat API Error:", e)
        return jsonify({"error": "系統發生未知的錯誤"}), 500

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
        return jsonify({"success": False, "error": str(e)}), 500
