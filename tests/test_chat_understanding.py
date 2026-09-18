import json
from unittest.mock import Mock

import pytest
from flask import Flask

from services import ai_service, conversation_guide, preference_service
from services import chat_pipeline_service as pipeline
from services.chat_pipeline_service import ChatPipelineService
from services.preference_adjuster import build_gnn_input


def mock_extraction(monkeypatch, result):
    generate = Mock(return_value={'response': json.dumps(result, ensure_ascii=False)})
    monkeypatch.setattr(preference_service.OllamaClient, 'generate', generate)
    return generate


def test_free_text_uses_semantics_even_when_keywords_match(monkeypatch):
    message = '想找能趕論文的咖啡廳，不要太酸，每人200元內，離車站走路10分鐘內'
    expected = {
        'purpose': ['讀書'], 'taste': ['不要太酸'],
        'budget': ['每人200元內'], 'special': ['離車站走路10分鐘內'],
    }
    generate = mock_extraction(monkeypatch, {
        'preferences': expected,
        'evidence': {
            'purpose': '趕論文', 'taste': '不要太酸',
            'budget': '每人200元內', 'special': '離車站走路10分鐘內',
        },
        'dialogue_act': 'preferences', 'next_dimension': 'vibe',
    })
    result = preference_service.extract_preferences([], message, 'test-model')
    generate.assert_called_once()
    assert set(result['preferences']) == set(expected)
    assert '論文' in result['preferences']['purpose'][0]
    assert result['preferences']['taste'] == ['不要太酸']
    assert result['preferences']['budget'] == ['每人200元內']
    assert result['preferences']['special'] == ['離車站走路10分鐘內']
    assert result['replace_dimensions'] == ['budget']


def test_correction_replaces_old_requirement_but_keeps_other_conditions(monkeypatch):
    base = {'special': ['插座', '寵物友善'], 'vibe': ['安靜'], 'budget': ['每人200元內']}
    message = '不帶狗了，插座還是要，預算可以提高到300元'
    generate = mock_extraction(monkeypatch, {
        'preferences': {'special': ['插座'], 'budget': ['300元內']},
        'evidence': {'special': '不帶狗了，插座還是要', 'budget': '預算可以提高到300元'},
        'remove_preferences': {'special': ['寵物友善']},
        'dialogue_act': 'preferences',
    })
    result = preference_service.extract_preferences([], message, 'test-model', base)
    merged = ChatPipelineService._merge_preferences(
        base, result['preferences'], result['replace_dimensions'], result['remove_preferences']
    )
    assert merged['vibe'] == ['安靜']
    assert merged['budget'] == ['預算可以提高到300元']
    assert '寵物友善' not in merged['special']
    assert '插座' in preference_service.positive_keywords(merged)
    assert not build_gnn_input(None, [], merged)[1]['pet']
    assert '寵物友善' in generate.call_args.kwargs['prompt']


def test_explicit_unrestricted_answer_can_clear_a_previous_preference(monkeypatch):
    mock_extraction(monkeypatch, {
        'preferences': {'budget': ['不限']},
        'evidence': {'budget': '預算不限了'}, 'dialogue_act': 'preferences',
    })
    result = preference_service.extract_preferences(
        [], '預算不限了', 'test-model', {'budget': ['200元內']}
    )
    merged = ChatPipelineService._merge_preferences(
        {'budget': ['200元內']}, result['preferences'], result['replace_dimensions']
    )
    assert merged == {'budget': ['不限']}


def test_assistant_suggestions_are_not_user_preferences(monkeypatch):
    mock_extraction(monkeypatch, {
        'preferences': {'special': ['插座'], 'vibe': ['安靜']},
        'evidence': {'special': '要有插座', 'vibe': '安靜舒服'},
    })
    result = preference_service.extract_preferences(
        [{'role': 'ai', 'content': '安靜舒服、要有插座嗎？'}], '我還沒想好', 'test-model'
    )
    assert result['preferences'] == {}
    assert result['replace_dimensions'] == []


def test_literal_condition_repairs_wrong_dimension_and_preserves_degree(monkeypatch):
    mock_extraction(monkeypatch, {
        'preferences': {'vibe': ['不酸']},
        'evidence': {'vibe': '不要太酸'}, 'dialogue_act': 'preferences',
    })
    result = preference_service.extract_preferences([], '不要太酸', 'test-model')
    assert result['preferences'] == {'taste': ['不要太酸']}


