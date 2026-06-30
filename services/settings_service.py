"""
系統設定（key/value）服務。

把需要「跨 worker / 跨重啟」持久化的執行期設定存到資料庫，
取代原本存在 current_app.config（單一程序記憶體）的做法。
目前用於：Ollama 目前選用的模型。
"""
from database import db
from models import SystemSetting

OLLAMA_MODEL_KEY = 'ollama_model'


def get_setting(key, default=None):
    row = db.session.get(SystemSetting, key)
    return row.setting_value if row else default


def set_setting(key, value):
    row = db.session.get(SystemSetting, key)
    if row:
        row.setting_value = value
    else:
        db.session.add(SystemSetting(setting_key=key, setting_value=value))
    db.session.commit()


def get_selected_model():
    """回傳管理員選用的 Ollama 模型名稱；未設定則回傳 None。"""
    return get_setting(OLLAMA_MODEL_KEY)


def set_selected_model(name):
    set_setting(OLLAMA_MODEL_KEY, name)
