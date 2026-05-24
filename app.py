from flask import Flask, redirect, url_for, session, jsonify, request
from authlib.integrations.flask_client import OAuth
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv
import requests
import uuid

load_dotenv()

# 允許 http 開發環境
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)

# --- 設定密鑰 ---
app.secret_key = os.getenv('SECRET_KEY', 'dev_key')
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
local_db_uri = 'mysql+pymysql://root:@localhost/cafematch'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DB_URI', local_db_uri)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==========================================
# MySQL 連線設定 (XAMPP 預設)
# 帳號: root
# 密碼: (空)
# 主機: localhost
# 資料庫: cafematch
# ==========================================


# 啟用 CORS
CORS(app, supports_credentials=True)

# --- 定義資料表模型 ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    # 使用 Text 類型來存長長的 Base64 圖片字串
    picture = db.Column(db.Text)
    is_admin = db.Column(db.Boolean, default=False)
    last_read_announcement_id = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<User {self.email}>'

# 管理員操作 Log 資料表
class AdminLog(db.Model):
    __tablename__ = 'admin_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    action = db.Column(db.String(255), nullable=False)  # 操作類型
    detail = db.Column(db.Text)  # 操作細節
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SystemAnnouncement(db.Model):
    """系統最新消息/公告"""
    __tablename__ = 'system_announcements'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BugReport(db.Model):
    """使用者 Bug 回報與意見建議"""
    __tablename__ = 'bug_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    report_type = db.Column(db.String(50), default='bug') # 'bug' 或 'suggest'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 管理員權限檢查裝飾器
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({"error": "未登入"}), 401
        user = User.query.filter_by(email=user_email).first()
        if not user or not user.is_admin:
            return jsonify({"error": "權限不足"}), 403
        return f(*args, **kwargs)
    return decorated_function

# 記錄操作 Log 的輔助函式
def log_action(email, action, detail=''):
    try:
        log = AdminLog(user_email=email, action=action, detail=detail)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f'Log error: {e}')
        db.session.rollback()

# ==========================================
# 新增：咖啡廳相關資料表模型
# 根據您的 phpMyAdmin 截圖對應欄位
# ==========================================

# 1. 咖啡廳主表 (cafes)
class Cafes(db.Model):
    __tablename__ = 'cafes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    # 截圖中的其他欄位
    num = db.Column(db.Integer)
    url = db.Column(db.String(255))
    address = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    website = db.Column(db.String(255))
    cost = db.Column(db.String(50))
    image = db.Column(db.Text)  # 店家圖片（Base64）
    
    # 建立關聯 (方便查詢)
    # 透過 secondary 指定中間表，直接關聯到 Tags
    tags = db.relationship('Tags', secondary='cafe_tags', backref='cafes')
    hours = db.relationship('OperatingHours', backref='cafe')

# 2. 標籤表 (tags)
class Tags(db.Model):
    __tablename__ = 'tags'
    # 截圖顯示主鍵是 tag_id，名稱是 tag_name
    tag_id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String(50), nullable=False)

# 3. 中間關聯表 (cafe_tags)
cafe_tags = db.Table('cafe_tags',
    db.Column('cafe_id', db.Integer, db.ForeignKey('cafes.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.tag_id'), primary_key=True)
)

# 4. 營業時間表 (operatinghours)
class OperatingHours(db.Model):
    __tablename__ = 'operatinghours'
    id = db.Column(db.Integer, primary_key=True)
    cafe_id = db.Column(db.Integer, db.ForeignKey('cafes.id'), nullable=False)
    day_of_week = db.Column(db.Integer) # 截圖顯示是數字 (1-7)
    open_time = db.Column(db.Time)
    close_time = db.Column(db.Time)
    is_closed = db.Column(db.Integer) # 截圖顯示是 0 或 1

# 5. 使用者收藏與互動狀態 (UserShopState)
class UserShopState(db.Model):
    __tablename__ = 'user_shop_state'
    id = db.Column(db.Integer, primary_key=True)
    # 這裡我們簡單做，只存 ID，不強制綁定外鍵約束，避免您遇到之前的 errno 150 錯誤
    user_id = db.Column(db.Integer, nullable=False) 
    cafe_id = db.Column(db.Integer, nullable=False)
    is_fav = db.Column(db.Boolean, default=False)     # 是否收藏
    is_visited = db.Column(db.Boolean, default=False) # 是否去過

# ==========================================
# 心理測驗系統：資料表模型
# ==========================================

class QuizQuestion(db.Model):
    """心理測驗題目"""
    __tablename__ = 'quiz_questions'
    id = db.Column(db.Integer, primary_key=True)
    order = db.Column(db.Integer, nullable=False)
    scenario_tag = db.Column(db.String(100))
    question_text = db.Column(db.Text, nullable=False)
    is_multiple = db.Column(db.Boolean, default=False)
    options = db.relationship('QuizOption', backref='question', order_by='QuizOption.code')

class QuizOption(db.Model):
    """心理測驗選項"""
    __tablename__ = 'quiz_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('quiz_questions.id'), nullable=False)
    code = db.Column(db.String(5), nullable=False)
    text = db.Column(db.Text, nullable=False)
    subtext = db.Column(db.Text)
    score_work = db.Column(db.Integer, default=0)
    score_env = db.Column(db.Integer, default=0)
    score_social = db.Column(db.Integer, default=0)
    score_taste = db.Column(db.Integer, default=0)
    score_cp = db.Column(db.Integer, default=0)
    filter_tag = db.Column(db.String(50))

class QuizResultType(db.Model):
    """心理測驗結果類型"""
    __tablename__ = 'quiz_result_types'
    id = db.Column(db.Integer, primary_key=True)
    type_key = db.Column(db.String(50), unique=True, nullable=False)
    condition = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    inner_voice = db.Column(db.Text)
    profile = db.Column(db.Text)
    cafe_match = db.Column(db.Text)

class UserQuizResult(db.Model):
    """使用者測驗結果紀錄"""
    __tablename__ = 'user_quiz_results'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    result_type_key = db.Column(db.String(50), nullable=False)
    score_work = db.Column(db.Integer, default=0)
    score_env = db.Column(db.Integer, default=0)
    score_social = db.Column(db.Integer, default=0)
    score_taste = db.Column(db.Integer, default=0)
    score_cp = db.Column(db.Integer, default=0)
    filter_tags = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatFeedback(db.Model):
    """使用者聊天反饋紀錄"""
    __tablename__ = 'chat_feedbacks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_message = db.Column(db.Text, nullable=True)
    ai_response = db.Column(db.Text, nullable=True)
    feedback_type = db.Column(db.String(20), nullable=False) # 'like', 'dislike'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    messages = db.Column(db.JSON, nullable=False, default=list) # 儲存 {text, sender, isTyping} 陣列
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ==========================================
# 社群功能：資料表模型
# ==========================================

