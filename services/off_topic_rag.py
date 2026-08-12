# -*- coding: utf-8 -*-
"""
off_topic_rag.py — 離題問題的檢索式婉拒（RAG）

問題：
  原本用關鍵字子字串比對，只認得列過的字，使用者換個說法就漏掉
  （「我的迴圈跑不出來」沒有「程式」二字）；而且回覆交給 LLM 改寫，
  同一個問題每次講法不同、立場時鬆時緊。

作法：
  把使用者的話拿去比對 data/off_topic_dataset.json，命中哪個類別，
  就回那個類別「寫死的台詞」——不經 LLM，所以字字一致、零延遲。

兩段式比對，因為兩種錯的代價不一樣：
  第一段 關鍵字錨點：命中即判定，近乎零誤判（「股票」「颱風」不可能是咖啡廳需求）。
  第二段 相似度檢索：補關鍵字漏掉的說法，門檻設保守一點。
  漏判（該擋沒擋）只是 LLM 多回一句廢話；
  誤殺（使用者在講需求卻被拒絕）會直接把人趕走，所以寧可漏不可誤。

相似度後端有兩種，介面相同：
  embedding  用 Ollama 的 /api/embed（需先 ollama pull 一顆 embedding 模型）。
             中文換句話說也認得，是這套真正該用的模式。
  lexical    純 Python 的中文字元 n-gram TF-IDF，零依賴、零下載。
             實測只認得字面重疊，「吃這個藥會不會有副作用」會被「會不會下雨」
             拉走——僅供沒有 embedding 模型時保底，不要當成主力。

後端選擇：環境變數 OFF_TOPIC_EMBED_MODEL 指定模型名稱即啟用 embedding，
未設定或呼叫失敗就自動退回 lexical。
"""

import json
import math
import os
import re
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATASET_PATH = os.path.join(_ROOT, 'data', 'off_topic_dataset.json')
_VECTOR_CACHE_PATH = os.path.join(_ROOT, 'data', 'off_topic_vectors.json')

_CACHE = None

# 比對前丟掉的雜訊：標點、空白、語助詞。「幫我寫一首詩吧！」要能對上「寫首詩」。
_NOISE = re.compile(r'[\s，。、！？!?,.~～…「」『』()（）:：;；\-—_"\'’]+')
_FILLERS = ('請問', '請', '幫我', '可以', '嗎', '呢', '啊', '喔', '唷', '吧', '了', '一下')


# ----------------------------------------------------------------------
# 共用
# ----------------------------------------------------------------------

def _normalize(text: str) -> str:
    text = (text or '').lower()
    text = _NOISE.sub('', text)
    for f in _FILLERS:
        text = text.replace(f, '')
    return text


def _mentions_cafe(text: str) -> bool:
    """
    同一句裡也講了「找店」才會用的詞 → 一律不判離題
    （「幫我查有插座的咖啡廳」不能被當成叫我查資料）。

    刻意不用 intent_classifier 的 CAFE_KEYWORDS：那份清單為了檢索店家而放很寬，
    含「花蓮」「結果」「熱」，拿來當豁免會讓「花蓮會不會下雨」也逃掉。
    """
    lower = (text or '').lower()
    return any(term in lower for term in _load()['anchors'])


# ----------------------------------------------------------------------
# lexical 後端：中文字元 n-gram TF-IDF
# ----------------------------------------------------------------------

def _ngrams(text: str, sizes) -> Counter:
    """英數連續片段整段收錄（python / sql 這種詞不該被切碎），中文走字元 n-gram。"""
    grams = Counter()
    norm = _normalize(text)
    for n in sizes:
        for i in range(max(0, len(norm) - n + 1)):
            grams[norm[i:i + n]] += 1
    for word in re.findall(r'[a-z0-9]{2,}', norm):
        grams[word] += 2
    return grams


