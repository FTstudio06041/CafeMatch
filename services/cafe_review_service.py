"""
cafe_review_service.py — 店家評論（評論即社群）

評論沿用 community_posts：綁定 cafe_id 且有 rating（1~5）的貼文就是評論。
  - 每人每店一則，再送一次就是編輯（不會冒出第二則）
  - 按讚、留言沿用 post_likes / post_comments
  - 對外不回傳 email：店家詳情是公開頁面，作者只顯示名稱與頭像
"""

import logging
import math

from sqlalchemy import func

from config.settings import get_utc_now
from database import db
from models import Cafes, CommunityPost, PostComment, PostLike, User

REVIEW_MAX_LENGTH = 1000
COMMENT_MAX_LENGTH = 300
DEFAULT_PER_PAGE = 10


class ReviewError(Exception):
    """可直接回給使用者的錯誤（訊息 + HTTP 狀態碼）。"""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _fmt_time(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z' if dt else ''


def _author(user):
    return {'name': user.name if user else '匿名', 'picture': (user.picture or '') if user else ''}


def _review_query(cafe_id):
    return CommunityPost.query.filter(
        CommunityPost.cafe_id == cafe_id, CommunityPost.rating.isnot(None)
    )


def _get_review(review_id):
    review = db.session.get(CommunityPost, review_id)
    if not review or review.rating is None or review.cafe_id is None:
        raise ReviewError('評論不存在', 404)
    return review


def _serialize_reviews(reviews, current_user):
    if not reviews:
        return []
    ids = [r.id for r in reviews]
    users = {u.id: u for u in User.query.filter(User.id.in_({r.user_id for r in reviews})).all()}
    like_counts = dict(db.session.query(PostLike.post_id, func.count(PostLike.id))
                       .filter(PostLike.post_id.in_(ids)).group_by(PostLike.post_id).all())
    comment_counts = dict(db.session.query(PostComment.post_id, func.count(PostComment.id))
                          .filter(PostComment.post_id.in_(ids)).group_by(PostComment.post_id).all())
    liked = set()
    if current_user:
        liked = {pid for (pid,) in db.session.query(PostLike.post_id)
                 .filter(PostLike.post_id.in_(ids), PostLike.user_id == current_user.id).all()}

    return [{
        'id': r.id,
        'rating': r.rating,
        'content': r.content or '',
        'created_at': _fmt_time(r.created_at),
        'updated_at': _fmt_time(r.updated_at),
        'author': _author(users.get(r.user_id)),
        'is_mine': bool(current_user and r.user_id == current_user.id),
        'like_count': like_counts.get(r.id, 0),
        'is_liked': r.id in liked,
        'comment_count': comment_counts.get(r.id, 0),
    } for r in reviews]


def review_summary(cafe_id):
    rows = db.session.query(CommunityPost.rating, func.count(CommunityPost.id)).filter(
        CommunityPost.cafe_id == cafe_id, CommunityPost.rating.isnot(None)
    ).group_by(CommunityPost.rating).all()
    distribution = {str(star): 0 for star in range(1, 6)}
    total = 0
    weighted = 0
    for rating, cnt in rows:
        if 1 <= rating <= 5:
            distribution[str(rating)] = cnt
            total += cnt
            weighted += rating * cnt
    return {
        'average': round(weighted / total, 1) if total else None,
        'count': total,
        'distribution': distribution,
    }


def list_reviews(cafe_id, current_user, page=1, per_page=DEFAULT_PER_PAGE):
    if not db.session.get(Cafes, cafe_id):
        raise ReviewError('找不到這家店', 404)
    per_page = max(1, min(int(per_page or DEFAULT_PER_PAGE), 50))
    page = max(1, int(page or 1))

    query = _review_query(cafe_id)
    if current_user:
        # 自己的評論另外放在 my_review，不在列表裡重複出現
        query = query.filter(CommunityPost.user_id != current_user.id)
    total = query.count()
    reviews = query.order_by(CommunityPost.created_at.desc(), CommunityPost.id.desc()) \
        .offset((page - 1) * per_page).limit(per_page).all()

    my_review = None
    if current_user:
        mine = _review_query(cafe_id).filter(CommunityPost.user_id == current_user.id).first()
        if mine:
            my_review = _serialize_reviews([mine], current_user)[0]

    return {
        'summary': review_summary(cafe_id),
        'my_review': my_review,
        'reviews': _serialize_reviews(reviews, current_user),
        'page': page,
        'pages': max(1, math.ceil(total / per_page)),
        'total': total,
    }


def upsert_review(user, cafe_id, rating, content):
    if not db.session.get(Cafes, cafe_id):
        raise ReviewError('找不到這家店', 404)
    # bool 是 int 的子類別、4.5 用 int() 會被無聲截斷，兩者都要先擋
    if isinstance(rating, bool) or (isinstance(rating, float) and not rating.is_integer()):
        raise ReviewError('請選擇 1 到 5 顆星')
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        raise ReviewError('請選擇 1 到 5 顆星')
    if not 1 <= rating <= 5:
        raise ReviewError('請選擇 1 到 5 顆星')
    content = (content or '').strip()
    if len(content) > REVIEW_MAX_LENGTH:
        raise ReviewError(f'評論不可超過 {REVIEW_MAX_LENGTH} 字')

    review = _review_query(cafe_id).filter(CommunityPost.user_id == user.id).first()
    if review:
        review.rating = rating
        review.content = content
        review.updated_at = get_utc_now()
    else:
        review = CommunityPost(user_id=user.id, cafe_id=cafe_id, rating=rating, content=content)
        db.session.add(review)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f'儲存店家評論失敗：{e}')
        raise ReviewError('系統錯誤，請稍後再試', 500)
    return _serialize_reviews([review], user)[0]