class CommunityPost(db.Model):
    """社群正常貼文"""
    __tablename__ = 'community_posts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    cafe_id = db.Column(db.Integer, nullable=True)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CommunityNote(db.Model):
    """社群便利貼"""
    __tablename__ = 'community_notes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.String(100), nullable=False)
    color_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CommunityLike(db.Model):
    """社群愛心（便利貼用）"""
    __tablename__ = 'community_likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note_id = db.Column(db.Integer, db.ForeignKey('community_notes.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CommunityComment(db.Model):
    """社群留言（便利貼用）"""
    __tablename__ = 'community_comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note_id = db.Column(db.Integer, db.ForeignKey('community_notes.id'), nullable=False)
    content = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==========================================
# 新增：API 接口
# ==========================================

@app.route('/api/cafes', methods=['GET'])
def get_cafes():
    try:
        all_cafes = Cafes.query.all()
        results = []
        import random

        # --- 新增：取得目前使用者的收藏狀態 ---
        user_email = session.get('user_email')
        user_states = {} # 格式: { cafe_id: {'fav': True, 'visited': False} }
        
        # 先用 email 換 user_id
        current_user = None
        if user_email:
            current_user = User.query.filter_by(email=user_email).first()
        
        if current_user:
            # 撈出這個人的所有紀錄
            states = UserShopState.query.filter_by(user_id=current_user.id).all()
            for s in states:
                user_states[s.cafe_id] = {'fav': s.is_fav, 'visited': s.is_visited}
        # -------------------------------------

        for cafe in all_cafes:
            tag_list = [f"#{t.tag_name}" for t in cafe.tags]
            tag_str = " ".join(tag_list) if tag_list else "#無標籤"

            hours_str = "營業時間請洽店家"
            if cafe.hours:
                for h in cafe.hours:
                    if h.is_closed == 0 and h.open_time and h.close_time:
                        # 簡單處理時間格式
                        try:
                            o_time = h.open_time.strftime('%H:%M')
                            c_time = h.close_time.strftime('%H:%M')
                            hours_str = f"{o_time} - {c_time}"
                        except:
                            pass
                        break
            
            # --- 新增：判斷狀態 ---
            # 如果 user_states 裡沒資料，預設就是 False
            my_state = user_states.get(cafe.id, {'fav': False, 'visited': False})

            map_link = ""
            if cafe.url:
                map_link = f"http://maps.app.goo.gl/{cafe.url}"
            
            # Earth/Coffee Tones Palette
            palette = [
                "#8D6E63", "#A1887F", "#BCAAA4", "#D7CCC8", # Browns
                "#795548", "#6D4C41", "#5D4037", "#4E342E", # Dark Browns
                "#78909C", "#607D8B", "#546E7A"             # Blue Greys
            ]
            
            results.append({
                "id": cafe.id,
                "name": cafe.name,
                "tags": tag_str,
                "rating": round(random.uniform(3.8, 5.0), 1),
                "hours": hours_str,
                "phone": cafe.phone or "無電話",
                "address": cafe.address or "地址未知",
                "desc": cafe.website or "尚無介紹",
                "color": random.choice(palette), 
                "image": cafe.image or "",
                "map_url": map_link, 
                "is_fav": my_state['fav'],          # 傳給前端亮燈
                "is_visited": my_state['visited']   # 傳給前端亮燈
            })
        
        return jsonify(results)

    except Exception as e:
        print("Database Error:", e)
        return jsonify({"error": str(e)}), 500
    

# --- 設定 OAuth ---
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# 程式啟動時，自動建立資料表
with app.app_context():
    db.create_all()
    # 手動為既有的 user 表加上 is_admin 欄位（db.create_all 不會修改已存在的表）
    try:
        db.session.execute(db.text("ALTER TABLE user ADD COLUMN is_admin TINYINT(1) DEFAULT 0"))
        db.session.commit()
        print('[INIT] 已為 user 表新增 is_admin 欄位')
    except Exception:
        db.session.rollback()
    try:
        db.session.execute(db.text("ALTER TABLE user ADD COLUMN last_read_announcement_id INT DEFAULT 0"))
        db.session.commit()
        print('[INIT] 已為 user 表新增 last_read_announcement_id 欄位')
    except Exception:
        db.session.rollback()
    # 手動為既有的 cafes 表加上 image 欄位
    try:
        db.session.execute(db.text("ALTER TABLE cafes ADD COLUMN image LONGTEXT"))
        db.session.commit()
        print('[INIT] 已為 cafes 表新增 image 欄位')
    except Exception:
        db.session.rollback()  # 欄位已存在，忽略錯誤
    # 初始化管理員帳號
    admin_email = 'wjy28396@gmail.com'
    admin_user = User.query.filter_by(email=admin_email).first()
    if admin_user and not admin_user.is_admin:
        admin_user.is_admin = True
        db.session.commit()
        print(f'[INIT] 已將 {admin_email} 設為管理員')

# --- 路由 ---

@app.route('/')
def index():
    return 'Backend (XAMPP MySQL) is running!'

@app.route('/login')
def login():
    redirect_uri = os.getenv('GOOGLE_CALLBACK_URL', url_for('authorize', _external=True))
    # 加入 prompt='select_account' 強制顯示帳號選擇畫面
    return google.authorize_redirect(redirect_uri, prompt='select_account')

@app.route('/auth/callback')
def authorize():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    google_email = user_info['email']
    google_name = user_info['name']
    google_picture = user_info['picture']

    # --- 登入邏輯：同步資料庫 ---
    user = User.query.filter_by(email=google_email).first()

    is_new_user = False

    if not user:
        # 新使用者
        new_user = User(email=google_email, name=google_name, picture=google_picture)
        db.session.add(new_user)
        db.session.commit()
        is_new_user = True # 標記為新使用者

    session['user_email'] = google_email
    
    # 記錄登入 Log
    log_action(google_email, '登入', '新用戶' if is_new_user else '既有用戶')
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173/')
    
    # 這裡多帶一個參數回到前端
    if is_new_user:
        # 移除 .html，直接導向 /chat
        return redirect(f'{frontend_url}chat?welcome=true') 
    else:
        # 移除 .html，直接導向 /chat
        return redirect(f'{frontend_url}chat')
    
@app.route('/logout')
def logout():
    user_email = session.get('user_email')
    if user_email:
        log_action(user_email, '登出')
    session.pop('user_email', None)
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173/')
    return redirect(frontend_url)

@app.route('/api/me')
def get_current_user():
    user_email = session.get('user_email')
    
    if not user_email:
        return jsonify({"is_logged_in": False}), 401

    # 去資料庫撈最新的資料
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

