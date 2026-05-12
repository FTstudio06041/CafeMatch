from flask import Flask, redirect, url_for, session, jsonify, request
from authlib.integrations.flask_client import OAuth
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
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

    def __repr__(self):
        return f'<User {self.email}>'
    
# ... (原本的 User class 保持不動) ...

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
    
    # 這裡多帶一個參數回到前端
    if is_new_user:
        # 移除 .html，直接導向 /chat
        return redirect('http://localhost:5173/chat?welcome=true') 
    else:
        # 移除 .html，直接導向 /chat
        return redirect('http://localhost:5173/chat')
    
@app.route('/logout')
def logout():
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
            "picture": user.picture
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

        # 3. 準備發送給 Ollama 的資料
        ollama_url = "http://localhost:11434/api/generate"
        payload = {
            "model": "qwen3.5:397b-cloud",
            "prompt": f"你是一個專業的台灣咖啡廳推薦助手。請用繁體中文自然地回答使用者的問題，像朋友一樣聊天即可。不要每次都自我介紹。\n\n使用者：{user_message}\n助手：",
            "stream": False # 讓 AI 一次把整段話講完再傳回前端
        }

        # 4. 發送請求給本機的 Ollama
        response = requests.post(ollama_url, json=payload)
        response.raise_for_status() # 檢查 HTTP 狀態碼
        
        # 5. 取出 AI 的回答並回傳給前端
        ai_reply = response.json().get("response", "抱歉，我現在腦筋有點打結，請再說一次。")
        return jsonify({"reply": ai_reply})

    except requests.exceptions.ConnectionError:
        print("Ollama 連線失敗，請檢查 Ollama 主程式是否開啟")
        return jsonify({"error": "AI 伺服器未啟動，請聯絡管理員。"}), 500
    except Exception as e:
        print("Chat API Error:", e)
        return jsonify({"error": "系統發生未知的錯誤"}), 500



if __name__ == '__main__':
    app.run(debug=True, port=5000)