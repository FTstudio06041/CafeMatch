"""咖啡護照與咖啡盲盒的 API。"""

from flask import Blueprint, current_app, jsonify, request

from database import db
from services import blindbox_service, passport_service
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
        return error_response('這週沒有可以拆的盒子', 404)
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