@app.route('/api/user/update', methods=['POST'])
def update_user_profile():
    user_email = session.get('user_email')
    
    if not user_email:
        return jsonify({"success": False, "message": "未登入"}), 401

    try:
        data = request.json 
        new_name = data.get('name')
        new_avatar = data.get('picture')

        # 找到該使用者並更新
        user = User.query.filter_by(email=user_email).first()
        
        if user:
            if new_name:
                user.name = new_name
            if new_avatar:
                user.picture = new_avatar
            
            db.session.commit() # 存入硬碟
            
            return jsonify({
                "success": True, 
                "name": user.name,
                "picture": user.picture
            })
        else:
            return jsonify({"success": False, "message": "User not found"}), 404
        
    except Exception as e:
        print("Error:", e)
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    
@app.route('/api/user/shop_state', methods=['POST'])
def update_shop_state():
    user_email = session.get('user_email')
    if not user_email: 
        return jsonify({"success": False, "message": "未登入"}), 401
    
    try:
        # 1. 取得使用者 ID
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({"success": False, "message": "使用者不存在"}), 404

        data = request.json
        cafe_id = data.get('cafe_id')
        action_type = data.get('type') # 'fav' or 'visited'
        
        # 2. 找找看有沒有舊紀錄
        state = UserShopState.query.filter_by(user_id=user.id, cafe_id=cafe_id).first()
        
        if not state:
            # 沒有就新增一筆
            state = UserShopState(user_id=user.id, cafe_id=cafe_id)
            db.session.add(state)
        
        # 3. 更新狀態
        if action_type == 'fav':
            state.is_fav = not state.is_fav
        elif action_type == 'visited':
            state.is_visited = not state.is_visited
            
        db.session.commit()
        return jsonify({"success": True, "fav": state.is_fav, "visited": state.is_visited})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/user/delete', methods=['POST'])
def delete_user_account():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"success": False, "message": "未登入"}), 401

    try:
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({"success": False, "message": "使用者不存在"}), 404

        # 1. 刪除相關資料 (UserShopState)
        UserShopState.query.filter_by(user_id=user.id).delete()
        
        # 2. 刪除使用者
        db.session.delete(user)
        db.session.commit()
        
        # 3. 清除 Session
        session.pop('user_email', None)
        
        return jsonify({"success": True, "message": "帳號已刪除"})

    except Exception as e:
        db.session.rollback()
        print("Delete Account Error:", e)
        return jsonify({"success": False, "message": str(e)}), 500

# ==========================================
# 聊天對話持久化 API
# ==========================================

@app.route('/api/chat/sessions', methods=['GET'])
def get_chat_sessions():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "請先登入"}), 401
    
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({"error": "使用者不存在"}), 404

    sessions = ChatSession.query.filter_by(user_id=user.id).order_by(ChatSession.updated_at.desc()).all()
    
    result = []
    for s in sessions:
        result.append({
            "id": s.id,
            "title": s.title,
            "updated_at": s.updated_at.strftime('%Y-%m-%d %H:%M:%S') if s.updated_at else None
        })
    return jsonify(result)

@app.route('/api/chat/sessions/<session_id>', methods=['GET'])
def get_chat_session_detail(session_id):
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "請先登入"}), 401
    
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({"error": "使用者不存在"}), 404

    chat_session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
    if not chat_session:
        return jsonify({"error": "找不到該對話"}), 404

    return jsonify({
        "id": chat_session.id,
        "title": chat_session.title,
        "messages": chat_session.messages,
        "updated_at": chat_session.updated_at.strftime('%Y-%m-%d %H:%M:%S') if chat_session.updated_at else None
    })

