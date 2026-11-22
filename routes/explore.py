import requests
from flask import Blueprint, jsonify, request, redirect, current_app
from database import db
from extensions import limiter
from models import Cafes, UserQuizResult
from utils.auth import get_current_user
from utils.response import error_response
from services.cafe_explore_service import get_cafes_data
from services.google_maps_service import has_google_maps_key, get_google_photo_uri
from services.home_recommend_service import DIMS, parse_scores, recommend_for_home

explore_bp = Blueprint('explore', __name__)

@explore_bp.route('/api/cafes', methods=['GET'])
def get_cafes():
    try:
        current_user = get_current_user()
        results = get_cafes_data(current_user)
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Database Error: {e}")
        return error_response("系統發生錯誤，請稍後再試", 500)


def _latest_quiz_scores(user):
    record = UserQuizResult.query.filter_by(user_id=user.id) \
        .order_by(UserQuizResult.created_at.desc()).first()
    if not record:
        return None
    return parse_scores({
        'work': record.score_work, 'env': record.score_env, 'social': record.score_social,
        'taste': record.score_taste, 'cp': record.score_cp,
    })


@explore_bp.route('/api/cafes/recommended', methods=['GET'])
@limiter.limit("30 per minute")
def get_recommended_cafes():
    """
    首頁「你可能會喜歡」。

    登入者用資料庫裡最近一次的測驗分數；未登入但在這台裝置做過測驗的人，
    前端會把分數放在 query string（work=..&env=..）帶過來。
    """
    try:
        current_user = get_current_user()
        scores = _latest_quiz_scores(current_user) if current_user else None
        if scores is None and all(d in request.args for d in DIMS):
            scores = parse_scores({d: request.args.get(d) for d in DIMS})
        limit = max(1, min(request.args.get('limit', 8, type=int), 20))
        cafe_ids = [cid for (cid,) in db.session.query(Cafes.id).order_by(Cafes.id).all()]
        return jsonify(recommend_for_home(cafe_ids, scores=scores, limit=limit))
    except Exception as e:
        current_app.logger.error(f"Recommend Error: {e}")
        return error_response("系統發生錯誤，請稍後再試", 500)


@explore_bp.route('/api/cafes/<int:cafe_id>/photo', methods=['GET'])
def get_cafe_photo(cafe_id):
    cafe = Cafes.query.get_or_404(cafe_id)

    if not has_google_maps_key():
        return jsonify({'error': 'Google Maps API key is not configured'}), 503

    try:
        max_width = request.args.get('width', 900, type=int)
        photo_uri = get_google_photo_uri(cafe, max_width=max_width)
        if not photo_uri:
            return jsonify({'error': 'No Google photo found for this cafe'}), 404
        return redirect(photo_uri, code=302)
    except requests.RequestException as e:
        current_app.logger.error(f'Google Places photo error for cafe {cafe_id}: {e}')
        db.session.rollback()
        return jsonify({'error': 'Failed to fetch Google photo'}), 502
    except Exception as e:
        current_app.logger.error(f'Cafe photo error for cafe {cafe_id}: {e}')
        db.session.rollback()
        return error_response("系統發生錯誤，請稍後再試", 500)
