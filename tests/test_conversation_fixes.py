# -*- coding: utf-8 -*-
"""
2026-11 對話情境實測找出的問題（純 Python，不需 DB / LLM）。

涵蓋：
  - 短回應（「好」「哈哈」）不做相似度檢索，不會被婉拒
  - 預算上限解析、價位帶比對、整週公休排除
  - 營業時段條件：觸發晚間硬條件、萃取時不被同句其他子句蓋掉
  - 花蓮以外的地點直接說明服務範圍
  - 出卡片那一輪的提示詞：換一批、禁止自己做卡片
"""
import pytest


# ---------------------------------------------------------------- 離題

@pytest.mark.parametrize('text', ['好', '哈哈', '嗯', '對', 'OK', '？'])
def test_short_replies_are_never_off_topic(text):
    from services import off_topic_rag
    is_off, *_ = off_topic_rag.classify(text)
    assert is_off is False


def test_short_keyword_hits_are_still_blocked():
    """短句只是不做相似度檢索；關鍵字錨點照樣攔。"""
    from services import off_topic_rag
    is_off, cat, _, detail = off_topic_rag.classify('股票')
    assert is_off is True and detail['stage'] == 'keyword'


# ---------------------------------------------------------------- 預算

@pytest.mark.parametrize('text, expected', [
    ('預算兩百內', 200),
    ('百元有找', 100),
    ('平價實惠', 200),
    ('預算一個人500', 500),
    ('under 300', 300),
    ('預算改成三百好了', 300),
    ('一百五以內', 150),
    ('不限', None),
    ('想找安靜的', None),
])
def test_parse_budget_max(text, expected):
    from services.preference_adjuster import parse_budget_max
    assert parse_budget_max({'budget': [text]}) == expected


def test_budget_only_reads_budget_dimension():
    """其他維度的數字多半是時間或人數，不能當成預算。"""
    from services.preference_adjuster import parse_budget_max
    assert parse_budget_max({'special': ['晚上十點後還有開的'], 'purpose': ['三個人聚會']}) is None


def test_latest_budget_wins():
    from services.preference_adjuster import parse_budget_max
    assert parse_budget_max({'budget': ['預算兩百內', '改成三百']}) == 300


def test_required_ids_enforce_budget_and_opening():
    from services.cafe_facts import required_ids, cost_floor
    pools = {
        'open': {1, 2, 3, 4},           # 5 號整週公休
        'costs': {1: '$1-200', 2: '$200-400', 3: '$1-400', 4: None, 5: '$1-200'},
    }
    assert cost_floor('$200-400') == 200
    assert required_ids(pools) == {1, 2, 3, 4}
    # 「兩百內」：$200-400 的下限不低於 200，不算；價位不明的保留
    assert required_ids(pools, 200) == {1, 3, 4}
    assert required_ids(pools, 300) == {1, 2, 3, 4}
    # 資料讀不到 → 不套用
    assert required_ids({}, 200) is None


# ---------------------------------------------------------------- 營業時段

@pytest.mark.parametrize('text, night', [
    ('晚上十點後還有開的', True),
    ('營業到九點', True),
    ('深夜', True),
    ('晚上想喝咖啡', False),
    ('下午兩點後', False),
])
def test_night_flag(text, night):
    from services.preference_adjuster import hard_filter_flags
    assert ('night' in hard_filter_flags(text)) is night


def test_opening_hours_clause_has_a_dimension():
    """認不出維度的子句會被同一句裡別的子句整欄蓋掉。"""
    from services.preference_service import _clause_dimensions
    assert _clause_dimensions('晚上十點後還有開的') == {'special'}
    # 「一點」是程度詞，不是時間
    assert 'special' not in _clause_dimensions('安靜一點')


def test_two_clauses_in_one_dimension_are_both_kept(monkeypatch):
    """「我要帶狗去，晚上十點後還有開的」兩個條件都要留下。"""
    from services import preference_service

    class FakeClient:
        def generate(self, **kwargs):
            return {'response': (
                '{"remove_preferences": {}, "evidence": {"special": "我要帶狗去"},'
                ' "preferences": {"special": ["我要帶狗去", "晚上十點後還有開的"]},'
                ' "dialogue_act": "preferences", "next_dimension": null}'
            )}

        def extract_json_from_response(self, text):
            import json
            return json.loads(text)

    monkeypatch.setattr(preference_service, 'OllamaClient', FakeClient)
    result = preference_service.extract_preferences(
        [], '我要帶狗去，晚上十點後還有開的', 'any-model')
    assert result['preferences']['special'] == ['我要帶狗去', '晚上十點後還有開的']


