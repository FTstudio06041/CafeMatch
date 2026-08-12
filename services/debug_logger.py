# -*- coding: utf-8 -*-
"""
debug_logger.py — 對話與推薦的終端除錯輸出

把每一輪對話「系統知道了什麼、決定做什麼」印在後端終端機上，
方便開發時追蹤資料怎麼被調整。

輸出範例：
  ┌─ 第 3 輪 ─────────────────────────────────────────
  │ 使用者    專心工作讀書
  │ 本輪萃取  purpose: 工作, 讀書                （快篩，未呼叫 LLM）
  │ 累積偏好  purpose: 工作,讀書 ／ vibe: 安靜
  │ 掌握度    2 / 5 個維度
  │ 狀態機    確認需求 → 這輪問「氛圍偏好」
  └───────────────────────────────────────────────────

關閉方式：環境變數 CHAT_DEBUG_LOG=0
"""

import os

DIMS = ('work', 'env', 'social', 'taste', 'cp')
DIM_LABELS = {
    'purpose': '造訪目的', 'vibe': '氛圍偏好', 'taste': '口味偏好',
    'budget': '預算考量', 'special': '特殊需求',
}
SCORE_LABELS = {
    'work': '工作專注', 'env': '空間氛圍', 'social': '社交',
    'taste': '口味', 'cp': 'CP值',
}
ACCURACY_LABELS = {
    'accurate': '覺得準（測驗分數全採用）',
    'partial': '有點落差（測驗分數打對折）',
    'inaccurate': '完全不像（測驗分數作廢）',
}

WIDTH = 62


def enabled() -> bool:
    return os.getenv('CHAT_DEBUG_LOG', '1') not in ('0', 'false', 'False')


def _line(label, value=''):
    print(f'│ {label:<9}{value}', flush=True)


def _top(title):
    print('\n┌─ ' + title + ' ' + '─' * max(0, WIDTH - len(title) - 4), flush=True)


def _bottom():
    print('└' + '─' * (WIDTH - 1) + '\n', flush=True)


def _fmt_prefs(prefs):
    """{'purpose': ['工作','讀書'], 'vibe': ['安靜']} → 造訪目的: 工作,讀書 ／ 氛圍偏好: 安靜"""
    if not prefs:
        return '（無）'
    parts = []
    for key, vals in prefs.items():
        if vals:
            parts.append(f'{DIM_LABELS.get(key, key)}: {",".join(vals)}')
    return ' ／ '.join(parts) if parts else '（無）'


def _fmt_scores(scores):
    if not scores:
        return '（無）'
    return '  '.join(
        f'{SCORE_LABELS[d]} {float(scores.get(d, 0) or 0):g}' for d in DIMS
    )


def log_quiz_result(scores, user_message=''):
    """使用者帶著心理測驗結果進入聊天。"""
    if not enabled():
        return
    _top('心理測驗結果進場')
    if scores:
        _line('五維分數', _fmt_scores(scores))
    else:
        _line('五維分數', '（前端未帶入，將於推薦時查資料庫最新紀錄）')
    title = ''
    for mark in ('【咖啡人格】', '咖啡人格'):
        if mark in (user_message or ''):
            title = user_message.split(mark, 1)[1].split('\n')[0].strip()
            break
    if title:
        _line('人格稱號', title)
    _line('本輪動作', '先問使用者「這個結果準不準」，不推薦')
    _bottom()


def log_off_topic(user_message, category, stage=None, score=None, hit=None):
    """使用者要求與咖啡廳無關的事，系統直接婉拒。"""
    if not enabled():
        return
    from services import off_topic_rag
    _top('離題請求（已婉拒）')
    _line('使用者', (user_message or '')[:44])
    _line('命中類別', f'{off_topic_rag.category_name(category)}（{category}）')
    if stage == 'keyword':
        _line('判定方式', f'關鍵字錨點「{hit}」')
    else:
        _line('判定方式', f'語意檢索（{off_topic_rag.backend_name()}）'
                          f'  相似度 {float(score or 0):.3f}')
    _line('本輪動作', '回該類別的固定台詞，不經 LLM、不萃取偏好')
    _bottom()


def log_blocked_recommend(collected, needed):
    """使用者要求推薦，但掌握的資料還不足以做出有根據的推薦。"""
    if not enabled():
        return
    _top('推薦請求被擋下（資料不足）')
    _line('掌握度', f'{collected} / 5 個維度（至少需要 {needed} 個）')
    _line('本輪動作', '不出卡片，改由狀態機再確認一題')
    _bottom()


def log_round(turn, user_message, fresh_prefs, merged_prefs, dims,
              decision, focus_dim=None, fast_path=False,
              scores=None, prev_scores=None, asked=None):
    """一般對話輪：萃取什麼、累積什麼、五維怎麼變、狀態機決定什麼。"""
    if not enabled():
        return
    _top(f'第 {turn} 輪對話')
    _line('使用者', (user_message or '')[:44])
    source = '（關鍵字快篩，未呼叫 LLM）' if fast_path else '（LLM 萃取）'
    _line('本輪萃取', f'{_fmt_prefs(fresh_prefs)}  {source}')
    _line('累積偏好', _fmt_prefs(merged_prefs))
    if scores:
        _line('五維分數', _fmt_scores_delta(scores, prev_scores))
    _line('掌握度', f'{dims} / 5 個維度')
    if asked:
        _line('已問過', '、'.join(DIM_LABELS.get(k, k) for k in asked))
    decision_text = decision
    if focus_dim:
        decision_text = f'{decision} → 這輪問「{focus_dim}」'
    _line('狀態機', decision_text)
    _bottom()


def _fmt_scores_delta(scores, prev):
    """五維分數，有變動的加註增減量：口味 7 (+3)"""
    parts = []
    for d in DIMS:
        now = float(scores.get(d, 0) or 0)
        text = f'{SCORE_LABELS[d]} {now:g}'
        if prev:
            diff = now - float(prev.get(d, 0) or 0)
            if abs(diff) > 0.05:
                text += f' ({diff:+g})'
        parts.append(text)
    return '  '.join(parts)


def log_recommendation(accuracy, base_scores, adjusted_scores, hard_filters,
                       keywords, engine, cafes, excluded=0):
    """按下「直接推薦」時：測驗分數如何被調整、最後推了哪幾家。"""
    if not enabled():
        return
    _top('推薦運算（使用者按下「直接推薦咖啡廳」）')
    _line('測驗回饋', ACCURACY_LABELS.get(accuracy, accuracy))
    _line('測驗基礎', _fmt_scores(base_scores))
    _line('調整後', _fmt_scores(adjusted_scores))
    actives = [k for k, v in (hard_filters or {}).items() if v]
    filter_names = {'pet': '寵物友善', 'parking': '好停車', 'night': '深夜營業'}
    _line('硬過濾', '、'.join(filter_names.get(a, a) for a in actives) if actives else '（無）')
    _line('混合關鍵字', '、'.join(keywords) if keywords else '（無）')
    if excluded:
        _line('已排除', f'{excluded} 家（換一批）')
    engine_text = 'GNN 模型' if engine == 'gnn' else '關鍵字檢索（GNN 不可用，已回退）'
    names = '、'.join(f'{c.name}({c.id})' for c in (cafes or [])[:5])
    _line('推薦引擎', engine_text)
    _line('推薦結果', names or '（無）')
    _bottom()