def _build_lexical(texts, cfg):
    sizes = tuple(cfg.get('ngram_sizes', [2, 3]))
    doc_grams = [_ngrams(t, sizes) for t in texts]

    df = Counter()
    for g in doc_grams:
        df.update(g.keys())
    total = len(doc_grams)

    # 跨太多例句的 n-gram 一律丟掉。中文問句共用大量框架
    # ——「怎麼辦」「有推薦的」「多少」——留著會讓主題完全進不到分數裡。
    cutoff = max(3, int(total * float(cfg.get('df_cutoff_ratio', 0.03))))
    idf = {g: math.log((total + 1) / (c + 1)) + 1.0
           for g, c in df.items() if c <= cutoff}

    vectors = []
    for grams in doc_grams:
        vec = {g: (1 + math.log(c)) * idf[g] for g, c in grams.items() if g in idf}
        vectors.append(_l2(vec))
    return {'kind': 'lexical', 'vectors': vectors, 'idf': idf, 'sizes': sizes}


def _l2(vec: dict) -> dict:
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def _lexical_query(backend, text):
    grams = _ngrams(text, backend['sizes'])
    idf = backend['idf']
    return _l2({g: (1 + math.log(c)) * idf[g] for g, c in grams.items() if g in idf})


def _lexical_scores(backend, qv):
    if not qv:
        return [0.0] * len(backend['vectors'])
    return [sum(w * dv[g] for g, w in qv.items() if g in dv)
            for dv in backend['vectors']]


# ----------------------------------------------------------------------
# embedding 後端：Ollama /api/embed
# ----------------------------------------------------------------------

def _embed(model, texts):
    import requests
    base = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
    r = requests.post(f'{base}/api/embed',
                      json={'model': model, 'input': texts}, timeout=120)
    r.raise_for_status()
    return r.json()['embeddings']


