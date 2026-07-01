from flask import Blueprint, jsonify, current_app
from services import situational_service

situational_bp = Blueprint('situational', __name__)


@situational_bp.route('/api/situational/questions', methods=['GET'])
def situational_get_questions():
    """提供 chat 情境元件的題目定義。提交走 /api/chat（帶 situational_context）。"""
    try:
        questions = situational_service.get_questions()
        return jsonify({"questions": questions})
    except Exception as e:
        current_app.logger.error(f'情境題目讀取錯誤：{e}')
        return jsonify({"questions": [], "error": "系統發生錯誤"}), 500
