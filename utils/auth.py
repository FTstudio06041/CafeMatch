from functools import wraps
from flask import session, g
from models import User
from utils.response import error_response

def get_current_user():
    user_email = session.get('user_email')
    if user_email:
        return User.query.filter_by(email=user_email).first()
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_email = session.get('user_email')
        if not user_email:
            return error_response("未登入", 401)
        user = User.query.filter_by(email=user_email).first()
        if not user or not user.is_admin:
            return error_response("權限不足", 403)
        g.user = user
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_email = session.get('user_email')
        if not user_email:
            return error_response("請先登入", 401)
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return error_response("使用者不存在", 404)
        g.user = user
        # Note: We pass 'user' explicitly because many legacy route functions expect it
        # Ideally they should just use g.user, but we pass it for backward compatibility for now.
        return f(user, *args, **kwargs)
    return decorated_function
