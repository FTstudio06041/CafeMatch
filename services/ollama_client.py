import requests
import logging
import os
import json
import re
from config.settings import OLLAMA_BASE_URL
from config.ai_constants import OLLAMA_CLIENT_TIMEOUT, OLLAMA_HEALTH_TIMEOUT

# 預設關閉推理模式。想讓某次呼叫恢復思考就傳 think=True，
# 傳 think=None 則完全不帶這個欄位（交給模型自己的預設）。
DISABLE_THINKING = False


class OllamaClient:
    def __init__(self, base_url=None):
        self.base_url = base_url or OLLAMA_BASE_URL

    def generate(self, model, prompt, stream=False, timeout=None, format=None,
                 options=None, think=DISABLE_THINKING):
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream
        }
        if format:
            payload["format"] = format
        if options:
            payload["options"] = options
        if think is not None:
            # 推理模型（Qwen3.5 這類）預設會先產生數千 token 的隱藏思考才回答。
            # 實測 qwen3.5:9b 為了回一句 32 字的問句，思考了 3,552 個 token、
            # 花掉 49.6 秒；關掉之後同一題只要 0.7 秒。
            # 這個系統每輪只需要一句短問句，不需要那種推理。
            # 對不支援思考的模型（gemma 等）這個欄位會被忽略，不影響。
            payload["think"] = think


        timeout = timeout or (OLLAMA_CLIENT_TIMEOUT if stream else 30)
        
        try:
            resp = requests.post(url, json=payload, stream=stream, timeout=timeout)
            resp.raise_for_status()
            
            if stream:
                return resp
            else:
                return resp.json()
        except requests.RequestException as e:
            logging.error(f"[OllamaClient Error] Failed to generate: {e}")
            raise

    def check_health(self, timeout=OLLAMA_HEALTH_TIMEOUT):
        try:
            resp = requests.get(self.base_url, timeout=timeout)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self, timeout=5):
        url = f"{self.base_url}/api/tags"
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json().get('models', [])
        except requests.RequestException as e:
            logging.error(f"[OllamaClient Error] Failed to list models: {e}")
            raise

    def delete_model(self, name, timeout=10):
        url = f"{self.base_url}/api/delete"
        payload = {"name": name}
        try:
            resp = requests.delete(url, json=payload, timeout=timeout)
            return resp.status_code == 200
        except requests.RequestException as e:
            logging.error(f"[OllamaClient Error] Failed to delete model {name}: {e}")
            return False

    def extract_json_from_response(self, response_text):
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None
