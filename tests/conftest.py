"""
pytest 全域設定。

安全防線：測試一律使用 in-memory SQLite。

app.py 用 load_dotenv(override=True)（讓 .env 一定蓋過繼承來的舊環境變數），
所以這裡不能直接設 DB_URI —— 會被 .env 蓋回真實資料庫。
改用 TEST_DB_URI，app.py 會在 load_dotenv 之後才套用它。

而且必須趕在任何測試模組 import app 之前設定：
flask-sqlalchemy 在 db.init_app() 當下就建立引擎，事後改 config 沒有用。
"""
import os
import sys

# 讓測試可以 import 專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 必須在 import app 之前設定
os.environ['TEST_DB_URI'] = 'sqlite:///:memory:'
