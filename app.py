import os
import logging
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from database import db
from extensions import oauth, limiter, migrate

# override=True：.env 一律蓋過已存在的環境變數。
# 啟動面板會把自己的 os.environ 傳給它啟動的後端（dev_launcher.py），
# 面板若開著沒關，舊的環境變數會一直被繼承下去；預設的 override=False
# 會讓 .env 完全不生效，改了金鑰卻怎麼重啟都沒用。
load_dotenv(override=True)

# 測試專用逃生門：pytest 用 TEST_DB_URI 強制走 in-memory SQLite。
# 必須放在 load_dotenv 之後 —— 因為 override=True 會把 .env 的 DB_URI
# 蓋回真實資料庫，測試就會打到正式資料（曾經因此整批資料表被 drop）。
if os.getenv('TEST_DB_URI'):
    os.environ['DB_URI'] = os.environ['TEST_DB_URI']

if os.getenv('FLASK_ENV') == 'development' or os.getenv('ALLOW_INSECURE_OAUTH') == '1':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)

# 配置標準日誌系統
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
app.logger.setLevel(logging.INFO)

# --- 設定密鑰與 Config ---
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    if os.getenv('FLASK_ENV') == 'development' or os.getenv('FLASK_DEBUG') == '1':
        app.logger.warning("No SECRET_KEY set. Falling back to dev_key for development.")
        secret_key = 'dev_key'
    else:
        raise RuntimeError("SECRET_KEY must be set in production")
app.secret_key = secret_key

# Cookie 安全屬性：HttpOnly 防止 XSS 竊取、SameSite 緩解 CSRF、Secure 僅在正式環境啟用（需 HTTPS）
# 注意：若正式環境前後端分屬不同網域，需改為 SAMESITE='None' 且 SESSION_COOKIE_SECURE=True
is_production = os.getenv('FLASK_ENV') == 'production'
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=is_production,
)
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
app.config['GOOGLE_MAPS_API_KEY'] = os.getenv('GOOGLE_MAPS_API_KEY')

local_db_uri = 'mysql+pymysql://root:@localhost/cafematch'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DB_URI', local_db_uri)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 啟用 CORS
cors_origins = [o.strip() for o in os.getenv('CORS_ORIGINS', os.getenv('FRONTEND_URL', 'http://localhost:5173')).split(',') if o.strip()]
CORS(app, supports_credentials=True, origins=cors_origins)

# 綁定 Extensions
db.init_app(app)
oauth.init_app(app)
limiter.init_app(app)
migrate.init_app(app, db)


@app.errorhandler(429)
def handle_rate_limit(e):
    from flask import jsonify
    return jsonify({"error": "請求過於頻繁，請稍候片刻再試", "done": True}), 429

oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# --- 匯入模型與註冊路由 ---
import models
from routes import register_blueprints

register_blueprints(app)

@app.cli.command("init-db")
def init_db():
    """初始化資料庫與管理員"""
    db.create_all()

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
        
    try:
        db.session.execute(db.text("ALTER TABLE cafes ADD COLUMN image LONGTEXT"))
        db.session.commit()
        print('[INIT] 已為 cafes 表新增 image 欄位')
    except Exception:
        db.session.rollback()
        
    try:
        db.session.execute(db.text("ALTER TABLE cafes ADD COLUMN google_place_id VARCHAR(255) DEFAULT NULL"))
        db.session.commit()
        print('[INIT] 已為 cafes 表新增 google_place_id 欄位')
    except Exception:
        db.session.rollback()
        
    try:
        db.session.execute(db.text("ALTER TABLE cafes ADD COLUMN google_photo_attribution TEXT"))
        db.session.commit()
        print('[INIT] 已為 cafes 表新增 google_photo_attribution 欄位')
    except Exception:
        db.session.rollback()
        
    try:
        db.session.execute(db.text("ALTER TABLE community_posts ADD COLUMN original_post_id INT DEFAULT NULL"))
        db.session.commit()
        print('[INIT] 已為 community_posts 表新增 original_post_id 欄位')
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(db.text("ALTER TABLE chat_sessions ADD COLUMN pref_state JSON NULL"))
        db.session.commit()
        print('[INIT] 已為 chat_sessions 表新增 pref_state 欄位')
    except Exception:
        db.session.rollback()
        
    # 初始化管理員帳號
    admin_emails = os.getenv('ADMIN_EMAILS', 'wjy28396@gmail.com').split(',')
    for admin_email in admin_emails:
        admin_email = admin_email.strip()
        if not admin_email:
            continue
        admin_user = models.User.query.filter_by(email=admin_email).first()
        if admin_user and not admin_user.is_admin:
            admin_user.is_admin = True
            db.session.commit()
            print(f'[INIT] 已將 {admin_email} 設為管理員')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