@app.route('/api/chat/sessions', methods=['POST'])
def save_chat_session():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "請先登入"}), 401
    
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({"error": "使用者不存在"}), 404

    data = request.json
    session_id = data.get('id')
    title = data.get('title', '新對話')
    messages = data.get('messages', [])

    try:
        chat_session = None
        if session_id:
            chat_session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
        
        if chat_session:
            chat_session.title = title
            chat_session.messages = messages
            chat_session.updated_at = datetime.utcnow()
        else:
            new_id = session_id if session_id else str(uuid.uuid4())
            chat_session = ChatSession(
                id=new_id,
                user_id=user.id,
                title=title,
                messages=messages
            )
            db.session.add(chat_session)
        
        db.session.commit()
        return jsonify({"success": True, "id": chat_session.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
def delete_chat_session(session_id):
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "請先登入"}), 401
    
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({"error": "使用者不存在"}), 404

    try:
        chat_session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
        if not chat_session:
            return jsonify({"error": "找不到該對話"}), 404
        
        db.session.delete(chat_session)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    # 1. 確保使用者有登入 (若不想強制登入可拿掉這段)
    # user_email = session.get('user_email')
    # if not user_email:
    #     return jsonify({"error": "請先登入"}), 401

    try:
        # 2. 接收前端傳來的訊息
        data = request.json
        user_message = data.get('message', '')
        history = data.get('history', [])

        if not user_message:
            return jsonify({"error": "未提供訊息"}), 400

        # ★ 防呆機制：先快速檢查 Ollama 是否在線
        try:
            health_check = requests.get("http://localhost:11434/", timeout=3)
        except Exception:
            return jsonify({"error": "Ollama 連線失敗，請確認是否已啟動 Ollama。"}), 503

        # 3. ★ 意圖分類 + 選擇性 RAG ★
        #    判斷使用者是否在問咖啡/推薦相關問題
        CAFE_KEYWORDS = [
            '咖啡', '推薦', '咖啡廳', '咖啡店', 'café', 'cafe', '喝', '甜點',
            '花蓮', '安靜', '讀書', '工作', '約會', '聚會', '早午餐', '下午茶',
            '便宜', '平價', '好喝', '好吃', '哪裡', '哪家', '附近', '營業',
            '幾點', '開門', '關門', '休息', '地址', '電話', '價格', '消費',
            '文青', '氛圍', '氣氛', '環境', '貓', '寵物', '座位', 'wifi',
            '拿鐵', '手沖', '濾掛', '豆子', '烘焙', '評價', '評論', '打卡',
            '測驗', '結果', '適合', '口感', '風味', '酸', '苦', '甜',
            '司康', '蛋糕', '鬆餅', '可頌', '冰', '熱'
        ]

        is_cafe_related = any(kw in user_message.lower() for kw in CAFE_KEYWORDS)
        cafe_context = ""

        if is_cafe_related:
            try:
                from sqlalchemy import or_
                # 從使用者訊息中提取命中的關鍵字
                matched_keywords = [kw for kw in CAFE_KEYWORDS if kw in user_message.lower()]
                
                # 用關鍵字搜尋相關的咖啡廳（透過名稱、地址、標籤）
                query = Cafes.query
                
                # 嘗試用標籤和名稱匹配
                tag_filters = []
                name_filters = []
                for kw in matched_keywords:
                    tag_filters.append(Tags.tag_name.contains(kw))
                    name_filters.append(Cafes.name.contains(kw))
                    name_filters.append(Cafes.address.contains(kw))

                # 先找標籤匹配的咖啡廳
                tagged_cafes = Cafes.query.join(Cafes.tags).filter(
                    or_(*tag_filters)
                ).distinct().limit(5).all() if tag_filters else []

                # 再找名稱/地址匹配的
                name_cafes = Cafes.query.filter(
                    or_(*name_filters)
                ).limit(3).all() if name_filters else []

                # 合併去重（最多取 5 家）
                seen_ids = set()
                relevant_cafes = []
                for cafe in tagged_cafes + name_cafes:
                    if cafe.id not in seen_ids and len(relevant_cafes) < 5:
                        seen_ids.add(cafe.id)
                        relevant_cafes.append(cafe)
                
                # 如果關鍵字匹配不到，就拿最熱門的 5 家
                if not relevant_cafes:
                    relevant_cafes = Cafes.query.order_by(Cafes.num.desc()).limit(5).all()

                # 組裝上下文
                cafe_lines = []
                DAY_NAMES = ['', '一', '二', '三', '四', '五', '六', '日']
                for cafe in relevant_cafes:
                    tags_str = ', '.join([t.tag_name for t in cafe.tags[:8]])
                    
                    # 營業時間簡要
                    hours_parts = []
                    for h in sorted(cafe.hours, key=lambda x: x.day_of_week or 0):
                        if h.is_closed:
                            hours_parts.append(f"週{DAY_NAMES[h.day_of_week]}:公休")
                        elif h.open_time and h.close_time:
                            hours_parts.append(f"週{DAY_NAMES[h.day_of_week]}:{h.open_time.strftime('%H:%M')}-{h.close_time.strftime('%H:%M')}")
                    hours_str = '、'.join(hours_parts) if hours_parts else '未提供'

                    cafe_lines.append(
                        f"- {cafe.name} | 地址：{cafe.address or '未提供'} | 消費：{cafe.cost or '未提供'} | "
                        f"標籤：{tags_str or '無'} | 營業：{hours_str}"
                    )
                
                cafe_context = "\n\n【以下是系統資料庫中的咖啡廳資料，請優先參考這些資料來回答】\n" + "\n".join(cafe_lines) + "\n"
            except Exception as e:
                print(f"RAG 查詢失敗: {e}")
                cafe_context = ""

        # 4. 組裝最終 Prompt
        ollama_url = "http://localhost:11434/api/generate"
        model_name = app.config.get('OLLAMA_MODEL', 'llama3.2:3b')

        if is_cafe_related:
            system_prompt = """你是「啡你莫屬」的資深咖啡廳顧問，正與熟客輕鬆聊天。請嚴格遵守以下對話原則：
1. 【語氣自然有溫度】：說話要像真人朋友一樣，絕對不要像機器人一樣列點，或說出「等待您的回應」。
2. 【漸進式引導與強制推薦】：每次最多只問 1 個最關鍵的問題。如果使用者已經明確回答了你的問題，或者你覺得資訊已經夠了，請「立刻」從系統資料庫中挑選 1 到 2 家最適合的店介紹給他，**絕對不允許再無止盡地提問**。
3. 【精華介紹】：介紹要像朋友分享一樣精華，不要貼出一大串資料。
4. 【絕不編造】：只能推薦系統資料庫中出現的店家。
5. 【極度簡短】：每一次的回覆請保持在 2 到 3 句話的長度，讓對話有來有往。"""
        else:
            system_prompt = """你是「啡你莫屬」系統的友善助手。
請用繁體中文簡短、自然地回答使用者的問題。說話要像朋友一樣輕鬆，如果話題適合，你可以主動用「一個」簡單的問題反問來延續話題。切記回答要非常簡潔，且不要每次都自我介紹。"""

        # 將歷史對話組合成字串
        history_text = ""
        if history:
            history_text = "\n\n【歷史對話紀錄】\n"
            for msg in history:
                role_name = "使用者" if msg.get("role") == "user" else "助手"
                history_text += f"{role_name}：{msg.get('content', '')}\n"

        prompt_text = f"{system_prompt}{cafe_context}{history_text}\n\n【最新訊息】\n使用者：{user_message}\n助手："
        
        payload = {
            "model": model_name,
            "prompt": prompt_text,
            "stream": True
        }

        # 4. 使用 Generator 轉發資料流給前端
        #    重點：先送出 debug_info，再連線 Ollama，讓前端不用等
        def generate():
            import json
            # ★ 先送出第一包 debug_info — 前端立刻就能顯示
            initial_debug = {
                "type": "debug_info",
                "model": model_name,
                "prompt": prompt_text,
                "is_cafe_related": is_cafe_related,
                "rag_context": cafe_context if cafe_context else "(未注入資料庫資料)"
            }
            yield json.dumps(initial_debug, ensure_ascii=False) + "\n"

            # ★ 然後才去連 Ollama（這裡可能會卡一段時間等模型載入）
            try:
                response = requests.post(ollama_url, json=payload, stream=True, timeout=300)
                response.raise_for_status()

                for line in response.iter_lines():
                    if line:
                        yield line.decode('utf-8') + "\n"
            except requests.exceptions.ConnectionError:
                error_msg = json.dumps({"error": "Ollama 連線失敗，請確認 Ollama 是否已啟動。", "done": True}, ensure_ascii=False)
                yield error_msg + "\n"
            except requests.exceptions.Timeout:
                error_msg = json.dumps({"error": "Ollama 回應逾時，模型可能正在載入中，請稍後再試。", "done": True}, ensure_ascii=False)
                yield error_msg + "\n"
            except Exception as e:
                error_msg = json.dumps({"error": f"Ollama 發生錯誤：{str(e)}", "done": True}, ensure_ascii=False)
                yield error_msg + "\n"

        resp = app.response_class(generate(), mimetype='application/x-ndjson')
        resp.headers['Cache-Control'] = 'no-cache'
        resp.headers['X-Accel-Buffering'] = 'no'
        return resp

    except Exception as e:
        print("Chat API Error:", e)
        return jsonify({"error": "系統發生未知的錯誤"}), 500


# ==========================================
# 管理員 API
# ==========================================

# --- 用戶管理 ---
@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'email': u.email,
        'name': u.name,
        'picture': u.picture[:80] + '...' if u.picture and len(u.picture) > 80 else u.picture,
        'is_admin': u.is_admin
    } for u in users])

@app.route('/api/admin/users/<int:user_id>/toggle_admin', methods=['POST'])
@admin_required
def admin_toggle_admin(user_id):
    target = User.query.get_or_404(user_id)
    # 防止取消自己的管理員權限
    current_email = session.get('user_email')
    if target.email == current_email:
        return jsonify({'error': '不能變更自己的管理員權限'}), 400
    target.is_admin = not target.is_admin
    db.session.commit()
    log_action(current_email, '切換管理員權限', f'將 {target.email} 設為 {"管理員" if target.is_admin else "一般用戶"}')
    return jsonify({'success': True, 'is_admin': target.is_admin})

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    target = User.query.get_or_404(user_id)
    current_email = session.get('user_email')
    if target.email == current_email:
        return jsonify({'error': '不能刪除自己'}), 400
    email = target.email
    UserShopState.query.filter_by(user_id=target.id).delete()
    db.session.delete(target)
    db.session.commit()
    log_action(current_email, '刪除用戶', f'已刪除 {email}')
    return jsonify({'success': True})

