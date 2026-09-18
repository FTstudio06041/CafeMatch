"""Exercise extraction and replies against a local model without writing chat or DB data."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.ai_service import build_prompt
from services.chat_pipeline_service import ChatPipelineService
from services.conversation_guide import analyze_and_guide
from services.ollama_client import OllamaClient
from services.preference_service import extract_preferences


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    history, preferences = [], {}
    messages = [
        '想找能趕論文的咖啡廳，不要太酸，每人200元內，離車站走路10分鐘內',
        '預算可以提高到300元，車站附近就不用了，但要有插座',
        '你是不是把不要太酸當成喜歡酸了？',
    ]
    for message in messages:
        print('USER:', message, flush=True)
        extracted = extract_preferences(history, message, args.model, preferences)
        preferences = ChatPipelineService._merge_preferences(
            preferences, extracted['preferences'], extracted.get('replace_dimensions'),
            extracted.get('remove_preferences'),
        )
        print('EXTRACTED:', json.dumps(extracted, ensure_ascii=False), flush=True)
        print('CURRENT:', json.dumps(preferences, ensure_ascii=False), flush=True)
        instruction = analyze_and_guide(
            history + [{'role': 'user', 'content': message}],
            {**extracted, 'preferences': preferences}, has_quiz=False,
        )
        prompt = build_prompt(message, history, True, '', instruction, preferences)
        response = OllamaClient().generate(
            model=args.model, prompt=prompt, stream=False, timeout=120,
        ).get('response', '')
        print('ASSISTANT:', response, flush=True)
        history.extend([
            {'role': 'user', 'content': message}, {'role': 'assistant', 'content': response},
        ])


if __name__ == '__main__':
    main()
