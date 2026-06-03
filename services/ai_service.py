"""
ai_service.py — CafeMatch AI 服務模組

將原本散落在 app.py /api/chat 路由中的所有 AI 邏輯，
拆分為三個清楚的職責區塊：
  1. 意圖分類 (Intent Classification)
  2. RAG 檢索 (Retrieval-Augmented Generation)
  3. LLM 呼叫與串流 (Ollama Streaming + Token 攔截)

以及 Ollama 基礎設施操作（健康檢查、模型列表、模型刪除）。
"""

import json
import requests
import os
from datetime import datetime


# ==========================================
# 常數定義
# ==========================================

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:3b"

# 用於判斷使用者訊息是否與咖啡推薦相關的關鍵字
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

# System Prompt 模板
CAFE_SYSTEM_PROMPT = """你是「啡你莫屬」的資深咖啡廳顧問，正與熟客輕鬆聊天。請嚴格遵守以下對話原則：
1. 【語氣自然有溫度】：說話要像真人朋友一樣，絕對不要像機器人一樣列點，或說出「等待您的回應」。
2. 【漸進式引導與強制推薦】：每次最多只問 1 個最關鍵的問題。如果使用者已經明確回答了你的問題，或者你覺得資訊已經夠了，請「立刻」從系統資料庫中挑選 1 到 2 家最適合的店介紹給他，**絕對不允許再無止盡地提問**。
3. 【精華介紹】：介紹要像朋友分享一樣精華，不要貼出一大串資料。
4. 【絕不編造】：只能推薦系統資料庫中出現的店家。
5. 【極度簡短】：每一次的回覆請保持在 2 到 3 句話的長度，讓對話有來有往。"""

GENERAL_SYSTEM_PROMPT = """你是「啡你莫屬」系統的友善助手。
請用繁體中文簡短、自然地回答使用者的問題。說話要像朋友一樣輕鬆，如果話題適合，你可以主動用「一個」簡單的問題反問來延續話題。切記回答要非常簡潔，且不要每次都自我介紹。"""

DAY_NAMES = ['', '一', '二', '三', '四', '五', '六', '日']


# ==========================================
# 1. 意圖分類 (Intent Classification)
# ==========================================

def classify_intent(user_message):
    """
    判斷使用者訊息是否與咖啡推薦相關。

    回傳:
        (is_cafe_related: bool, matched_keywords: list[str])
    """
    lower_msg = user_message.lower()
    matched = [kw for kw in CAFE_KEYWORDS if kw in lower_msg]
    return len(matched) > 0, matched


# ==========================================
# 2. RAG 檢索 (Retrieval-Augmented Generation)
# ==========================================

def retrieve_cafe_context(matched_keywords, Cafes, Tags):
    """
    根據命中的關鍵字從資料庫檢索相關咖啡廳資料，
    並組裝成可注入 Prompt 的上下文文字。

    參數:
        matched_keywords: 使用者訊息中命中的關鍵字列表
        Cafes: SQLAlchemy Cafes 模型類別
        Tags: SQLAlchemy Tags 模型類別

    回傳:
        cafe_context: str — 格式化後的咖啡廳資料上下文
    """
    try:
        from sqlalchemy import or_

        # 建立篩選條件
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
        for cafe in relevant_cafes:
            tags_str = ', '.join([t.tag_name for t in cafe.tags[:8]])

            # 營業時間簡要
            hours_parts = []
            for h in sorted(cafe.hours, key=lambda x: x.day_of_week or 0):
                if h.is_closed:
                    hours_parts.append(f"週{DAY_NAMES[h.day_of_week]}:公休")
                elif h.open_time and h.close_time:
                    hours_parts.append(
                        f"週{DAY_NAMES[h.day_of_week]}:"
                        f"{h.open_time.strftime('%H:%M')}-{h.close_time.strftime('%H:%M')}"
                    )
            hours_str = '、'.join(hours_parts) if hours_parts else '未提供'

            cafe_lines.append(
                f"- {cafe.name} | 地址：{cafe.address or '未提供'} | 消費：{cafe.cost or '未提供'} | "
                f"標籤：{tags_str or '無'} | 營業：{hours_str}"
            )

        if cafe_lines:
            return "\n\n【以下是系統資料庫中的咖啡廳資料，請優先參考這些資料來回答】\n" + "\n".join(cafe_lines) + "\n"
        return ""

    except Exception as e:
        print(f"RAG 查詢失敗: {e}")
        return ""


# ==========================================
# 3. Prompt 組裝
# ==========================================

