from database import db
from datetime import datetime
from config.settings import get_utc_now

class AdminLog(db.Model):
    __tablename__ = 'admin_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_utc_now)

class SystemAnnouncement(db.Model):
    __tablename__ = 'system_announcements'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    updated_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)

class BugReport(db.Model):
    __tablename__ = 'bug_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    report_type = db.Column(db.String(50), default='bug')
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)

class SystemSetting(db.Model):
    """跨 worker / 跨重啟持久化的執行期設定（key/value）。"""
    __tablename__ = 'system_settings'
    setting_key = db.Column(db.String(100), primary_key=True)
    setting_value = db.Column(db.Text)
