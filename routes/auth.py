import os
from flask import Blueprint, session, redirect, url_for, request, jsonify, current_app
from extensions import oauth
from database import db
from models import User, UserShopState
from services.admin_service import AdminService
from utils.auth import login_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    # Use url_for with _external=True to generate the callback URL based on the blueprint
    # Wait, the old callback URL was hardcoded or url_for('authorize').
    # Let's map it to auth.authorize
    redirect_uri = os.getenv('GOOGLE_CALLBACK_URL', url_for('auth.authorize', _external=True))
    return oauth.google.authorize_redirect(redirect_uri, prompt='select_account')

@auth_bp.route('/auth/callback')
def authorize():
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173/')

    # Google 回呼失敗不能讓使用者看到 500。常見原因：
    # - 從 www.cafematch.net 開始登入，但回呼網址是 cafematch.net，
    #   兩個網域的 session cookie 不共用 → state 對不上（MismatchingStateError）
    # - 在 callback 頁按重新整理／上一頁，同一個 code 被重複兌換（invalid_grant）
    # - 使用者在 Google 頁面按取消（帶 error=access_denied 回來）
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo') or {}
        google_email = user_info['email']
    except Exception as e:
        current_app.logger.warning(
            'Google OAuth callback 失敗 (host=%s, error=%s): %r',
            request.host, request.args.get('error'), e,
        )
        return redirect(f'{frontend_url}?login_error=1')

    google_name = user_info.get('name') or google_email.split('@')[0]
    google_picture = user_info.get('picture')

    user = User.query.filter_by(email=google_email).first()
    is_new_user = False

    if not user:
        new_user = User(email=google_email, name=google_name, picture=google_picture)
        db.session.add(new_user)
        db.session.commit()
        is_new_user = True

    session['user_email'] = google_email
    AdminService.log_action(google_email, '登入', '新用戶' if is_new_user else '既有用戶')


    if is_new_user:
        # 新用戶強制先完成心理測驗，才能開始使用聊天
        return redirect(f'{frontend_url}quiz?welcome=true')
    else:
        return redirect(f'{frontend_url}chat')
    
@auth_bp.route('/logout')
def logout():
    user_email = session.get('user_email')
    if user_email:
        AdminService.log_action(user_email, '登出')
    session.pop('user_email', None)
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173/')
    return redirect(frontend_url)

@auth_bp.route('/api/me')
def get_current_user():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"is_logged_in": False}), 401

    user = User.query.filter_by(email=user_email).first()
    if user:
        return jsonify({
            "is_logged_in": True,
            "name": user.name,
            "email": user.email,
            "picture": user.picture,
            "is_admin": user.is_admin
        })
    else:
        return jsonify({"is_logged_in": False}), 401

@auth_bp.route('/api/user/update', methods=['POST'])
@login_required
def update_user_profile(user):
    try:
        data = request.json or {}
        new_name = data.get('name')
        new_avatar = data.get('picture')

        if new_name:
            user.name = new_name
        if new_avatar:
            user.picture = new_avatar

        db.session.commit()
        return jsonify({"success": True, "name": user.name, "picture": user.picture})
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "系統發生錯誤，請稍後再試"}), 500
    
@auth_bp.route('/api/user/shop_state', methods=['POST'])
@login_required
def update_shop_state(user):
    """切換使用者對某間咖啡廳的『收藏 / 已造訪』狀態。

    body 可帶 source（explore / chat / blindbox / passport），記進流水帳。
    回傳多了 new_badges（這次新解鎖的徽章）與 blindbox_completed。
    """
    from services import passport_service
    try:
        data = request.json or {}
        cafe_id = data.get('cafe_id')
        action_type = data.get('type')

        if not isinstance(cafe_id, int) or action_type not in ('fav', 'visited'):
            return jsonify({"success": False, "message": "參數錯誤"}), 400

        result = passport_service.toggle_shop_state(user, cafe_id, action_type, data.get('source'))
        if result is None:
            return jsonify({"success": False, "message": "找不到這間咖啡廳"}), 404
        return jsonify({"success": True, **result})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("[shop_state] 更新失敗")
        return jsonify({"success": False, "message": "系統發生錯誤，請稍後再試"}), 500


@auth_bp.route('/api/user/delete', methods=['POST'])
@login_required
def delete_user_account(user):
    """永久刪除帳號與其所有關聯資料。"""
    try:
        from services.user_service import delete_user_data
        delete_user_data(user.id)
        session.pop('user_email', None)
        return jsonify({"success": True, "message": "帳號已刪除"})
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "系統發生錯誤，請稍後再試"}), 500