# --- 店家管理 ---
@app.route('/api/admin/cafes', methods=['GET'])
@admin_required
def admin_get_cafes():
    cafes = Cafes.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'address': c.address or '',
        'phone': c.phone or '',
        'website': c.website or '',
        'cost': c.cost or '',
        'image': c.image or '',
        'tags': ', '.join([t.tag_name for t in c.tags])
    } for c in cafes])

@app.route('/api/admin/cafes/<int:cafe_id>', methods=['PUT'])
@admin_required
def admin_update_cafe(cafe_id):
    cafe = Cafes.query.get_or_404(cafe_id)
    data = request.json
    if 'name' in data: cafe.name = data['name']
    if 'address' in data: cafe.address = data['address']
    if 'phone' in data: cafe.phone = data['phone']
    if 'website' in data: cafe.website = data['website']
    if 'cost' in data: cafe.cost = data['cost']
    if 'image' in data: cafe.image = data['image']
    db.session.commit()
    current_email = session.get('user_email')
    log_action(current_email, '更新店家', f'更新 {cafe.name} (ID: {cafe_id})')
    return jsonify({'success': True})

@app.route('/api/admin/cafes/<int:cafe_id>', methods=['DELETE'])
@admin_required
def admin_delete_cafe(cafe_id):
    cafe = Cafes.query.get_or_404(cafe_id)
    name = cafe.name
    # 刪除關聯資料
    db.session.execute(cafe_tags.delete().where(cafe_tags.c.cafe_id == cafe_id))
    OperatingHours.query.filter_by(cafe_id=cafe_id).delete()
    UserShopState.query.filter_by(cafe_id=cafe_id).delete()
    db.session.delete(cafe)
    db.session.commit()
    current_email = session.get('user_email')
    log_action(current_email, '刪除店家', f'已刪除 {name} (ID: {cafe_id})')
    return jsonify({'success': True})

# --- Log 檢視 ---
@app.route('/api/admin/logs', methods=['GET'])
@admin_required
def admin_get_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    logs = AdminLog.query.order_by(AdminLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'logs': [{
            'id': l.id,
            'user_email': l.user_email,
            'action': l.action,
            'detail': l.detail or '',
            'created_at': l.created_at.strftime('%Y-%m-%d %H:%M:%S') if l.created_at else ''
        } for l in logs.items],
        'total': logs.total,
        'pages': logs.pages,
        'current_page': logs.page
    })

# --- 模型管理 ---
@app.route('/api/admin/model', methods=['GET'])
@admin_required
def admin_get_model():
    """取得目前使用的模型和 Ollama 已安裝的模型列表"""
    # 目前使用的模型（從 chat API 中的設定讀取）
    current_model = app.config.get('OLLAMA_MODEL', 'llama3.2:3b')
    
    # 嘗試從 Ollama 取得已安裝的模型列表
    installed_models = []
    ollama_status = 'offline'
    try:
        resp = requests.get('http://localhost:11434/api/tags', timeout=5)
        if resp.ok:
            ollama_status = 'online'
            models_data = resp.json().get('models', [])
            installed_models = [{
                'name': m.get('name', ''),
                'size': m.get('size', 0),
                'modified_at': m.get('modified_at', '')
            } for m in models_data]
    except:
        ollama_status = 'offline'
    
    return jsonify({
        'current_model': current_model,
        'ollama_status': ollama_status,
        'installed_models': installed_models
    })

@app.route('/api/admin/model/switch', methods=['POST'])
@admin_required
def admin_switch_model():
    """切換 Ollama 使用的模型"""
    data = request.json
    new_model = data.get('model')
    if not new_model:
        return jsonify({'error': '請指定模型名稱'}), 400
    
    app.config['OLLAMA_MODEL'] = new_model
    current_email = session.get('user_email')
    log_action(current_email, '切換模型', f'切換至 {new_model}')
    return jsonify({'success': True, 'current_model': new_model})

@app.route('/api/admin/model/delete', methods=['POST'])
@admin_required
def admin_delete_model():
    """刪除 Ollama 模型"""
    data = request.json
    model_name = data.get('model')
    if not model_name:
        return jsonify({'error': '請指定模型名稱'}), 400
    
    # 防止刪除目前正在使用的模型
    current_model = app.config.get('OLLAMA_MODEL', 'llama3.2:3b')
    if model_name == current_model:
        return jsonify({'error': '不能刪除目前正在使用的模型'}), 400

    try:
        # 發送刪除請求給 Ollama
        # Ollama API: DELETE /api/delete {"name": "..."}
        resp = requests.delete('http://localhost:11434/api/delete', json={'name': model_name})
        if resp.ok:
            current_email = session.get('user_email')
            log_action(current_email, '刪除模型', f'刪除模型 {model_name}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': f'Ollama 刪除失敗: {resp.text}'}), 500
    except Exception as e:
        return jsonify({'error': f'連線失敗: {str(e)}'}), 500


# ==========================================
# 心理測驗系統：結果判定函式
# ==========================================

def determine_result_type(scores):
    """
    根據五維分數判定使用者所屬的測驗結果類型。
    判定邏輯：
    1. 若所有維度的最大值與最小值差距 ≤ 2 → balanced（隨遇而安型）
    2. 若 work 與 env 同時突出 → work_env（游牧創作者）
    3. 若 taste 與 cp 同時突出 → taste_cp（老饕精算師）
    4. 否則取最高分維度作為單一結果
    """
    work = scores['work']
    env = scores['env']
    social = scores['social']
    taste = scores['taste']
    cp = scores['cp']
    all_scores = [work, env, social, taste, cp]
    max_score = max(all_scores)
    avg = sum(all_scores) / 5

    # 判定：平衡型
    if max(all_scores) - min(all_scores) <= 2:
        return 'balanced'

    # 判定：work + env 雙高型
    if abs(work - env) <= 2 and work >= avg + 2 and env >= avg + 2:
        others = [social, taste, cp]
        if all(work > o + 3 for o in others) and all(env > o + 3 for o in others):
            return 'work_env'

    # 判定：taste + cp 雙高型
    if abs(taste - cp) <= 2 and taste >= avg + 2 and cp >= avg + 2:
        others = [work, env, social]
        if all(taste > o + 3 for o in others) and all(cp > o + 3 for o in others):
            return 'taste_cp'

    # 判定：單一最高維度
    dimension_keys = ['work', 'env', 'social', 'taste', 'cp']
    max_idx = all_scores.index(max_score)
    return dimension_keys[max_idx]


# ==========================================
# 心理測驗系統：API 端點
# ==========================================