def test_sit_long_is_a_special_need():
    from services.preference_service import _clause_dimensions
    assert _clause_dimensions('可以久坐') == {'special'}


# ---------------------------------------------------------------- 服務範圍

@pytest.mark.parametrize('text, outside', [
    ('台北信義區有什麼推薦的咖啡廳？', True),
    ('高雄的咖啡廳', True),
    ('我從台北過來，想找安靜的店', False),
    ('我是台北人', False),
    ('從台北來花蓮玩', False),
    ('想找東京那種風格的店', False),
    ('日式簡約', False),
    ('想找有貓的店', False),
])
def test_outside_service_area(text, outside):
    from services.service_area import outside_area
    assert bool(outside_area(text)) is outside


# ---------------------------------------------------------------- 卡片模式提示詞

def test_refresh_rule_only_when_cards_are_a_new_batch():
    from services.ai_service import build_prompt
    kwargs = dict(user_message='直接推薦咖啡廳', history=[], is_cafe_related=True,
                  cafe_context='x', cards_mode=True)
    assert '換一批' in build_prompt(refresh=True, **kwargs)
    assert '換一批' not in build_prompt(refresh=False, **kwargs)


def test_card_stop_sequences_cover_observed_fake_cards():
    """實測模型自己做卡片時用過的開頭記號，一定要在停止序列裡。"""
    from config.ai_constants import CARDS_MODE_STOP_SEQUENCES
    for marker in ('***', '【圖文卡片】', '[圖文卡片]', '![', '📍', '\n(', '\n（'):
        assert marker in CARDS_MODE_STOP_SEQUENCES


# ---------------------------------------------------------------- 逐店核對條件

def test_card_facts_wording():
    """全部、部分、0 家、無資料四種情況寫成不同句子，模型才分得出「都」與「其中幾家」。"""
    from services.ai_service import _format_card_facts
    text = _format_card_facts([
        {'text': '預算兩百內', 'matched': 5, 'total': 5},
        {'text': '晚上十點後還有開的', 'matched': 1, 'total': 5},
        {'text': '要帶狗', 'matched': 0, 'total': 5},
        {'text': '要有插座', 'matched': None, 'total': 5},
    ])
    assert '「預算兩百內」：下面 5 家全部符合' in text
    assert '有 1 家的資料顯示符合' in text
    assert '「要帶狗」：下面 5 家都沒有資料顯示符合' in text
    assert '「要有插座」：店家資料沒有明確標註' in text


def test_card_facts_rule_only_with_facts():
    from services.ai_service import build_prompt
    kwargs = dict(user_message='直接推薦咖啡廳', history=[], is_cafe_related=True,
                  cafe_context='x', cards_mode=True)
    with_facts = build_prompt(card_facts=[{'text': '甜點', 'matched': 2, 'total': 5}], **kwargs)
    assert '<CARD_FACTS>' in with_facts and '條件只能照核對結果講' in with_facts
    assert '<CARD_FACTS>' not in build_prompt(**kwargs)


def test_run_on_sentence_clauses_split_on_spaces(monkeypatch):
    """口語不打標點時，「可以久坐」仍要歸到特殊需求，且不重複留在氛圍。"""
    from services import preference_service

    class FakeClient:
        def generate(self, **kwargs):
            return {'response': (
                '{"remove_preferences": {}, "evidence": {},'
                ' "preferences": {"vibe": ["可以久坐"], "special": ["有wifi"]},'
                ' "dialogue_act": "preferences", "next_dimension": null}'
            )}

        def extract_json_from_response(self, text):
            import json
            return json.loads(text)

    monkeypatch.setattr(preference_service, 'OllamaClient', FakeClient)
    prefs = preference_service.extract_preferences(
        [], '想要有wifi 可以久坐', 'any-model')['preferences']
    assert '可以久坐' in prefs['special']
    assert 'vibe' not in prefs


def test_cafe_wording_rule():
    from config.prompts.task_rules import CAFE_TASK_RULES
    assert '不要說成餐廳' in CAFE_TASK_RULES
