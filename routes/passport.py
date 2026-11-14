"""咖啡護照、咖啡盲盒與滑卡的 API。"""

from flask import Blueprint, current_app, jsonify, request

from database import db
from services import blindbox_service, passport_service, swipe_service
from utils.auth import login_required
from utils.response import error_response

passport_bp = Blueprint('passport', __name__)


@passport_bp.route('/api/passport', methods=['GET'])
@login_required
def get_passport(user):
    try:
        return jsonify(passport_service.get_passport(user))
    except Exception:
        current_app.logger.exception('[passport] 讀取失敗')
        return error_response('系統發生錯誤，請稍後再試', 500)


@passport_bp.route('/api/user/shop_states', methods=['GET'])
@login_required
def get_shop_states(user):
    """聊天推薦卡片用：一次拿到所有收藏／去過的狀態。"""
    states = passport_service.get_shop_states(user.id)
    return jsonify({str(k): v for k, v in states.items()})


@passport_bp.route('/api/blindbox', methods=['GET'])
@login_required
def get_blindbox(user):
    try:
        box = blindbox_service.get_or_create_current(user.id)
        return jsonify({
            'box': blindbox_service.serialize(box, user.id),
            'history': blindbox_service.history(user.id, exclude_id=box.id if box else None),
        })
    except Exception:
        db.session.rollback()
        current_app.logger.exception('[blindbox] 讀取失敗')
        return error_response('系統發生錯誤，請稍後再試', 500)


@passport_bp.route('/api/blindbox/open', methods=['POST'])
@login_required
def open_blindbox(user):
    box = blindbox_service.open_box(user.id)
    if not box:
        return error_response('今天沒有可以拆的盒子', 404)
    return jsonify({'box': blindbox_service.serialize(box, user.id)})


@passport_bp.route('/api/blindbox/reroll', methods=['POST'])
@login_required
def reroll_blindbox(user):
    reason = (request.json or {}).get('reason')
    box, err = blindbox_service.reroll(user.id, reason)
    if err:
        return error_response(err, 400)
    return jsonify({'box': blindbox_service.serialize(box, user.id)})


@passport_bp.route('/api/blindbox/<int:box_id>/rate', methods=['POST'])
@login_required
def rate_blindbox(user, box_id):
    data = request.json or {}
    box, err = blindbox_service.rate(user.id, box_id, data.get('rating'), data.get('comment'))
    if err:
        return error_response(err, 400)
    return jsonify({'box': blindbox_service.serialize(box, user.id)})


# ==========================================
# 滑卡（護照頁）
# ==========================================

@passport_bp.route('/api/swipe/deck', methods=['GET'])
@login_required
def get_swipe_deck(user):
    return jsonify(swipe_service.deck(user.id))


@passport_bp.route('/api/swipe', methods=['POST'])
@login_required
def post_swipe(user):
    data = request.json or {}
    cafe_id = data.get('cafe_id')
    if not isinstance(cafe_id, int) or isinstance(cafe_id, bool):
        return error_response('參數錯誤', 400)
    result, err = swipe_service.swipe(user.id, cafe_id, data.get('direction'))
    if err:
        return error_response(err, 400)
    return jsonify({'success': True, **result})


@passport_bp.route('/api/swipe/undo', methods=['POST'])
@login_required
def undo_swipe(user):
    result, err = swipe_service.undo(user.id)
    if err:
        return error_response(err, 400)
    return jsonify({'success': True, **result})


@passport_bp.route('/api/swipe/reset', methods=['POST'])
@login_required
def reset_swipes(user):
    return jsonify({'success': True, 'restored': swipe_service.reset_passed(user.id)})
