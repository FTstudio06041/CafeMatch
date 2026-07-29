from database import db
from datetime import datetime
from config.settings import get_utc_now
import uuid

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    messages = db.Column(db.JSON, nullable=False, default=list)
    # 累積偏好狀態：{"preferences": {...}, "progress_base": 0|50}
    # 讓偏好掌握度與已確認維度跨重新整理／重開對話仍然保留
    pref_state = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    updated_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)

class ChatFeedback(db.Model):
    __tablename__ = 'chat_feedbacks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_message = db.Column(db.Text, nullable=True)
    ai_response = db.Column(db.Text, nullable=True)
    feedback_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)

class AiQueryLog(db.Model):
    __tablename__ = 'ai_query_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    model_name = db.Column(db.String(100), nullable=False)
    prompt_tokens = db.Column(db.Integer, default=0)
    completion_tokens = db.Column(db.Integer, default=0)
    total_time_ms = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=get_utc_now)
