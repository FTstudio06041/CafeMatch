# -*- coding: utf-8 -*-
"""
對話引導狀態機單元測試（純 Python，不需 DB / LLM）。

涵蓋：
  - 測驗準確度三級門檻（準 2 維／有點落差 3 維／完全不像我 4 維）
  - 按鈕制：狀態機永不回傳「直接推薦」
  - 「都可以」視為明確回答（維度記為不限、不重複追問）
  - 推薦後模式（卡片標記）
  - 偏好合併與清洗（pipeline 靜態方法）
  - 偏好調整層（準度權重、維度加分、硬過濾）
"""
import pytest

from services.conversation_guide import analyze_and_guide, apply_no_preference_answers


def kind_of(instruction):
    """把引導指令歸類成決策類型。"""
    assert instruction is not None, "狀態機不應回傳 None（推薦只能由按鈕觸發）"
    if '」的確認問題' in instruction:
        return '確認'
    if '已經透過下方卡片推薦過' in instruction:
        return '推薦後'
    if '大致掌握' in instruction:
        return '邀請按鈕'
    return '未知'


def focus_of(instruction):
    """取出確認指令針對的維度標籤。"""
    return instruction.split('把「')[1].split('」的確認問題')[0]


def guide(history, prefs):
    return analyze_and_guide(history, {'preferences': prefs})


# ==========================================
# 三級門檻
# ==========================================

def test_partial_doubt_needs_three_dims():
    """有點落差 → 收滿 3 維度才邀請按鈕。"""
    h = [{'role': 'ai', 'content': '準不準呀？'}, {'role': 'user', 'content': '有點落差'}]
    assert kind_of(guide(h, {})) == '確認'

    h += [{'role': 'ai', 'content': 'Q1？'}, {'role': 'user', 'content': '工作'}]
    assert kind_of(guide(h, {'purpose': ['工作']})) == '確認'

    h += [{'role': 'ai', 'content': 'Q2？'}, {'role': 'user', 'content': '安靜'}]
    assert kind_of(guide(h, {'purpose': ['工作'], 'vibe': ['安靜']})) == '確認'

    h += [{'role': 'ai', 'content': 'Q3？'}, {'role': 'user', 'content': '甜點'}]
    r = guide(h, {'purpose': ['工作'], 'vibe': ['安靜'], 'taste': ['甜點']})
    assert kind_of(r) == '邀請按鈕'


def test_inaccurate_needs_four_dims():
    """完全不像我 → 測驗作廢，收滿 4 維度才邀請按鈕。"""
    h = [{'role': 'ai', 'content': '準不準呀？'}, {'role': 'user', 'content': '完全不像我'}]
    prefs = {}
    labels = [
        ({'purpose': ['工作']}, '確認'),
        ({'purpose': ['工作'], 'vibe': ['安靜']}, '確認'),
        ({'purpose': ['工作'], 'vibe': ['安靜'], 'taste': ['甜點']}, '確認'),
        ({'purpose': ['工作'], 'vibe': ['安靜'], 'taste': ['甜點'], 'budget': ['平價']}, '邀請按鈕'),
    ]
    assert kind_of(guide(h, prefs)) == '確認'
    for prefs, expected in labels:
        h += [{'role': 'ai', 'content': '下一題？'}, {'role': 'user', 'content': '回答'}]
        assert kind_of(guide(h, prefs)) == expected


def test_accurate_needs_two_dims():
    """覺得準 → 2 維度即邀請按鈕。"""
    h = [
        {'role': 'ai', 'content': '準不準呀？'}, {'role': 'user', 'content': '蠻準的！'},
        {'role': 'ai', 'content': 'Q1？'}, {'role': 'user', 'content': '約會'},
        {'role': 'ai', 'content': 'Q2？'}, {'role': 'user', 'content': '網美'},
    ]
    r = guide(h, {'purpose': ['約會'], 'vibe': ['網美']})
    assert kind_of(r) == '邀請按鈕'


# ==========================================
# 按鈕制
# ==========================================

def test_specific_first_message_still_invites_button():
    """第一句就很具體 → 也只邀請按鈕，不自動推薦。"""
    h = [{'role': 'user', 'content': '我想找安靜可以工作的咖啡廳'}]
    r = guide(h, {'purpose': ['工作'], 'vibe': ['安靜']})
    assert kind_of(r) == '邀請按鈕'


def test_vague_first_message_confirms():
    h = [{'role': 'user', 'content': '推薦咖啡廳'}]
    r = guide(h, {})
    assert kind_of(r) == '確認'
    assert focus_of(r) == '造訪目的'


def test_after_recommendation_enters_post_mode():
    """歷史帶卡片標記 → 推薦後模式（不出新卡、導回按鈕）。"""
    h = [
        {'role': 'user', 'content': '推薦咖啡廳'},
        {'role': 'ai', 'content': '這幾家都很適合！\n[已推薦店家卡片]'},
        {'role': 'user', 'content': '第一家有插座嗎？'},
    ]
    assert kind_of(guide(h, {})) == '推薦後'


# ==========================================
# 「都可以」也是明確回答
# ==========================================