def delete_review(user, review_id):
    review = _get_review(review_id)
    if review.user_id != user.id and not user.is_admin:
        raise ReviewError('只能刪除自己的評論', 403)
    PostLike.query.filter_by(post_id=review.id).delete()
    PostComment.query.filter_by(post_id=review.id).delete()
    db.session.delete(review)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f'刪除店家評論失敗：{e}')
        raise ReviewError('系統錯誤，請稍後再試', 500)


def toggle_like(user, review_id):
    review = _get_review(review_id)
    existing = PostLike.query.filter_by(post_id=review.id, user_id=user.id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(PostLike(user_id=user.id, post_id=review.id))
        liked = True
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f'評論按讚失敗：{e}')
        raise ReviewError('系統錯誤，請稍後再試', 500)
    return {'liked': liked, 'like_count': PostLike.query.filter_by(post_id=review.id).count()}


def _serialize_comment(comment, author, current_user):
    return {
        'id': comment.id,
        'content': comment.content,
        'created_at': _fmt_time(comment.created_at),
        'author': _author(author),
        'is_mine': bool(current_user and comment.user_id == current_user.id),
    }


def list_comments(review_id, current_user):
    review = _get_review(review_id)
    comments = PostComment.query.filter_by(post_id=review.id) \
        .order_by(PostComment.created_at.asc(), PostComment.id.asc()).all()
    users = {u.id: u for u in User.query.filter(User.id.in_({c.user_id for c in comments})).all()} if comments else {}
    return [_serialize_comment(c, users.get(c.user_id), current_user) for c in comments]


def add_comment(user, review_id, content):
    review = _get_review(review_id)
    content = (content or '').strip()
    if not content:
        raise ReviewError('留言內容不可為空')
    if len(content) > COMMENT_MAX_LENGTH:
        raise ReviewError(f'留言不可超過 {COMMENT_MAX_LENGTH} 字')
    comment = PostComment(user_id=user.id, post_id=review.id, content=content)
    db.session.add(comment)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f'新增評論留言失敗：{e}')
        raise ReviewError('系統錯誤，請稍後再試', 500)
    return _serialize_comment(comment, user, user)


def delete_comment(user, review_id, comment_id):
    _get_review(review_id)
    comment = db.session.get(PostComment, comment_id)
    if not comment or comment.post_id != review_id:
        raise ReviewError('留言不存在', 404)
    if comment.user_id != user.id and not user.is_admin:
        raise ReviewError('只能刪除自己的留言', 403)
    db.session.delete(comment)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f'刪除評論留言失敗：{e}')
        raise ReviewError('系統錯誤，請稍後再試', 500)