@app.route('/api/quiz/questions', methods=['GET'])
def quiz_get_questions():
    """取得所有測驗題目（不需登入），不含分數欄位"""
    questions = QuizQuestion.query.order_by(QuizQuestion.order).all()
    result = []
    for q in questions:
        options_list = []
        for opt in q.options:
            options_list.append({
                'id': opt.id,
                'code': opt.code,
                'text': opt.text,
                'subtext': opt.subtext
            })
        result.append({
            'id': q.id,
            'order': q.order,
            'scenario_tag': q.scenario_tag,
            'question_text': q.question_text,
            'is_multiple': q.is_multiple,
            'options': options_list
        })
    return jsonify({'questions': result})


@app.route('/api/quiz/submit', methods=['POST'])
def quiz_submit():
    """提交測驗答案並取得結果（需登入）"""
    # 檢查登入狀態
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'error': '請先登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'error': '使用者不存在'}), 404

    try:
        data = request.json
        answer_ids = data.get('answers', [])
        filter_ids = data.get('filters', [])

        # 累加答案選項的分數
        scores = {'work': 0, 'env': 0, 'social': 0, 'taste': 0, 'cp': 0}

        if answer_ids:
            answer_options = QuizOption.query.filter(QuizOption.id.in_(answer_ids)).all()
            for opt in answer_options:
                scores['work'] += opt.score_work
                scores['env'] += opt.score_env
                scores['social'] += opt.score_social
                scores['taste'] += opt.score_taste
                scores['cp'] += opt.score_cp

        # 收集篩選標籤
        filter_tags = []
        if filter_ids:
            filter_options = QuizOption.query.filter(QuizOption.id.in_(filter_ids)).all()
            for opt in filter_options:
                if opt.filter_tag:
                    filter_tags.append(opt.filter_tag)

        # 判定結果類型
        result_type_key = determine_result_type(scores)

        # 查詢完整結果描述
        result_type = QuizResultType.query.filter_by(type_key=result_type_key).first()

        # 存入使用者測驗紀錄
        record = UserQuizResult(
            user_id=user.id,
            result_type_key=result_type_key,
            score_work=scores['work'],
            score_env=scores['env'],
            score_social=scores['social'],
            score_taste=scores['taste'],
            score_cp=scores['cp'],
            filter_tags=','.join(filter_tags) if filter_tags else ''
        )
        db.session.add(record)
        db.session.commit()

        # 組裝回傳結果
        result_data = None
        if result_type:
            result_data = {
                'type_key': result_type.type_key,
                'title': result_type.title,
                'inner_voice': result_type.inner_voice,
                'profile': result_type.profile,
                'cafe_match': result_type.cafe_match
            }

        return jsonify({
            'result': result_data,
            'scores': scores,
            'filters': filter_tags,
            'record_id': record.id
        })

    except Exception as e:
        db.session.rollback()
        print(f'測驗提交錯誤：{e}')
        return jsonify({'error': f'提交失敗：{str(e)}'}), 500


@app.route('/api/quiz/history', methods=['GET'])
def quiz_history():
    """取得當前使用者的所有測驗紀錄（需登入）"""
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'error': '請先登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'error': '使用者不存在'}), 404

    records = UserQuizResult.query.filter_by(user_id=user.id)\
        .order_by(UserQuizResult.created_at.desc()).all()

    history = []
    for r in records:
        # 查詢結果類型取得稱號
        rt = QuizResultType.query.filter_by(type_key=r.result_type_key).first()
        history.append({
            'id': r.id,
            'type_key': r.result_type_key,
            'title': rt.title if rt else '',
            'scores': {
                'work': r.score_work,
                'env': r.score_env,
                'social': r.score_social,
                'taste': r.score_taste,
                'cp': r.score_cp
            },
            'filters': r.filter_tags or '',
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else ''
        })

    return jsonify({'history': history})


@app.route('/api/quiz/latest', methods=['GET'])
def quiz_latest():
    """取得當前使用者最新一筆測驗結果（需登入）"""
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'error': '請先登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'error': '使用者不存在'}), 404

    record = UserQuizResult.query.filter_by(user_id=user.id)\
        .order_by(UserQuizResult.created_at.desc()).first()

    if not record:
        return jsonify({'result': None})

    # 查詢完整結果描述
    result_type = QuizResultType.query.filter_by(type_key=record.result_type_key).first()

    scores = {
        'work': record.score_work,
        'env': record.score_env,
        'social': record.score_social,
        'taste': record.score_taste,
        'cp': record.score_cp
    }

    filter_tags = record.filter_tags.split(',') if record.filter_tags else []

    result_data = None
    if result_type:
        result_data = {
            'type_key': result_type.type_key,
            'title': result_type.title,
            'inner_voice': result_type.inner_voice,
            'profile': result_type.profile,
            'cafe_match': result_type.cafe_match
        }

    return jsonify({
        'result': result_data,
        'scores': scores,
        'filters': filter_tags,
        'record_id': record.id
    })
@app.route('/api/chat/feedback', methods=['POST'])
def chat_feedback():
    data = request.json
    feedback_type = data.get('feedback_type')
    user_message = data.get('user_message', '')
    ai_response = data.get('ai_response', '')
    user_email = session.get('user_email')
    
    user_id = None
    if user_email:
        user = User.query.filter_by(email=user_email).first()
        if user:
            user_id = user.id

    if not feedback_type:
        return jsonify({"success": False, "error": "Missing feedback type"}), 400

    try:
        feedback = ChatFeedback(
            user_id=user_id,
            user_message=user_message,
            ai_response=ai_response,
            feedback_type=feedback_type
        )
        db.session.add(feedback)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# 社群功能：API 路由
# ==========================================

# --- 便利貼 API ---

@app.route('/api/community/notes', methods=['GET'])
def community_get_notes():
    """取得所有便利貼（不需登入即可查看）"""
    try:
        from datetime import timedelta
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        notes = CommunityNote.query.filter(CommunityNote.created_at >= twenty_four_hours_ago).order_by(CommunityNote.created_at.desc()).all()

        # 檢查當前使用者是否已登入（用於判斷 is_liked）
        current_user = None
        user_email = session.get('user_email')
        if user_email:
            current_user = User.query.filter_by(email=user_email).first()

        result = []
        for note in notes:
            # 查詢作者資訊
            author = User.query.get(note.user_id)
            # 計算愛心數與留言數
            like_count = CommunityLike.query.filter_by(note_id=note.id).count()
            comment_count = CommunityComment.query.filter_by(note_id=note.id).count()

            note_data = {
                'id': note.id,
                'content': note.content,
                'color_index': note.color_index,
                'created_at': note.created_at.strftime('%Y-%m-%d %H:%M') if note.created_at else '',
                'user_name': author.name if author else '匿名',
                'user_picture': author.picture if author else '',
                'user_email': author.email if author else '',
                'like_count': like_count,
                'comment_count': comment_count
            }

            # 已登入使用者額外回傳 is_liked
            if current_user:
                existing_like = CommunityLike.query.filter_by(
                    user_id=current_user.id, note_id=note.id
                ).first()
                note_data['is_liked'] = existing_like is not None
            else:
                note_data['is_liked'] = False

            result.append(note_data)

        return jsonify({'success': True, 'notes': result})

    except Exception as e:
        print(f'取得便利貼錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/community/notes', methods=['POST'])
