"""
需求覆蓋核對：使用者講得出口的條件，遠多於系統認得的條件。

「水菸」既不在 tags 表、也不在五維加分表裡，原本會一路靜靜穿過硬過濾與
標籤比對，最後被放寬機制補滿名額，推出一批毫不相干的店。這裡確認它現在
會被抓出來，而且抓出來之後真的進得了 Prompt。
"""
import pytest

from app import app, db
from services import cafe_facts, ai_service


@pytest.fixture
def seeded():
    """建一家有標籤的店，並清掉 cafe_facts 的 10 分鐘快取。"""
    from models import Cafes, Tags

    with app.app_context():
        assert db.engine.url.drivername.startswith('sqlite'), (
            f'測試拒絕在非 SQLite 資料庫上執行：{db.engine.url}'
        )
        db.create_all()
        cafe = Cafes(name='測試咖啡', address='花蓮市測試路 1 號', cost='100-200')
        cafe.tags = [Tags(tag_name='肉桂捲'), Tags(tag_name='插座'), Tags(tag_name='香')]
        db.session.add(cafe)
        db.session.commit()

        cafe_facts._vocab_cache = None
        cafe_facts._cache = None
        yield

        db.session.remove()
        db.drop_all()
        cafe_facts._vocab_cache = None
        cafe_facts._cache = None


def test_uncovered_condition_is_reported(seeded):
    """資料庫完全查不到的需求要被指名，不能混在「系統有處理」裡。"""
    coverage = cafe_facts.classify_conditions({
        'special': ['有水菸'],
        'taste': ['想吃肉桂捲'],
        'vibe': ['安靜'],
    })

    assert coverage['uncovered'] == ['有水菸']
    assert [v['text'] for v in coverage['verifiable']] == ['想吃肉桂捲']
    assert coverage['soft'] == ['安靜']
    assert coverage['total_cafes'] == 1


def test_single_char_tags_do_not_fake_coverage(seeded):
    """
    292 個標籤裡有「香」「杯」「烤」這種評論碎片。若讓它們參與子字串比對，
    幾乎任何句子都會被判成「查得到」—— 那等於把這道檢查整個關掉。
    """
    coverage = cafe_facts.classify_conditions({'taste': ['想喝香醇一點的水菸風味']})

    assert coverage['verifiable'] == []
    assert coverage['uncovered'] == ['想喝香醇一點的水菸風味']


def test_negative_conditions_are_not_treated_as_demands(seeded):
    """「不要有水菸」不是要系統去滿足的東西，不該被回報成查無資料。"""
    coverage = cafe_facts.classify_conditions({'special': ['不要有水菸'], 'budget': ['不限']})

    assert coverage['uncovered'] == []
    assert coverage['verifiable'] == []


def test_empty_vocabulary_reports_nothing(seeded):
    """
    詞彙表讀不到（資料庫掛了）時一律不報 —— 寧可少講一句，
    也不要對著使用者宣稱「我們沒有這個」。
    """
    cafe_facts._vocab_cache = {'tags': {}, 'total_cafes': 0}
    cafe_facts._vocab_at = float('inf')
    try:
        coverage = cafe_facts.classify_conditions({'special': ['有水菸']})
        assert coverage['uncovered'] == []
    finally:
        cafe_facts._vocab_cache = None
        cafe_facts._vocab_at = 0.0


def test_prompt_carries_coverage_and_rule():
    """查無資料時，揭露規則與核對結論都要進 Prompt。"""
    coverage = {
        'uncovered': ['有水菸'],
        'verifiable': [{'text': '插座', 'evidence': '插座', 'count': 6}],
        'soft': ['安靜'],
        'total_cafes': 56,
    }
    prompt = ai_service.build_prompt(
        user_message='推薦花蓮有水菸的咖啡廳',
        history=[],
        is_cafe_related=True,
        cafe_context='- 測試咖啡 | 標籤：插座',
        guide_instruction=None,
        extracted_preferences={'special': ['有水菸']},
        cards_mode=True,
        coverage=coverage,
    )

    assert '<REQUEST_COVERAGE>' in prompt
    assert '有水菸' in prompt
    assert '全部 56 家店都沒有「有水菸」這項資料' in prompt
    assert '必須誠實揭露' in prompt
    # soft 條件系統確實有處理，講出來只會混淆
    assert '安靜' not in prompt.split('<REQUEST_COVERAGE>')[1]


def test_prompt_stays_clean_when_everything_is_covered():
    """全部對得上時不注入 —— 講「全部滿足」只會誘導模型複述條件。"""
    prompt = ai_service.build_prompt(
        user_message='推薦有插座的咖啡廳',
        history=[],
        is_cafe_related=True,
        cafe_context='- 測試咖啡 | 標籤：插座',
        guide_instruction=None,
        extracted_preferences={'special': ['插座']},
        cards_mode=True,
        coverage={'uncovered': [], 'verifiable': [{'text': '插座', 'count': 6}],
                  'soft': [], 'total_cafes': 56},
    )

    assert '<REQUEST_COVERAGE>' not in prompt
    assert '必須誠實揭露' not in prompt


def test_recognised_but_unusable_conditions_are_still_reported(seeded):
    """
    guide_dimensions.json 的 detect_keywords 認得「包廂」，但標籤表沒有、
    硬條件也沒有 —— 推薦時它一點作用都起不了。「聽得懂」不等於「做得到」，
    這種條件必須照樣回報，否則使用者又會拿到一批沒有包廂的店而不知情。
    """
    coverage = cafe_facts.classify_conditions({'special': ['要有包廂']})

    assert coverage['uncovered'] == ['要有包廂']
    assert coverage['soft'] == []


def test_partial_tag_match_is_not_verifiable(seeded):
    """
    「無麩質甜點」含有標籤「甜點」，但關鍵需求是「無麩質」。
    用 2/5 的重疊宣告可驗證，等於拿甜點店去回答無麩質的問題。
    """
    coverage = cafe_facts.classify_conditions({'taste': ['無麩質肉桂捲甜點']})

    assert coverage['verifiable'] == []


def test_common_phrasing_for_late_hours_triggers_night_filter():
    """
    「營業到很晚」是最自然的講法，原本不在硬條件名單裡 —— 硬過濾從未被觸發，
    使用者以為系統有篩，實際上沒有。
    """
    from services.preference_adjuster import build_gnn_input

    _scores, hard_filters, _accuracy = build_gnn_input(
        None, [], {'special': ['想找營業到很晚的店']}
    )

    assert hard_filters['night'] is True


def test_everyday_vibe_wording_is_not_flagged_as_missing(seeded):
    """
    誤報比漏報傷得多：對著使用者說「我們沒有氣氛這項資料」會很荒謬。
    引導設定檔認得的日常說法，五維加分表也要跟上。
    """
    coverage = cafe_facts.classify_conditions({
        'vibe': ['氣氛要好', '清幽一點'],
        'purpose': ['帶筆電來唸書', '跟同事聚聚'],
        'taste': ['想喝冰的'],
        'budget': ['不想太貴'],
    })

    assert coverage['uncovered'] == []


def test_numeric_conditions_are_never_reported_missing(seeded):
    """
    「低於500」三層詞彙表全不中，差點被宣告成「沒有任何一家符合」——
    而 500 元以下的店其實一大堆。帶數字的條件講的多半是價格或時間，
    cafes.cost 與 operatinghours 都有資料，不能報成查無。
    """
    coverage = cafe_facts.classify_conditions({
        'budget': ['低於500', '一百元以內'],
        'special': ['營業到22點'],
    })

    assert coverage['uncovered'] == []
