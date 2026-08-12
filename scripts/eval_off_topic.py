# -*- coding: utf-8 -*-
"""
eval_off_topic.py — 量離題檢索準不準

跑法：
    venv\\Scripts\\python.exe scripts\\eval_off_topic.py
    venv\\Scripts\\python.exe scripts\\eval_off_topic.py --sweep   # 掃門檻，看該設多少

看三個數字：
    攔截率   離題的有沒有被擋下來（漏掉只是多回一句廢話，不致命）
    分類正確 擋下來之後有沒有回對類別的台詞（回錯類別會很突兀）
    誤殺率   使用者在講需求卻被當成離題 —— 這個要壓到 0，比前兩個都重要
"""

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from services import off_topic_rag  # noqa: E402

EVAL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'off_topic_eval.json'
)


def load_eval():
    with open(EVAL_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def run(verbose=True):
    data = load_eval()
    state = off_topic_rag._load()

    blocked = correct = 0
    misses, wrong_cat = [], []
    for case in data['off_topic']:
        is_off, cat, _, d = off_topic_rag.classify(case['text'])
        score = d['score']
        if is_off:
            blocked += 1
            if cat == case['expect']:
                correct += 1
            else:
                wrong_cat.append((case['text'], case['expect'], cat, score))
        else:
            misses.append((case['text'], case['expect'], score))

    false_kills = []
    for text in data['on_topic']:
        is_off, cat, _, d = off_topic_rag.classify(text)
        if is_off:
            false_kills.append((text, cat, d['score']))

    n_off, n_on = len(data['off_topic']), len(data['on_topic'])
    if verbose:
        print(f"後端 {off_topic_rag.backend_name()}   "
              f"門檻 min_score={state['min_score']}  guard_margin={state['guard_margin']}\n")
        print(f"攔截率    {blocked}/{n_off}  ({blocked / n_off:.0%})")
        print(f"分類正確  {correct}/{n_off}  ({correct / n_off:.0%})")
        print(f"誤殺      {len(false_kills)}/{n_on}  ({len(false_kills) / n_on:.0%})"
              f"  {'← 要壓到 0' if false_kills else '✓'}\n")

        if misses:
            print('沒攔到（會走一般流程，LLM 自己回）：')
            for text, expect, score in misses:
                print(f'  {text}   期望 {expect}  最高分 {score:.3f}')
            print()
        if wrong_cat:
            print('攔到了但回錯類別的台詞：')
            for text, expect, got, score in wrong_cat:
                print(f'  {text}   期望 {expect} → 實得 {got}  ({score:.3f})')
            print()
        if false_kills:
            print('誤殺（使用者在講需求卻被拒絕）：')
            for text, cat, score in false_kills:
                print(f'  {text}   被當成 {cat}  ({score:.3f})')
            print()

    return {'blocked': blocked, 'correct': correct, 'false_kills': len(false_kills),
            'n_off': n_off, 'n_on': n_on}


def sweep():
    """掃 min_score，找誤殺為 0 的前提下攔截率最高的設定。"""
    data = load_eval()
    print(f'{"min_score":>10}  {"攔截":>6}  {"分類對":>6}  {"誤殺":>5}')
    for step in range(10, 46, 2):
        thr = step / 100
        state = off_topic_rag._load()
        state['min_score'] = thr
        blocked = correct = kills = 0
        for case in data['off_topic']:
            is_off, cat, _, _d = off_topic_rag.classify(case['text'])
            if is_off:
                blocked += 1
                correct += (cat == case['expect'])
        for text in data['on_topic']:
            is_off, _c, _r, _d = off_topic_rag.classify(text)
            kills += is_off
        flag = '  ← 誤殺' if kills else ''
        print(f'{thr:>10.2f}  {blocked:>6}  {correct:>6}  {kills:>5}{flag}')
    off_topic_rag.reload_dataset()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sweep', action='store_true', help='掃門檻')
    args = ap.parse_args()
    if args.sweep:
        sweep()
    else:
        run()
