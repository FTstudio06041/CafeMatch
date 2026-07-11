"""
pytest 全域設定。

安全防線：測試一律使用 in-memory SQLite。
flask-sqlalchemy 3.x 在 db.init_app() 當下就會建立引擎，
所以必須趕在任何測試模組 import app 之前，就用環境變數蓋掉 DB_URI；
事後改 app.config['SQLALCHEMY_DATABASE_URI'] 是無效的。
"""
import os
import sys

# 讓測試可以 import 專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 必須在 import app 之前設定（load_dotenv 不會覆蓋既有環境變數）
os.environ['DB_URI'] = 'sqlite:///:memory:'
