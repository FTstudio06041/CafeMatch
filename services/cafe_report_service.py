"""
cafe_report_service.py — 店家的 24 小時現況回報

沿用舊的便利貼（community_notes）：綁定 cafe_id 的便利貼就是現況回報，
例如「現在人很多」「還有插座位」，24 小時後自動不再顯示（資料不刪）。
  - 每人每店同時只有一則有效回報，再回報一次就是更新內容並重新計時
  - 「我也看到了」沿用便利貼按讚（community_likes）
"""

import logging
from datetime import timedelta

from sqlalchemy import func

from config.settings import get_utc_now
from database import db
from models import Cafes, CommunityComment, CommunityLike, CommunityNote, User
from services.cafe_review_service import ReviewError, _author, _fmt_time

REPORT_MAX_LENGTH = 100
REPORT_TTL = timedelta(hours=24)
# 前端的快速選項，也是後端唯一認得的「預設回報」—— 只是方便點選，
# 使用者仍可自己打字
QUICK_REPORTS = ('現在人很多', '還有空位', '有插座位', '很安靜', '有點吵', '今天有營業')


def _active_query(cafe_id):
    since = get_utc_now() - REPORT_TTL
    return CommunityNote.query.filter(
        CommunityNote.cafe_id == cafe_id, CommunityNote.created_at >= since
    )


def _get_report(report_id):
    report = db.session.get(CommunityNote, report_id)
    if not report or report.cafe_id is None:
        raise ReviewError('回報不存在', 404)
    return report


def list_reports(cafe_id, current_user):
    if not db.session.get(Cafes, cafe_id):
        raise ReviewError('找不到這家店', 404)
    reports = _active_query(cafe_id).order_by(CommunityNote.created_at.desc()).all()
    if not reports:
        return []
    ids = [r.id for r in reports]
    users = {u.id: u for u in User.query.filter(User.id.in_({r.user_id for r in reports})).all()}
    like_counts = dict(db.session.query(CommunityLike.note_id, func.count(CommunityLike.id))
                       .filter(CommunityLike.note_id.in_(ids)).group_by(CommunityLike.note_id).all())
    liked = set()
    if current_user:
        liked = {nid for (nid,) in db.session.query(CommunityLike.note_id)
                 .filter(CommunityLike.note_id.in_(ids), CommunityLike.user_id == current_user.id).all()}
    return [{
        'id': r.id,
        'content': r.content,
        'created_at': _fmt_time(r.created_at),
        'author': _author(users.get(r.user_id)),
        'is_mine': bool(current_user and r.user_id == current_user.id),
        'confirm_count': like_counts.get(r.id, 0),
        'is_confirmed': r.id in liked,
    } for r in reports]


def create_report(user, cafe_id, content):
    if not db.session.get(Cafes, cafe_id):
        raise ReviewError('找不到這家店', 404)
    content = (content or '').strip()
    if not content:
        raise ReviewError('回報內容不可為空')
    if len(content) > REPORT_MAX_LENGTH:
        raise ReviewError(f'回報不可超過 {REPORT_MAX_LENGTH} 字')

    report = _active_query(cafe_id).filter(CommunityNote.user_id == user.id).first()
    if report:
        # 重新回報：內容換新、重新計時；舊的「我也看到了」不再適用
        CommunityLike.query.filter_by(note_id=report.id).delete()
        report.content = content
        report.created_at = get_utc_now()
    else:
        report = CommunityNote(user_id=user.id, cafe_id=cafe_id, content=content, color_index=0)
        db.session.add(report)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f'儲存現況回報失敗：{e}')
        raise ReviewError('系統錯誤，請稍後再試', 500)
    return {
        'id': report.id,
        'content': report.content,
        'created_at': _fmt_time(report.created_at),
        'author': _author(user),
        'is_mine': True,
        'confirm_count': 0,
        'is_confirmed': False,
    }


def delete_report(user, report_id):
    report = _get_report(report_id)
    if report.user_id != user.id and not user.is_admin:
        raise ReviewError('只能刪除自己的回報', 403)
    CommunityLike.query.filter_by(note_id=report.id).delete()
    CommunityComment.query.filter_by(note_id=report.id).delete()
    db.session.delete(report)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f'刪除現況回報失敗：{e}')
        raise ReviewError('系統錯誤，請稍後再試', 500)


def toggle_confirm(user, report_id):
    report = _get_report(report_id)
    if report.created_at and report.created_at.replace(tzinfo=None) < (get_utc_now() - REPORT_TTL).replace(tzinfo=None):
        raise ReviewError('這則回報已經過期', 410)
    existing = CommunityLike.query.filter_by(note_id=report.id, user_id=user.id).first()
    if existing:
        db.session.delete(existing)
        confirmed = False
    else:
        db.session.add(CommunityLike(user_id=user.id, note_id=report.id))
        confirmed = True
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f'現況回報確認失敗：{e}')
        raise ReviewError('系統錯誤，請稍後再試', 500)
    return {'confirmed': confirmed,
            'confirm_count': CommunityLike.query.filter_by(note_id=report.id).count()}
