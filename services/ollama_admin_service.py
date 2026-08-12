from services.ollama_client import OllamaClient
from config.settings import OLLAMA_DEFAULT_MODEL

def check_health():
    """
    檢查 Ollama 服務是否在線。
    """
    client = OllamaClient()
    return client.check_health()

# 只會做 embedding、不能拿來對話的模型。挑預設模型時要跳過——
# 這些出現在 ollama list 裡，但餵給 /api/generate 只會得到無法使用的結果。
# （bge-m3 是離題檢索用的，見 services/off_topic_rag.py）
_EMBEDDING_ONLY_PREFIXES = ('bge-', 'nomic-embed', 'mxbai-embed', 'all-minilm',
                            'snowflake-arctic-embed', 'paraphrase-')


def is_chat_capable(model_name: str) -> bool:
    name = (model_name or '').lower()
    return bool(name) and not name.startswith(_EMBEDDING_ONLY_PREFIXES)


def get_default_model():
    """
    動態取得預設模型（只在管理員沒有指定時才會用到）。
    先嘗試從環境變數讀取 OLLAMA_MODEL，若無，則向 Ollama 請求已安裝的模型清單，
    取「能對話且體積最小」的那個。若 Ollama 無回應或無模型，則回傳空字串。

    取最小的而不是清單第一個：沒有指定時我們對硬體一無所知，
    最小的模型最有機會真的載得起來。挑到載不動的模型，
    使用者只會看到對話連不上，而看不出原因。
    """
    if OLLAMA_DEFAULT_MODEL != "llama3.2:3b":
        return OLLAMA_DEFAULT_MODEL

    status, models = list_models()
    if status == 'online' and models:
        usable = [m for m in models if is_chat_capable(m.get('name'))]
        if usable:
            usable.sort(key=lambda m: m.get('size') or 0)
            return usable[0]['name']

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