def community_create_note():
    """新增便利貼（需登入）"""
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        data = request.json
        content = data.get('content', '').strip()
        color_index = data.get('color_index', 0)

        if not content:
            return jsonify({'success': False, 'message': '內容不可為空'}), 400
        if len(content) > 100:
            return jsonify({'success': False, 'message': '內容不可超過 100 字'}), 400

        # 檢查該使用者是否已有便利貼
        existing_note = CommunityNote.query.filter_by(user_id=user.id).first()
        if existing_note:
            existing_note.content = content
            existing_note.color_index = color_index
            existing_note.created_at = datetime.utcnow()
            note = existing_note
        else:
            note = CommunityNote(
                user_id=user.id,
                content=content,
                color_index=color_index
            )
            db.session.add(note)
        
        db.session.commit()

        return jsonify({
            'success': True,
            'note': {
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
        })

    except Exception as e:
        db.session.rollback()
        print(f'新增便利貼錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/community/notes/<int:note_id>', methods=['DELETE'])
def community_delete_note(note_id):
    """刪除便利貼（需登入，僅限本人）"""
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        note = CommunityNote.query.get(note_id)
        if not note:
            return jsonify({'success': False, 'message': '便利貼不存在'}), 404
        if note.user_id != user.id:
            return jsonify({'success': False, 'message': '只能刪除自己的便利貼'}), 403

        # 同時刪除相關的愛心與留言
        CommunityLike.query.filter_by(note_id=note_id).delete()
        CommunityComment.query.filter_by(note_id=note_id).delete()
        db.session.delete(note)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        print(f'刪除便利貼錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


# --- 愛心 API ---

@app.route('/api/community/notes/<int:note_id>/like', methods=['POST'])
def community_toggle_like(note_id):
    """按愛心 / 取消愛心（需登入，Toggle 機制）"""
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        note = CommunityNote.query.get(note_id)
        if not note:
            return jsonify({'success': False, 'message': '便利貼不存在'}), 404

        existing_like = CommunityLike.query.filter_by(
            user_id=user.id, note_id=note_id
        ).first()

        if existing_like:
            # 已按過 → 取消愛心
            db.session.delete(existing_like)
            is_liked = False
        else:
            # 未按過 → 新增愛心
            new_like = CommunityLike(user_id=user.id, note_id=note_id)
            db.session.add(new_like)
            is_liked = True

        db.session.commit()
        like_count = CommunityLike.query.filter_by(note_id=note_id).count()

        return jsonify({
            'success': True,
            'is_liked': is_liked,
            'like_count': like_count
        })

    except Exception as e:
        db.session.rollback()
        print(f'愛心操作錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


# --- 留言 API ---

@app.route('/api/community/notes/<int:note_id>/comments', methods=['GET'])
def community_get_comments(note_id):
    """取得便利貼的留言（不需登入即可查看）"""
    try:
        note = CommunityNote.query.get(note_id)
        if not note:
            return jsonify({'success': False, 'message': '便利貼不存在'}), 404

        comments = CommunityComment.query.filter_by(note_id=note_id)\
            .order_by(CommunityComment.created_at.asc()).all()

        result = []
        for c in comments:
            author = User.query.get(c.user_id)
            result.append({
                'id': c.id,
                'content': c.content,
                'user_name': author.name if author else '匿名',
                'user_picture': author.picture if author else '',
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M') if c.created_at else ''
            })

        return jsonify({'success': True, 'comments': result})

    except Exception as e:
        print(f'取得留言錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/community/notes/<int:note_id>/comments', methods=['POST'])
def community_create_comment(note_id):
    """新增便利貼留言（需登入）"""
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        note = CommunityNote.query.get(note_id)
        if not note:
            return jsonify({'success': False, 'message': '便利貼不存在'}), 404

        data = request.json
        content = data.get('content', '').strip()

        if not content:
            return jsonify({'success': False, 'message': '留言內容不可為空'}), 400
        if len(content) > 200:
            return jsonify({'success': False, 'message': '留言不可超過 200 字'}), 400

        comment = CommunityComment(
            user_id=user.id,
            note_id=note_id,
            content=content
        )
        db.session.add(comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'user_name': user.name,
                'user_picture': user.picture or '',
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M') if comment.created_at else ''
            }
        })

    except Exception as e:
        db.session.rollback()
        print(f'新增留言錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


# --- 貼文 API ---

@app.route('/api/community/posts', methods=['GET'])
def community_get_posts():
    """取得貼文列表（不需登入即可查看，支援分頁）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        pagination = CommunityPost.query.order_by(CommunityPost.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)

        result = []
        for post in pagination.items:
            author = User.query.get(post.user_id)

            # 若有關聯店家，從 Cafes 表查名稱
            cafe_name = None
            if post.cafe_id:
                cafe = Cafes.query.get(post.cafe_id)
                cafe_name = cafe.name if cafe else None

            result.append({
                'id': post.id,
                'content': post.content,
                'image': post.image or '',
                'cafe_id': post.cafe_id,
                'cafe_name': cafe_name or '',
                'user_name': author.name if author else '匿名',
                'user_picture': author.picture if author else '',
                'user_email': author.email if author else '',
                'created_at': post.created_at.strftime('%Y-%m-%d %H:%M') if post.created_at else ''
            })

        return jsonify({
            'success': True,
            'posts': result,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': pagination.page
        })

    except Exception as e:
        print(f'取得貼文錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/community/posts', methods=['POST'])
def community_create_post():
    """新增貼文（需登入）"""
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        data = request.json
        content = data.get('content', '').strip()
        image = data.get('image')  # Base64 圖片，選填
        cafe_id = data.get('cafe_id')  # 關聯店家，選填

        if not content:
            return jsonify({'success': False, 'message': '貼文內容不可為空'}), 400

        post = CommunityPost(
            user_id=user.id,
            content=content,
            image=image,
            cafe_id=cafe_id
        )
        db.session.add(post)
        db.session.commit()

        # 查詢關聯店家名稱
        cafe_name = ''
        if cafe_id:
            cafe = Cafes.query.get(cafe_id)
            cafe_name = cafe.name if cafe else ''

        return jsonify({
            'success': True,
            'post': {
                'id': post.id,
                'content': post.content,
                'image': post.image or '',
                'cafe_id': post.cafe_id,
                'cafe_name': cafe_name,
                'user_name': user.name,
                'user_picture': user.picture or '',
                'created_at': post.created_at.strftime('%Y-%m-%d %H:%M') if post.created_at else ''
            }
        })

    except Exception as e:
        db.session.rollback()
        print(f'新增貼文錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/community/posts/<int:post_id>', methods=['DELETE'])
def community_delete_post(post_id):
    """刪除貼文（需登入，僅限本人）"""
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        post = CommunityPost.query.get(post_id)
        if not post:
            return jsonify({'success': False, 'message': '貼文不存在'}), 404
        if post.user_id != user.id:
            return jsonify({'success': False, 'message': '只能刪除自己的貼文'}), 403

        db.session.delete(post)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        print(f'刪除貼文錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/feedbacks', methods=['GET'])
def get_feedbacks():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "請先登入"}), 401
    user = User.query.filter_by(email=user_email).first()
    if not user or not user.is_admin:
        return jsonify({"error": "權限不足"}), 403

    try:
        feedbacks = ChatFeedback.query.order_by(ChatFeedback.created_at.desc()).all()
        result = []
        for f in feedbacks:
            user_info = "訪客"
            if f.user_id:
                u = User.query.get(f.user_id)
                user_info = u.username if u else "未知使用者"
            result.append({
                "id": f.id,
                "user": user_info,
                "user_message": f.user_message,
                "ai_response": f.ai_response,
                "feedback_type": f.feedback_type,
                "created_at": f.created_at.strftime('%Y-%m-%d %H:%M')
            })
        return jsonify({"success": True, "feedbacks": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# 系統公告 / 最新消息 API
# ==========================================

@app.route('/api/announcements/latest', methods=['GET'])
def get_latest_announcement():
    """取得最新的公告，並根據使用者登入狀態與閱讀記錄判斷是否需要跳出彈窗"""
    try:
        # 取得最新的一則公告
        latest_ann = SystemAnnouncement.query.order_by(SystemAnnouncement.id.desc()).first()
        if not latest_ann:
            return jsonify({'success': True, 'show_popup': False, 'announcement': None})

        # 檢查登入狀態
        user_email = session.get('user_email')
        if not user_email:
            # 未登入不跳出彈窗
            return jsonify({'success': True, 'show_popup': False, 'announcement': None})

        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({'success': True, 'show_popup': False, 'announcement': None})

        # 比對最新公告 id 與使用者的最後閱讀紀錄
        show_popup = latest_ann.id > user.last_read_announcement_id

        return jsonify({
            'success': True,
            'show_popup': show_popup,
            'announcement': {
                'id': latest_ann.id,
                'content': latest_ann.content,
                'created_at': latest_ann.created_at.strftime('%Y-%m-%d %H:%M') if latest_ann.created_at else ''
            }
        })
    except Exception as e:
        print(f'取得最新公告錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/announcements/read', methods=['POST'])
def mark_announcement_as_read():
    """標記最新公告為已讀"""
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        # 取得最新公告 ID
        latest_ann = SystemAnnouncement.query.order_by(SystemAnnouncement.id.desc()).first()
        if latest_ann:
            user.last_read_announcement_id = latest_ann.id
            db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f'更新公告已讀記錄錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


# --- 管理員公告 CRUD ---

@app.route('/api/admin/announcements', methods=['GET'])
@admin_required
def admin_get_announcements():
    """管理員取得所有公告列表"""
    try:
        anns = SystemAnnouncement.query.order_by(SystemAnnouncement.id.desc()).all()
        result = []
        for a in anns:
            result.append({
                'id': a.id,
                'content': a.content,
                'created_at': a.created_at.strftime('%Y-%m-%d %H:%M') if a.created_at else ''
            })
        return jsonify({'success': True, 'announcements': result})
    except Exception as e:
        print(f'管理員載入公告錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/announcements', methods=['POST'])
@admin_required
def admin_create_announcement():
    """管理員發布新公告"""
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'success': False, 'message': '公告內容不能為空'}), 400

    try:
        new_ann = SystemAnnouncement(content=content)
        db.session.add(new_ann)
        db.session.commit()

        # 記錄管理員 Log
        user_email = session.get('user_email')
        log_action(user_email, '發布系統公告', f'發布了新公告：{content[:30]}...')

        return jsonify({'success': True, 'id': new_ann.id})
    except Exception as e:
        db.session.rollback()
        print(f'發布公告錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/announcements/<int:ann_id>', methods=['DELETE'])
@admin_required
def admin_delete_announcement(ann_id):
    """管理員刪除公告"""
    try:
        ann = SystemAnnouncement.query.get(ann_id)
        if not ann:
            return jsonify({'success': False, 'message': '公告不存在'}), 404

        db.session.delete(ann)
        db.session.commit()

        # 記錄管理員 Log
        user_email = session.get('user_email')
        log_action(user_email, '刪除系統公告', f'刪除了公告 ID：{ann_id}')

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f'刪除公告錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500

# ==========================================
# Bug 回報與意見建議 API
# ==========================================

@app.route('/api/bug_reports', methods=['POST'])
def create_bug_report():
    """使用者提交 Bug 回報或意見建議（免登入，若登入則自動綁定使用者）"""
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    report_type = data.get('report_type', 'bug').strip()

    if not content:
        return jsonify({'success': False, 'message': '回報內容不能為空'}), 400
    if report_type not in ['bug', 'suggest']:
        return jsonify({'success': False, 'message': '無效的回報類型'}), 400

    try:
        user_email = session.get('user_email')
        user_id = None
        if user_email:
            user = User.query.filter_by(email=user_email).first()
            if user:
                user_id = user.id

        new_report = BugReport(
            user_id=user_id,
            report_type=report_type,
            content=content
        )
        db.session.add(new_report)
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f'提交 Bug 回報錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/bug_reports', methods=['GET'])
@admin_required
def admin_get_bug_reports():
    """管理員取得所有 Bug 回報列表"""
    try:
        reports = BugReport.query.order_by(BugReport.id.desc()).all()
        result = []
        for r in reports:
            author = User.query.get(r.user_id) if r.user_id else None
            result.append({
                'id': r.id,
                'report_type': r.report_type,
                'content': r.content,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
                'user_name': author.name if author else '訪客/未登入',
                'user_email': author.email if author else ''
            })
        return jsonify({'success': True, 'reports': result})
    except Exception as e:
        print(f'管理員載入 Bug 回報錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/admin/bug_reports/<int:report_id>', methods=['DELETE'])
@admin_required
def admin_delete_bug_report(report_id):
    """管理員刪除 Bug 回報"""
    try:
        report = BugReport.query.get(report_id)
        if not report:
            return jsonify({'success': False, 'message': '回報不存在'}), 404

        db.session.delete(report)
        db.session.commit()

        # 記錄管理員 Log
        user_email = session.get('user_email')
        log_action(user_email, '刪除 Bug 回報', f'刪除了回報 ID：{report_id}')

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f'刪除 Bug 回報錯誤：{e}')
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)