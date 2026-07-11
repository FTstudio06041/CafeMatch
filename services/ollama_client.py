import requests
import logging
import os
import json
import re
from config.settings import OLLAMA_BASE_URL
from config.ai_constants import OLLAMA_CLIENT_TIMEOUT, OLLAMA_HEALTH_TIMEOUT

class OllamaClient:
    def __init__(self, base_url=None):
        self.base_url = base_url or OLLAMA_BASE_URL

    def generate(self, model, prompt, stream=False, timeout=None, format=None, options=None):
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
