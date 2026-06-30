from datetime import datetime, timedelta
from config.settings import get_utc_now
from sqlalchemy import func
import logging
from database import db
from models import User, CommunityNote, CommunityLike, CommunityComment

class NoteService:
    @staticmethod
    def get_notes(current_user=None):
        twenty_four_hours_ago = get_utc_now() - timedelta(hours=24)
        notes = CommunityNote.query.filter(CommunityNote.created_at >= twenty_four_hours_ago).order_by(CommunityNote.created_at.desc()).all()
        result = []
        if not notes:
            return result

        user_ids = {n.user_id for n in notes}
        users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
        note_ids = [n.id for n in notes]

        like_counts_q = db.session.query(CommunityLike.note_id, func.count(CommunityLike.id)).filter(CommunityLike.note_id.in_(note_ids)).group_by(CommunityLike.note_id).all()
        like_counts = {nid: cnt for nid, cnt in like_counts_q}

        comment_counts_q = db.session.query(CommunityComment.note_id, func.count(CommunityComment.id)).filter(CommunityComment.note_id.in_(note_ids)).group_by(CommunityComment.note_id).all()
        comment_counts = {nid: cnt for nid, cnt in comment_counts_q}

        user_liked_set = set()
        if current_user:
            user_likes = CommunityLike.query.filter(CommunityLike.note_id.in_(note_ids), CommunityLike.user_id == current_user.id).all()
            user_liked_set = {like.note_id for like in user_likes}

        for note in notes:
            author = users.get(note.user_id)
            result.append({
                'id': note.id,
                'content': note.content,
                'color_index': note.color_index,
                'created_at': note.created_at.strftime('%Y-%m-%d %H:%M') if note.created_at else '',
                'user_name': author.name if author else '匿名',
                'user_picture': author.picture if author else '',
                'user_email': author.email if author else '',
                'like_count': like_counts.get(note.id, 0),
                'comment_count': comment_counts.get(note.id, 0),
                'is_liked': note.id in user_liked_set
            })
        return result

    @staticmethod
    def create_or_update_note(user, content, color_index):
        existing_note = CommunityNote.query.filter_by(user_id=user.id).first()
        if existing_note:
            existing_note.content = content
            existing_note.color_index = color_index
            existing_note.created_at = get_utc_now()
            note = existing_note
        else:
            note = CommunityNote(
                user_id=user.id,
                content=content,
                color_index=color_index
            )
            db.session.add(note)
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating/updating note: {e}")
            return None
        return {
            'id': note.id,
            'content': note.content,
            'color_index': note.color_index,
            'created_at': note.created_at.strftime('%Y-%m-%d %H:%M') if note.created_at else '',
            'user_name': user.name,
            'user_picture': user.picture or '',
            'like_count': 0,
            'comment_count': 0,
            'is_liked': False
        }

    @staticmethod
    def delete_note(user, note_id):
        note = CommunityNote.query.get(note_id)
        if not note:
            return False, '便利貼不存在'
        if note.user_id != user.id:
            return False, '只能刪除自己的便利貼'

        CommunityLike.query.filter_by(note_id=note_id).delete()
        CommunityComment.query.filter_by(note_id=note_id).delete()
        db.session.delete(note)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting note: {e}")
            return False, '系統錯誤'
        return True, ''

    @staticmethod
    def toggle_like_note(user, note_id):
        note = CommunityNote.query.get(note_id)
        if not note:
            return False, '便利貼不存在', None

        existing_like = CommunityLike.query.filter_by(
            user_id=user.id, note_id=note_id
        ).first()

        if existing_like:
            db.session.delete(existing_like)
            is_liked = False
        else:
            new_like = CommunityLike(user_id=user.id, note_id=note_id)
            db.session.add(new_like)
            is_liked = True

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error toggling note like: {e}")
            return False, '系統錯誤', None
        like_count = CommunityLike.query.filter_by(note_id=note_id).count()
        return True, is_liked, like_count

    @staticmethod
    def get_note_comments(note_id):
        comments = CommunityComment.query.filter_by(note_id=note_id).order_by(CommunityComment.created_at.desc()).all()
        user_ids = list(set([c.user_id for c in comments]))
        users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
        
        result = []
        for c in comments:
            author = users.get(c.user_id)
            result.append({
                'id': c.id,
                'content': c.content,
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'author': {
                    'name': author.name if author else '未知',
                    'email': author.email if author else '',
                    'avatar': author.picture if author else None
                }
            })
        return result

    @staticmethod
    def create_note_comment(user, note_id, content):
        note = CommunityNote.query.get(note_id)
        if not note:
            return False, '便利貼不存在', None
        
        comment = CommunityComment(
            user_id=user.id,
            note_id=note_id,
            content=content
        )
        db.session.add(comment)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating comment: {e}")
            return False, '系統錯誤', None

        return True, '', {
            'id': comment.id,
            'content': comment.content,
            'user_name': user.name,
            'user_picture': user.picture or '',
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M') if comment.created_at else ''
        }
