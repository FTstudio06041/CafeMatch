import uuid
import json
from datetime import datetime
from config.settings import get_utc_now
from flask import Blueprint, jsonify, request, session, stream_with_context, current_app, g
from database import db
from models import User, ChatSession, ChatFeedback
from services.chat_pipeline_service import ChatPipelineService
from utils.auth import login_required
from utils.response import error_response, success_response
from extensions import limiter

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/api/chat/sessions', methods=['GET'])
@login_required
def get_chat_sessions(user):
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
@login_required
def get_chat_session_detail(user, session_id):
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
    if not chat_session:
        return error_response("找不到該對話", 404)

    return jsonify({
        "id": chat_session.id,
        "title": chat_session.title,
        "messages": chat_session.messages,
        "updated_at": chat_session.updated_at.strftime('%Y-%m-%d %H:%M:%S') if chat_session.updated_at else None
    })

@chat_bp.route('/api/chat/sessions', methods=['POST'])
@login_required
def save_chat_session(user):
    data = request.json
    if len(json.dumps(data)) > 1024 * 1024:
        return error_response("Payload 過大", 413)

    session_id = data.get('id')
    title = data.get('title', '新對話')
    if len(title) > 100:
        title = title[:100]

    messages = data.get('messages', [])
    if len(messages) > 1000:
        return error_response("訊息數量過多", 413)

    allowed_roles = {'user', 'ai', 'system'}
    allowed_keys = {'role', 'content', 'feedback', 'debug_info', 'status', 'cafes'}
    cleaned_messages = []
    for msg in messages:
        if not isinstance(msg, dict):
            return error_response("訊息格式錯誤", 400)
        if msg.get('role') not in allowed_roles:
            return error_response("包含不合法的角色", 400)
        cleaned_msg = {k: v for k, v in msg.items() if k in allowed_keys}
        cleaned_messages.append(cleaned_msg)
    messages = cleaned_messages

    try:
        if session_id:
            chat_session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
            if not chat_session:
                return error_response("找不到該對話", 404)
            
            chat_session.title = title
            chat_session.messages = messages
            chat_session.updated_at = get_utc_now()
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
        return success_response({"id": chat_session.id})
    except Exception as e:
        db.session.rollback()
        return error_response("系統發生錯誤，請稍後再試", 500)

@chat_bp.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
@login_required
def delete_chat_session(user, session_id):
    try:
        chat_session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
        if not chat_session:
            return error_response("找不到該對話", 404)
        
        db.session.delete(chat_session)
        db.session.commit()
        return success_response()
    except Exception as e:
        db.session.rollback()
        return error_response("系統發生錯誤，請稍後再試", 500)

@chat_bp.route('/api/chat', methods=['POST'])
@limiter.limit("20 per minute")
def chat_with_ai():
    data = request.json
    is_debug_requested = data.get('debug', False)
    
    resp = current_app.response_class(
        stream_with_context(ChatPipelineService.generate_pipeline(data, is_debug_requested)), 
        mimetype='application/x-ndjson'
    )
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp

@chat_bp.route('/api/chat/feedback', methods=['POST'])
@limiter.limit("30 per minute")
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
        return error_response("Missing feedback type", 400)

    try:
        feedback = ChatFeedback(
            user_id=user_id,
            user_message=user_message,
            ai_response=ai_response,
            feedback_type=feedback_type
        )
        db.session.add(feedback)
        db.session.commit()
        return success_response()
    except Exception as e:
        db.session.rollback()
        return error_response("系統發生錯誤，請稍後再試", 500)