def test_model_cannot_remove_unrelated_preferences_without_matching_evidence(monkeypatch):
    base = {'purpose': ['工作'], 'taste': ['不要太酸'], 'budget': ['200元內']}
    mock_extraction(monkeypatch, {
        'preferences': {'budget': ['300元內']},
        'evidence': {'purpose': '預算300元內', 'taste': '預算300元內', 'budget': '預算300元內'},
        'remove_preferences': {'purpose': ['工作'], 'taste': ['不要太酸'], 'budget': ['200元內']},
        'dialogue_act': 'preferences',
    })
    result = preference_service.extract_preferences([], '預算300元內', 'test-model', base)
    merged = ChatPipelineService._merge_preferences(
        base, result['preferences'], result['replace_dimensions'], result['remove_preferences']
    )
    assert merged == {'purpose': ['工作'], 'taste': ['不要太酸'], 'budget': ['預算300元內']}


def test_question_about_current_preference_does_not_change_its_meaning(monkeypatch):
    base = {'taste': ['不要太酸']}
    message = '你是不是把不要太酸當成喜歡酸了？'
    mock_extraction(monkeypatch, {
        'preferences': {'taste': ['不喜歡酸']},
        'evidence': {'taste': message}, 'remove_preferences': {'taste': ['不要太酸']},
        'dialogue_act': 'question',
    })
    result = preference_service.extract_preferences([], message, 'test-model', base)
    merged = ChatPipelineService._merge_preferences(
        base, result['preferences'], result['replace_dimensions'], result['remove_preferences']
    )
    assert merged == base


def test_one_quote_cannot_launder_a_whole_dimension(monkeypatch):
    """一句佐證只證得了一個條件，模型多寫的沒講過條件不能跟著過關。"""
    message = '不要太吵，可以待久一點'
    mock_extraction(monkeypatch, {
        'preferences': {'vibe': ['安靜', '有插座', '手沖好喝', '網美牆']},
        'evidence': {'vibe': '不要太吵'}, 'dialogue_act': 'preferences',
    })
    result = preference_service.extract_preferences([], message, 'test-model')
    assert result['preferences']['vibe'] == ['安靜']


def test_semantic_normalization_still_survives(monkeypatch):
    """收緊之後，原文沒有的說法仍要能被正規化成偏好。"""
    mock_extraction(monkeypatch, {
        'preferences': {'vibe': ['安靜']},
        'evidence': {'vibe': '不要太吵'}, 'dialogue_act': 'preferences',
    })
    result = preference_service.extract_preferences([], '不要太吵', 'test-model')
    assert result['preferences'] == {'vibe': ['安靜']}


def test_literal_values_are_not_capped_by_the_normalization_limit(monkeypatch):
    """原文照抄的值有幾個收幾個，配額只約束沒有原文可對的值。"""
    message = '安靜、有插座、不限時'
    mock_extraction(monkeypatch, {
        'preferences': {'special': ['插座', '不限時'], 'vibe': ['安靜']},
        'evidence': {'special': message, 'vibe': message}, 'dialogue_act': 'preferences',
    })
    result = preference_service.extract_preferences([], message, 'test-model')
    assert result['preferences']['special'] == ['插座', '不限時']
    assert result['preferences']['vibe'] == ['安靜']


@pytest.mark.parametrize('response', [[], {'preferences': []}, None])
def test_bad_extraction_does_not_erase_saved_preferences(monkeypatch, response):
    mock_extraction(monkeypatch, response)
    result = preference_service.extract_preferences([], '不要太酸', 'test-model')
    assert result['extraction_failed']
    assert result['preferences'] == {}


def test_exact_budget_option_preserves_the_amount_without_model(monkeypatch):
    generate = mock_extraction(monkeypatch, {})
    result = preference_service.extract_preferences([], '預算兩百內', 'test-model')
    assert result['preferences'] == {'budget': ['預算兩百內']}
    generate.assert_not_called()


@pytest.mark.parametrize('reply', ['不用插座', '可以帶狗', '沒有要吃甜點', '可以'])
def test_short_specific_answers_are_not_treated_as_unrestricted(reply):
    history = [
        {'role': 'ai', 'content': '[QUICK_OPTIONS] 要有插座 | 不限時久坐 | 寵物友善 | 沒特別需求'},
        {'role': 'user', 'content': reply},
    ]
    assert conversation_guide.apply_no_preference_answers(history, {}) == {}


def test_negative_conditions_do_not_boost_the_opposite_recommendation():
    prefs = {'special': ['不需要停車', '不要有貓', '不限時'], 'taste': ['不要甜點']}
    scores, filters, _ = build_gnn_input(None, [], prefs)
    assert filters == {'pet': False, 'parking': False, 'night': False}
    assert scores['taste'] == 0
    assert scores['work'] == 2
    assert preference_service.positive_keywords(prefs) == ['不限時']