def _unit(vec):
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def _build_embedding(texts, model, fingerprint):
    """
    整份資料集只 embed 一次，結果連同指紋存檔；
    資料集或模型沒變就直接讀快取，服務啟動不用等。
    """
    if os.path.exists(_VECTOR_CACHE_PATH):
        try:
            with open(_VECTOR_CACHE_PATH, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            if cached.get('fingerprint') == fingerprint:
                return {'kind': 'embedding', 'model': model,
                        'vectors': cached['vectors']}
        except (ValueError, KeyError, OSError):
            pass

    vectors = [_unit(v) for v in _embed(model, texts)]
    try:
        with open(_VECTOR_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump({'fingerprint': fingerprint, 'model': model,
                       'vectors': vectors}, f)
    except OSError:
        pass
    return {'kind': 'embedding', 'model': model, 'vectors': vectors}


def _embedding_scores(backend, qv):
    return [sum(a * b for a, b in zip(qv, dv)) for dv in backend['vectors']]


# ----------------------------------------------------------------------
# 載入
# ----------------------------------------------------------------------

def _build():
    with open(_DATASET_PATH, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    cfg = raw.get('retrieval', {})
    categories = raw.get('categories', [])

    # 關鍵字錨點：長的先比，避免「程式」蓋掉「程式碼」
    keywords = []
    for cat in categories:
        for kw in cat.get('keywords', []):
            keywords.append((kw.lower(), cat['id']))
    keywords.sort(key=lambda x: len(x[0]), reverse=True)

    texts, labels, cat_ids = [], [], []
    for cat in categories:
        for ex in cat.get('examples', []):
            texts.append(ex)
            labels.append('off_topic')
            cat_ids.append(cat['id'])
    for ex in (raw.get('on_topic_guards') or {}).get('examples', []):
        texts.append(ex)
        labels.append('on_topic')
        cat_ids.append(None)

    # 預設就用 bge-m3；模型沒 pull、Ollama 沒開、或呼叫失敗都會自動退回 lexical，
    # 所以部署到沒有這顆模型的機器上不會壞，只是準度降回字面比對。
    # 要強制走 lexical（例如單元測試不想依賴 Ollama）就設成空字串。
    model = os.getenv('OFF_TOPIC_EMBED_MODEL', 'bge-m3').strip()
    backend = None
    if model:
        fingerprint = f'{model}|{len(texts)}|{hash(tuple(texts)) & 0xffffffff}'
        try:
            backend = _build_embedding(texts, model, fingerprint)
        except Exception as e:                                  # noqa: BLE001
            import logging
            logging.warning('離題檢索：embedding 後端不可用（%s），退回 lexical', e)
    if backend is None:
        backend = _build_lexical(texts, cfg)

    key = 'min_score_embedding' if backend['kind'] == 'embedding' else 'min_score'
    return {
        'backend': backend,
        'labels': labels,
        'cat_ids': cat_ids,
        'keywords': keywords,
        'anchors': [t.lower() for t in
                    (raw.get('cafe_anchor_terms') or {}).get('terms', [])],
        'min_score': float(cfg.get(key, 0.28)),
        'guard_margin': float(cfg.get('guard_margin', 0.04)),
        'responses': {c['id']: c['response'] for c in categories},
        'names': {c['id']: c['name'] for c in categories},
    }


def _load():
    global _CACHE
    if _CACHE is None:
        _CACHE = _build()
    return _CACHE


def reload_dataset():
    """改完 JSON 不必重啟服務。"""
    global _CACHE
    _CACHE = None
    return _load()


def backend_name():
    return _load()['backend']['kind']


# ----------------------------------------------------------------------
# 對外
# ----------------------------------------------------------------------

def search(user_message: str, top_k: int = 5):
    """最相近的幾筆 [(label, category_id, score, example)]，調門檻與除錯用。"""
    state = _load()
    backend = state['backend']
    if backend['kind'] == 'embedding':
        try:
            qv = _unit(_embed(backend['model'], [user_message])[0])
        except Exception:                                       # noqa: BLE001
            return []
        scores = _embedding_scores(backend, qv)
    else:
        scores = _lexical_scores(backend, _lexical_query(backend, user_message))

    ranked = sorted(
        zip(state['labels'], state['cat_ids'], scores),
        key=lambda x: x[2], reverse=True
    )
    return ranked[:top_k]


def match_keyword(user_message: str):
    """關鍵字錨點階段。回傳 (keyword, category_id) 或 (None, None)。"""
    text = (user_message or '').lower()
    if not text.strip() or _mentions_cafe(text):
        return None, None
    # 原文與去掉語助詞的版本都比一次：「可以幫我翻譯一下嗎」要對得上「幫我翻譯」
    stripped = _normalize(text)
    for kw, cat_id in _load()['keywords']:
        if kw in text or kw.replace(' ', '') in stripped:
            return kw.strip(), cat_id
    return None, None


def classify(user_message: str):
    """
    判斷是不是離題，並取出該回的固定台詞。

    回傳 (is_off_topic, category_id, response, detail)
      detail — {'stage': 'keyword'|'retrieval'|None, 'score': float, 'hit': str|None}
    """
    state = _load()
    blank = (False, None, None, {'stage': None, 'score': 0.0, 'hit': None})
    if not (user_message or '').strip():
        return blank

    kw, cat_id = match_keyword(user_message)
    if kw:
        return (True, cat_id, state['responses'].get(cat_id),
                {'stage': 'keyword', 'score': 1.0, 'hit': kw})

    if _mentions_cafe(user_message):
        return blank

    hits = search(user_message, top_k=10)
    if not hits:
        return blank

    best_off = next((h for h in hits if h[0] == 'off_topic'), None)
    best_guard = next((h for h in hits if h[0] == 'on_topic'), None)
    score = best_off[2] if best_off else 0.0

    if not best_off or score < state['min_score']:
        return (False, None, None,
                {'stage': None, 'score': score, 'hit': None})

    # 護欄：使用者可能用「幫我算一下兩個人多少錢」這種句型講需求，
    # 和「幫我算數學」字面很像。護欄贏（或差距在容忍範圍內）就放行。
    if best_guard and best_guard[2] + state['guard_margin'] >= score:
        return (False, None, None,
                {'stage': None, 'score': score, 'hit': None})

    cat_id = best_off[1]
    return (True, cat_id, state['responses'].get(cat_id),
            {'stage': 'retrieval', 'score': score, 'hit': None})


def category_name(category_id):
    return _load()['names'].get(category_id, category_id)
