from services.ollama_client import OllamaClient
from config.settings import OLLAMA_DEFAULT_MODEL

def check_health():
    """
    檢查 Ollama 服務是否在線。
    """
    client = OllamaClient()
    return client.check_health()

def get_default_model():
    """
    動態取得預設模型。
    先嘗試從環境變數讀取 OLLAMA_MODEL，若無，則向 Ollama 請求已安裝的模型清單，
    並回傳第一個模型的名稱。若 Ollama 無回應或無模型，則回傳空字串。
    """
    if OLLAMA_DEFAULT_MODEL != "llama3.2:3b":
        return OLLAMA_DEFAULT_MODEL
        
    status, models = list_models()
    if status == 'online' and models:
        return models[0]['name']
        
    return ""

def list_models():
    """
    取得 Ollama 已安裝的模型清單。

    回傳:
        (status: str, models: list[dict])
        status 為 'online' 或 'offline'
    """
    client = OllamaClient()
    try:
        models = client.list_models(timeout=5)
        return 'online', models
    except Exception:
        return 'offline', []

def delete_model(model_name):
    """
    刪除指定的 Ollama 模型。

    回傳:
        (success: bool, error_message: str|None)
    """
    client = OllamaClient()
    if client.delete_model(model_name, timeout=10):
        return True, None
    else:
        return False, f"Ollama 刪除失敗: 請查看日誌"
