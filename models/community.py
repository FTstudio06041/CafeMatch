from database import db
from datetime import datetime
from config.settings import get_utc_now

class CommunityPost(db.Model):
    __tablename__ = 'community_posts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    cafe_id = db.Column(db.Integer, nullable=True)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.Text, nullable=True)
    original_post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=True)
    # 有星等（1~5）且綁定 cafe_id 的貼文就是店家評論：每人每店一則，
    # 按讚與留言沿用 post_likes / post_comments（評論即社群）
    rating = db.Column(db.SmallInteger, nullable=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    updated_at = db.Column(db.DateTime, nullable=True)

class PostLike(db.Model):
    __tablename__ = 'post_likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='uix_user_post_like'),)

class PostComment(db.Model):
    __tablename__ = 'post_comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)

class CommunityNote(db.Model):
    __tablename__ = 'community_notes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.String(100), nullable=False)
    color_index = db.Column(db.Integer, default=0)
    # 綁定 cafe_id 的便利貼是店家的「24 小時現況回報」；NULL 是舊的全站便利貼
    cafe_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)

class CommunityLike(db.Model):
    __tablename__ = 'community_likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note_id = db.Column(db.Integer, db.ForeignKey('community_notes.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    __table_args__ = (db.UniqueConstraint('user_id', 'note_id', name='uix_user_note_like'),)

class CommunityComment(db.Model):
    __tablename__ = 'community_comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note_id = db.Column(db.Integer, db.ForeignKey('community_notes.id'), nullable=False)
    content = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)
