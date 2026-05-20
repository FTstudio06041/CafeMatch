from flask import Flask, redirect, url_for, session, jsonify, request
from authlib.integrations.flask_client import OAuth
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv
import requests

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
    redirect_uri = url_for('authorize', _external=True)
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
    
    # 這裡多帶一個參數回到前端
    if is_new_user:
        # 移除 .html，直接導向 /chat
        return redirect('http://localhost:5173/chat?welcome=true') 
    else:
        # 移除 .html，直接導向 /chat
        return redirect('http://localhost:5173/chat')
    
@app.route('/logout')
def logout():
    user_email = session.get('user_email')
    if user_email:
        log_action(user_email, '登出')
    session.pop('user_email', None)
    return redirect('http://localhost:5173')

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
            system_prompt = "你是「啡你莫屬」系統的專業台灣咖啡廳推薦助手。請用繁體中文自然地回答使用者的問題，像朋友一樣聊天。如果系統提供了咖啡廳資料，請優先根據這些真實資料來推薦，不要自己編造店名。"
        else:
            system_prompt = "你是「啡你莫屬」系統的友善助手。請用繁體中文自然地回答使用者的問題，像朋友一樣聊天即可。不要每次都自我介紹。"

        prompt_text = f"{system_prompt}{cafe_context}\n\n使用者：{user_message}\n助手："
        
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)