"""店家詳情裡的社群功能：評論（評論即社群）與 24 小時現況回報。"""

from flask import Blueprint, current_app, request

from extensions import limiter
from services import cafe_report_service, cafe_review_service
from services.cafe_review_service import ReviewError
from utils.auth import get_current_user, login_required
from utils.response import error_response, success_response

cafe_community_bp = Blueprint('cafe_community', __name__)


def _handle(action, *args, **kwargs):
    """統一處理 ReviewError（可直接回給使用者）與非預期錯誤。"""
    try:
        return action(*args, **kwargs), None
    except ReviewError as e:
        return None, error_response(e.message, e.status)
    except Exception as e:
        current_app.logger.error(f'{action.__name__} 失敗：{e}')
        return None, error_response('系統發生錯誤，請稍後再試', 500)


def _json():
    return request.get_json(silent=True) or {}


# ---------- 評論 ----------

@cafe_community_bp.route('/api/cafes/<int:cafe_id>/reviews', methods=['GET'])
def get_reviews(cafe_id):
    data, err = _handle(cafe_review_service.list_reviews, cafe_id, get_current_user(),
                        page=request.args.get('page', 1, type=int),
                        per_page=request.args.get('per_page', 10, type=int))
    return err or success_response(data)


@cafe_community_bp.route('/api/cafes/<int:cafe_id>/reviews', methods=['POST'])
@limiter.limit("10 per minute")
@login_required
def save_review(user, cafe_id):
    body = _json()
    review, err = _handle(cafe_review_service.upsert_review, user, cafe_id,
                          body.get('rating'), body.get('content'))
    if err:
        return err
    return success_response({'review': review,
                             'summary': cafe_review_service.review_summary(cafe_id)})


@cafe_community_bp.route('/api/reviews/<int:review_id>', methods=['DELETE'])
@login_required
def remove_review(user, review_id):
    _, err = _handle(cafe_review_service.delete_review, user, review_id)
    return err or success_response()


@cafe_community_bp.route('/api/reviews/<int:review_id>/like', methods=['POST'])
@limiter.limit("60 per minute")
@login_required
def like_review(user, review_id):
    data, err = _handle(cafe_review_service.toggle_like, user, review_id)
    return err or success_response(data)


@cafe_community_bp.route('/api/reviews/<int:review_id>/comments', methods=['GET'])
def get_review_comments(review_id):
    data, err = _handle(cafe_review_service.list_comments, review_id, get_current_user())
    return err or success_response({'comments': data})


@cafe_community_bp.route('/api/reviews/<int:review_id>/comments', methods=['POST'])
@limiter.limit("20 per minute")
@login_required
def add_review_comment(user, review_id):
    data, err = _handle(cafe_review_service.add_comment, user, review_id, _json().get('content'))
    return err or success_response({'comment': data})


@cafe_community_bp.route('/api/reviews/<int:review_id>/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def remove_review_comment(user, review_id, comment_id):
    _, err = _handle(cafe_review_service.delete_comment, user, review_id, comment_id)
    return err or success_response()


# ---------- 24 小時現況回報 ----------

@cafe_community_bp.route('/api/cafes/<int:cafe_id>/reports', methods=['GET'])
def get_reports(cafe_id):
    data, err = _handle(cafe_report_service.list_reports, cafe_id, get_current_user())
    if err:
        return err
    return success_response({'reports': data, 'quick_reports': list(cafe_report_service.QUICK_REPORTS)})


@cafe_community_bp.route('/api/cafes/<int:cafe_id>/reports', methods=['POST'])
@limiter.limit("10 per minute")
@login_required
def save_report(user, cafe_id):
    data, err = _handle(cafe_report_service.create_report, user, cafe_id, _json().get('content'))
    return err or success_response({'report': data})


@cafe_community_bp.route('/api/reports/<int:report_id>', methods=['DELETE'])
@login_required
def remove_report(user, report_id):
    _, err = _handle(cafe_report_service.delete_report, user, report_id)
    return err or success_response()


@cafe_community_bp.route('/api/reports/<int:report_id>/confirm', methods=['POST'])
@limiter.limit("60 per minute")
@login_required
def confirm_report(user, report_id):
    data, err = _handle(cafe_report_service.toggle_confirm, user, report_id)
    return err or success_response(data)