def build_prompt(user_message, history, is_cafe_related, cafe_context, guide_instruction=None):
    """
    將 system prompt、RAG 上下文、歷史對話、使用者訊息組裝成完整的 Prompt。

    回傳:
        prompt_text: str
    """
    system_prompt = CAFE_SYSTEM_PROMPT if is_cafe_related else GENERAL_SYSTEM_PROMPT

    # 注入對話引導指令（由 conversation_guide 模組提供）
    if guide_instruction:
        system_prompt += f"\n\n【本輪任務】\n{guide_instruction}"

    # 組裝歷史對話
    history_text = ""
    if history:
        history_text = "\n\n【歷史對話紀錄】\n"
        for msg in history:
            role_name = "使用者" if msg.get("role") == "user" else "助手"
            history_text += f"{role_name}：{msg.get('content', '')}\n"

    return f"{system_prompt}{cafe_context}{history_text}\n\n【最新訊息】\n使用者：{user_message}\n助手："


# ==========================================
# 4. LLM 呼叫與串流 (含 Token 攔截)
# ==========================================

def stream_generate(model_name, prompt_text, is_cafe_related, cafe_context, db, AiQueryLog, user_id=None):
    """
    呼叫 Ollama API 進行串流生成，並在串流結束時攔截 Token 統計資料，
    寫入 AiQueryLog 資料表。

    這是一個 Python Generator 函式，直接 yield 給 Flask response_class 使用。

    參數:
        model_name: str — 使用的模型名稱
        prompt_text: str — 完整的 Prompt
        is_cafe_related: bool — 是否為咖啡相關查詢
        cafe_context: str — RAG 上下文
        db: SQLAlchemy db 實例
        AiQueryLog: SQLAlchemy 模型類別
        user_id: int|None — 使用者 ID（若有登入）
    """
    ollama_url = f"{OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": model_name,
        "prompt": prompt_text,
        "stream": True
    }

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
                decoded = line.decode('utf-8')
                yield decoded + "\n"

                # ★ 攔截最後一包：當 done=true 時，Ollama 會回傳 Token 統計
                try:
                    chunk = json.loads(decoded)
                    if chunk.get('done', False):
                        _save_query_log(
                            db=db,
                            AiQueryLog=AiQueryLog,
                            user_id=user_id,
                            model_name=model_name,
                            prompt_tokens=chunk.get('prompt_eval_count', 0),
                            completion_tokens=chunk.get('eval_count', 0),
                            total_duration_ns=chunk.get('total_duration', 0),
                        )
                except (json.JSONDecodeError, Exception):
                    pass  # 非 JSON 或寫入失敗不影響串流

    except requests.exceptions.ConnectionError:
        error_msg = json.dumps(
            {"error": "Ollama 連線失敗，請確認 Ollama 是否已啟動。", "done": True},
            ensure_ascii=False
        )
        yield error_msg + "\n"
    except requests.exceptions.Timeout:
        error_msg = json.dumps(
            {"error": "Ollama 回應逾時，模型可能正在載入中，請稍後再試。", "done": True},
            ensure_ascii=False
        )
        yield error_msg + "\n"
    except Exception as e:
        error_msg = json.dumps(
            {"error": f"Ollama 發生錯誤：{str(e)}", "done": True},
            ensure_ascii=False
        )
        yield error_msg + "\n"


def _save_query_log(db, AiQueryLog, user_id, model_name, prompt_tokens, completion_tokens, total_duration_ns):
    """
    將 Ollama 回傳的 Token 統計與延遲數據寫入 AiQueryLog 資料表。
    total_duration_ns 是 Ollama 回傳的奈秒(nanoseconds)單位。
    """
    try:
        total_ms = int(total_duration_ns / 1_000_000) if total_duration_ns else 0
        log_entry = AiQueryLog(
            user_id=user_id,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_time_ms=total_ms,
            created_at=datetime.utcnow()
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"[AiQueryLog] 寫入失敗: {e}")
        db.session.rollback()


# ==========================================
# 5. Ollama 基礎設施操作
# ==========================================

def check_health():
    """
    檢查 Ollama 服務是否在線。

    回傳:
        bool — True 表示在線
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/", timeout=3)
        return resp.ok
    except Exception:
        return False


def get_default_model():
    """
    動態取得預設模型。
    先嘗試從環境變數讀取 OLLAMA_MODEL，若無，則向 Ollama 請求已安裝的模型清單，
    並回傳第一個模型的名稱。若 Ollama 無回應或無模型，則回傳空字串。
    """
    env_model = os.getenv('OLLAMA_MODEL')
    if env_model:
        return env_model
        
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
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.ok:
            models_data = resp.json().get('models', [])
            models = [{
                'name': m.get('name', ''),
                'size': m.get('size', 0),
                'modified_at': m.get('modified_at', '')
            } for m in models_data]
            return 'online', models
        return 'offline', []
    except Exception:
        return 'offline', []


def delete_model(model_name):
    """
    刪除指定的 Ollama 模型。

    回傳:
        (success: bool, error_message: str|None)
    """
    try:
        resp = requests.delete(
            f"{OLLAMA_BASE_URL}/api/delete",
            json={'name': model_name}
        )
        if resp.ok:
            return True, None
        return False, f"Ollama 刪除失敗: {resp.text}"
    except Exception as e:
        return False, f"連線失敗: {str(e)}"