_ASKED_PURPOSE = {
    'role': 'ai',
    'content': '想做什麼呢？\n[QUICK_OPTIONS] 專心工作讀書 | 放空放鬆 | 朋友聚會 | 約會',
}


def test_no_preference_marks_dimension():
    h = [
        {'role': 'user', 'content': '推薦咖啡廳'},
        _ASKED_PURPOSE,
        {'role': 'user', 'content': '都可以'},
    ]
    prefs = apply_no_preference_answers(h, {})
    assert prefs.get('purpose') == ['不限']


def test_no_preference_moves_to_next_dimension():
    h = [
        {'role': 'user', 'content': '推薦咖啡廳'},
        _ASKED_PURPOSE,
        {'role': 'user', 'content': '都可以'},
    ]
    r = guide(h, {})
    assert kind_of(r) == '確認'
    assert focus_of(r) == '氛圍偏好', '不應重複追問已回答「都可以」的維度'


def test_real_preference_replaces_no_preference():
    """先答不限、後來給了真實偏好 → 真實偏好優先。"""
    from services.chat_pipeline_service import ChatPipelineService
    merged = ChatPipelineService._merge_preferences(
        {'purpose': ['不限']}, {'purpose': ['工作']}
    )
    assert merged['purpose'] == ['工作']


# ==========================================
# 偏好合併與清洗
# ==========================================

def test_merge_preferences_dedupes_and_caps():
    from services.chat_pipeline_service import ChatPipelineService
    merged = ChatPipelineService._merge_preferences(
        {'vibe': ['安靜', '老宅']}, {'vibe': ['安靜', '日式'], 'budget': ['平價']}
    )
    assert merged['vibe'] == ['安靜', '老宅', '日式']
    assert merged['budget'] == ['平價']


def test_clean_pref_dict_rejects_garbage():
    from services.chat_pipeline_service import ChatPipelineService
    clean = ChatPipelineService._clean_pref_dict({
        'vibe': ['安靜', 123, ''],
        'hacker': ['payload'],
        'budget': 'not-a-list',
    })
    assert clean == {'vibe': ['安靜']}


# ==========================================
# 偏好調整層（GNN 輸入）
# ==========================================

def test_adjuster_accuracy_weights():
    from services.preference_adjuster import build_gnn_input
    base = {'work': 8, 'env': 6, 'social': 2, 'taste': 4, 'cp': 5}

    adjusted, _, acc = build_gnn_input(base, [], {})
    assert acc == 'accurate' and adjusted['work'] == 8.0

    adjusted, _, acc = build_gnn_input(base, [{'role': 'user', 'content': '有點落差'}], {})
    assert acc == 'partial' and adjusted['work'] == 4.0

    adjusted, _, acc = build_gnn_input(base, [{'role': 'user', 'content': '完全不像我'}], {})
    assert acc == 'inaccurate' and adjusted['work'] == 0.0


def test_fast_path_extracts_without_llm():
    """點選快速選項這類短訊息，規則就能萃取（不呼叫 LLM）。"""
    from services.preference_service import _rule_extract
    assert _rule_extract('專心工作讀書') == {'purpose': ['工作', '讀書']}
    assert _rule_extract('安靜舒服')['vibe']
    assert _rule_extract('平價實惠') == {'budget': ['平價']}
    assert _rule_extract('嗯嗯好') == {}


def test_blend_scores_favours_tag_matches():
    """標籤匹配的店家，混合分數應高於同等 GNN 分數但沒匹配的店。"""
    from services.gnn_recommender import _blend_scores
    id2tags = {1: ['甜點', '蛋糕'], 2: ['插座', '安靜']}
    candidates = [
        {'cafe_id': 1, 'gnn_score': 0.97},
        {'cafe_id': 2, 'gnn_score': 0.98},
    ]
    _blend_scores(candidates, ['甜點'], id2tags, weight=0.4)
    by_id = {c['cafe_id']: c for c in candidates}
    assert by_id[1]['tag_score'] == 1.0
    assert by_id[2]['tag_score'] == 0.0
    assert by_id[1]['blended_score'] > by_id[2]['blended_score']


def test_blend_without_keywords_keeps_gnn_order():
    from services.gnn_recommender import _blend_scores
    candidates = [
        {'cafe_id': 1, 'gnn_score': 0.90},
        {'cafe_id': 2, 'gnn_score': 0.95},
    ]
    _blend_scores(candidates, [], {}, weight=0.4)
    by_id = {c['cafe_id']: c for c in candidates}
    assert by_id[2]['blended_score'] > by_id[1]['blended_score']


def test_adjuster_keyword_boosts_and_hard_filters():
    from services.preference_adjuster import build_gnn_input
    adjusted, hard, _ = build_gnn_input(
        None, [], {'purpose': ['聚會'], 'taste': ['甜點'], 'special': ['寵物', '插座']}
    )
    assert adjusted['social'] >= 3
    assert adjusted['taste'] >= 3
    assert adjusted['work'] >= 2      # 插座 → 工作型場域
    assert hard['pet'] is True
    assert hard['parking'] is False