def test_complete_phrases_still_match_recommendation_tags():
    keywords = preference_service.positive_keywords({'vibe': ['安靜舒服'], 'special': ['要有插座']})
    assert {'安靜', '舒服', '插座'} <= set(keywords)


def test_do_not_recommend_is_not_a_recommend_request():
    assert not conversation_guide.wants_recommendation('先不要直接推薦，我還有條件')
    assert conversation_guide.wants_recommendation('不要問了，直接推薦')


def test_question_is_not_lost_when_model_calls_it_chat():
    instruction = conversation_guide.analyze_and_guide(
        [{'role': 'user', 'content': '你是不是把不要太酸當成喜歡酸了？'}],
        {'preferences': {'taste': ['不要太酸']}, 'dialogue_act': 'chat'},
    )
    assert conversation_guide.classify_instruction(instruction)[0] == '回答提問'


def test_enough_specific_requirements_can_stop_before_all_dimensions():
    instruction = conversation_guide.analyze_and_guide(
        [{'role': 'user', 'content': '想工作，要有插座，200元內就好'}],
        {'preferences': {'purpose': ['工作'], 'special': ['插座'], 'budget': ['200元內']},
         'dialogue_act': 'preferences', 'next_dimension': None},
        has_quiz=False,
    )
    assert conversation_guide.classify_instruction(instruction)[0] == '邀請按鈕'


def test_requirement_phrased_as_question_can_continue_relevant_followup():
    instruction = conversation_guide.analyze_and_guide(
        [{'role': 'user', 'content': '有沒有能安靜工作的店？'}],
        {'preferences': {'purpose': ['工作'], 'vibe': ['安靜']},
         'dialogue_act': 'preferences', 'next_dimension': 'special'},
        has_quiz=False,
    )
    assert conversation_guide.classify_instruction(instruction) == ('確認', '特殊需求')


def test_prompt_keeps_first_turn_preferences_without_replaying_old_buttons():
    prompt = ai_service.build_prompt('幫我找店', [], True, '',
                                    extracted_preferences={'budget': ['200元內']})
    assert '200元內' in prompt
    prompt = ai_service.build_prompt(
        '不需要停車', [{'role': 'ai', 'content': '有其他需求嗎？\n[QUICK_OPTIONS] 甲 | 乙'}],
        True, '', guide_instruction='先確認最新條件',
    )
    assert '有其他需求嗎？' in prompt
    assert '[QUICK_OPTIONS]' not in prompt


@pytest.fixture
def pipeline_context(monkeypatch):
    app = Flask(__name__)
    app.secret_key = 'test'
    monkeypatch.setattr(pipeline, 'check_health', lambda: True)
    monkeypatch.setattr(pipeline, 'get_selected_model', lambda: 'test-model')
    monkeypatch.setattr(pipeline.off_topic_rag, 'classify', lambda _: (False, None, '', {}))
    monkeypatch.setattr(ChatPipelineService, '_resolve_quiz_scores', lambda _: None)
    monkeypatch.setattr(pipeline.debug_logger, 'log_round', lambda **_: None)
    with app.test_request_context('/'):
        yield


@pytest.mark.parametrize('ready', [False, True])
def test_followup_and_invitation_reach_model_with_latest_conditions(monkeypatch, pipeline_context, ready):
    prefs = {'purpose': ['工作'], 'vibe': ['安靜']}
    if ready:
        prefs.update({'taste': ['拿鐵'], 'budget': ['200元內'], 'special': ['插座']})
    monkeypatch.setattr(preference_service, 'extract_preferences', lambda *args, **kwargs: {
        'preferences': prefs, 'dialogue_act': 'preferences', 'next_dimension': 'special',
    })
    generate = Mock(return_value=iter([
        json.dumps({'response': '趕報告的話，需要插座讓筆電充電嗎？'}),
        json.dumps({'done': True}),
    ]))
    monkeypatch.setattr(ai_service, 'stream_generate', generate)
    chunks = [json.loads(chunk) for chunk in ChatPipelineService.generate_pipeline(
        {'message': '我想找安靜工作的咖啡廳', 'history': []}, False
    )]
    generate.assert_called_once()
    assert '安靜' in generate.call_args.kwargs['prompt_text']
    assert any('趕報告' in chunk.get('response', '') for chunk in chunks)
    if not ready:
        assert any('[QUICK_OPTIONS]' in chunk.get('response', '') for chunk in chunks)
    assert chunks[-1]['done']
