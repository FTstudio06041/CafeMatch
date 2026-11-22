"""咖啡護照、每日咖啡盲盒與滑卡。

規則判斷（evaluate_badges / choose_from_ranked）是純函式，直接測；
API 走 in-memory SQLite，GNN 在測試環境不可用，盲盒會走隨機路徑。
"""

import random
from datetime import datetime, timedelta

import pytest

from app import app, db
from config.settings import get_utc_now
from services import blindbox_service, passport_service

BADGES = [
    {'id': 'first', 'name': '第一枚章', 'rule': {'type': 'visit_count', 'count': 1}},
    {'id': 'three', 'name': '三家', 'rule': {'type': 'visit_count', 'count': 3}},
    {'id': 'half', 'name': '過半', 'rule': {'type': 'visit_ratio', 'ratio': 0.5}},
    {'id': 'work', 'name': '插座', 'rule': {'type': 'tag_count', 'count': 2, 'keywords': ['插座', '不限時']}},
    {'id': 'cheap', 'name': '銅板', 'rule': {'type': 'cost_count', 'count': 1, 'cost': '$1-200'}},
    {'id': 'out', 'name': '市區外', 'rule': {'type': 'area_excludes', 'count': 1, 'text': '花蓮市'}},
    {'id': 'box', 'name': '盲盒', 'rule': {'type': 'blindbox_count', 'count': 1}},
    {'id': 'streak', 'name': '連續', 'rule': {'type': 'week_streak', 'count': 3}},
    {'id': 'weird', 'name': '未知規則', 'rule': {'type': 'no_such_rule'}},
]


def _stamp(day, tags=(), cost='$200-400', address='970花蓮縣花蓮市中正路1號'):
    return {'visited_at': day, 'tags': list(tags), 'cost': cost, 'address': address}


def _by_id(results):
    return {b['id']: b for b in results}


# ==========================================
# 純函式
# ==========================================

def test_no_stamps_unlocks_nothing():
    res = _by_id(passport_service.evaluate_badges([], 10, [], BADGES))
    assert not any(b['unlocked'] for b in res.values())
    assert 'weird' not in res  # 不認得的規則直接略過，不會讓整個護照壞掉


def test_count_badges_unlock_on_the_stamp_that_crosses_the_line():
    d = datetime(2026, 11, 2, 4)
    stamps = [_stamp(d + timedelta(days=i)) for i in range(3)]
    res = _by_id(passport_service.evaluate_badges(stamps, 10, [], BADGES))
    assert res['first']['unlocked_at'].startswith('2026-11-02')
    assert res['three']['unlocked'] and res['three']['unlocked_at'].startswith('2026-11-04')
    assert res['half']['progress'] == 3 and res['half']['target'] == 5 and not res['half']['unlocked']


def test_legacy_stamps_without_date_count_as_earliest():
    stamps = [_stamp(datetime(2026, 11, 5)), _stamp(None)]
    res = _by_id(passport_service.evaluate_badges(stamps, 10, [], BADGES))
    assert res['first']['unlocked'] and res['first']['unlocked_at'] is None


def test_tag_cost_and_area_rules():
    d = datetime(2026, 11, 2)
    stamps = [
        _stamp(d, tags=['插座充足']),
        _stamp(d, tags=['不限時', '甜點']),
        _stamp(d, cost='$1-200', address='973花蓮縣吉安鄉中央路1號'),
    ]
    res = _by_id(passport_service.evaluate_badges(stamps, 10, [], BADGES))
    assert res['work']['unlocked']      # 子字串比對：「插座」對得上「插座充足」
    assert res['cheap']['unlocked']
    assert res['out']['unlocked']


def test_week_streak_needs_consecutive_weeks():
    mon = datetime(2026, 10, 26, 4)  # 台灣時間週一中午
    gap = [_stamp(mon), _stamp(mon + timedelta(days=7)), _stamp(mon + timedelta(days=21))]
    assert not _by_id(passport_service.evaluate_badges(gap, 10, [], BADGES))['streak']['unlocked']
    run = [_stamp(mon + timedelta(days=7 * i)) for i in range(3)] + [_stamp(mon + timedelta(days=1))]
    res = _by_id(passport_service.evaluate_badges(run, 10, [], BADGES))['streak']
    assert res['unlocked'] and res['progress'] == 3


def test_day_key_uses_taipei_time():
    # UTC 15:59 = 台灣 23:59 還是當天；UTC 16:00 = 台灣隔天 00:00
    assert passport_service.day_key(datetime(2026, 11, 14, 15, 59)) == '2026-11-14'
    assert passport_service.day_key(datetime(2026, 11, 14, 16, 0)) == '2026-11-15'
    assert passport_service.day_end_utc(datetime(2026, 11, 14, 3)) == datetime(2026, 11, 14, 16)


def test_week_key_uses_taipei_time():
    # UTC 週日 17:00 = 台灣週一 01:00，已經換週
    assert passport_service.week_key(datetime(2026, 11, 15, 17)) == '2026-W47'
    assert passport_service.week_key(datetime(2026, 11, 15, 15)) == '2026-W46'


def test_area_of():
    assert passport_service.area_of('970花蓮縣花蓮市軒轅路15號') == '花蓮市'
    assert passport_service.area_of('973花蓮縣吉安鄉中央路三段') == '吉安鄉'
    assert passport_service.area_of('') == ''


def test_choose_prefers_novel_cafes_within_gnn_pool():
    ranked = [{'cafe_id': i, 'rank': i, 'gnn_score': 0.9} for i in range(1, 21)]
    cafe_tags = {i: ['插座'] for i in range(1, 21)}
    cafe_tags[5] = ['老宅']        # 前 12 名裡唯一跟舒適圈不同的
    cafe_tags[15] = ['海景']       # 很新鮮，但 GNN 名次太後面，不該被挑
    chosen, nov = blindbox_service.choose_from_ranked(
        ranked, cafe_tags, {'插座'}, rng=random.Random(0))
    picks = {blindbox_service.choose_from_ranked(ranked, cafe_tags, {'插座'}, rng=random.Random(s))[0]['cafe_id']
             for s in range(30)}
    assert 15 not in picks
    assert 5 in picks
    assert 0 <= nov <= 1


# ==========================================
# API
# ==========================================

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.app_context():
        assert db.engine.url.drivername.startswith('sqlite')
    with app.test_client() as c:
        with app.app_context():
            db.create_all()
            _seed()
        with c.session_transaction() as s:
            s['user_email'] = 'passport@example.test'
        yield c
        with app.app_context():
            db.session.remove()
            db.drop_all()


def _seed():
    from models import Cafes, Tags, User
    db.session.add(User(email='passport@example.test', name='P', picture=''))
    work = Tags(tag_name='插座充足')
    old = Tags(tag_name='老宅復古')
    db.session.add_all([work, old])
    for i in range(1, 7):
        cafe = Cafes(id=i, name=f'店{i}', address='970花蓮縣花蓮市中正路1號', cost='$200-400')
        cafe.tags = [work] if i <= 3 else [old]
        db.session.add(cafe)
    db.session.commit()


def _toggle(client, cafe_id, kind='visited', source='explore'):
    return client.post('/api/user/shop_state', json={'cafe_id': cafe_id, 'type': kind, 'source': source}).get_json()


def test_visit_returns_new_badge_and_logs_event(client):
    from models import ShopStateEvent, UserShopState
    first = _toggle(client, 1)
    assert first['success'] and first['visited']
    assert [b['id'] for b in first['new_badges']] == ['first_stamp']
    again = _toggle(client, 2, source='chat')
    assert again['new_badges'] == []  # 已經有的徽章不會再報一次
    with app.app_context():
        events = ShopStateEvent.query.order_by(ShopStateEvent.id).all()
        assert [(e.cafe_id, e.action, e.source) for e in events] == [(1, 'visit', 'explore'), (2, 'visit', 'chat')]
        assert UserShopState.query.filter_by(cafe_id=1).first().visited_at is not None


def test_unvisit_clears_date_and_unknown_source_is_recorded_as_unknown(client):
    from models import ShopStateEvent, UserShopState
    _toggle(client, 1)
    res = _toggle(client, 1, source='<script>')
    assert res['visited'] is False
    with app.app_context():
        assert UserShopState.query.filter_by(cafe_id=1).first().visited_at is None
        assert ShopStateEvent.query.order_by(ShopStateEvent.id.desc()).first().source == 'unknown'


def test_shop_state_rejects_missing_cafe(client):
    r = client.post('/api/user/shop_state', json={'cafe_id': 999, 'type': 'visited'})
    assert r.status_code == 404


def test_passport_payload(client):
    _toggle(client, 1)
    _toggle(client, 2, kind='fav')
    data = client.get('/api/passport').get_json()
    assert data['total_cafes'] == 6 and data['stamp_count'] == 1
    stamped = [b for b in data['book'] if b['stamped']]
    assert [b['cafe_id'] for b in stamped] == [1] and stamped[0]['area'] == '花蓮市'
    assert data['badge_count'] >= 1
    states = client.get('/api/user/shop_states').get_json()
    assert states == {'1': {'fav': False, 'visited': True, 'want': False},
                      '2': {'fav': True, 'visited': False, 'want': False}}


def test_blindbox_hides_cafe_until_opened(client):
    box = client.get('/api/blindbox').get_json()['box']
    assert box['status'] == 'sealed' and 'cafe' not in box
    assert box['hints']['area'] == '花蓮市' and box['rerolls_left'] == 1
    again = client.get('/api/blindbox').get_json()['box']
    assert again['id'] == box['id']  # 同一天只有一盒
    assert box['day_key'] == passport_service.day_key()
    opened = client.post('/api/blindbox/open').get_json()['box']
    assert opened['status'] == 'opened' and opened['cafe']['id']


def test_blindbox_skips_known_cafes(client):
    for cid in (1, 2, 3, 4, 5):
        _toggle(client, cid)
    box = client.get('/api/blindbox').get_json()['box']
    opened = client.post('/api/blindbox/open').get_json()['box']
    assert opened['cafe']['id'] == 6
    assert box['id'] == opened['id']


def test_visiting_the_box_cafe_completes_it_and_unlocks_badge(client):
    client.get('/api/blindbox')
    cafe_id = client.post('/api/blindbox/open').get_json()['box']['cafe']['id']
    res = _toggle(client, cafe_id, source='blindbox')
    assert res['blindbox_completed'] is True
    assert {'first_stamp', 'box_rookie'} <= {b['id'] for b in res['new_badges']}
    data = client.get('/api/blindbox').get_json()
    assert data['box']['status'] == 'completed'
    assert data['history'] == []  # 今天完成的那盒已經顯示在卡片上，不重複列進歷史
    rated = client.post(f"/api/blindbox/{data['box']['id']}/rate", json={'rating': 4, 'comment': '好喝'})
    assert rated.status_code == 200 and rated.get_json()['box']['rating'] == 4
    bad = client.post(f"/api/blindbox/{data['box']['id']}/rate", json={'rating': 9})
    assert bad.status_code == 400
    passport = client.get('/api/passport').get_json()
    assert any(b['via_blindbox'] for b in passport['book'])


def test_reroll_once_per_day_and_records_reason(client):
    from models import BlindBox
    first = client.get('/api/blindbox').get_json()['box']
    r = client.post('/api/blindbox/reroll', json={'reason': 'too_far'})
    second = r.get_json()['box']
    assert r.status_code == 200 and second['id'] != first['id'] and second['rerolls_left'] == 0
    assert client.post('/api/blindbox/reroll', json={'reason': 'too_far'}).status_code == 400
    with app.app_context():
        old = db.session.get(BlindBox, first['id'])
        assert old.status == 'skipped' and old.skip_reason == 'too_far'
        assert db.session.get(BlindBox, second['id']).cafe_id != old.cafe_id
    hist = client.get('/api/blindbox').get_json()['history']
    assert hist[0]['status'] == 'skipped' and hist[0]['cafe_name'] is None  # 沒拆就不公開


def _age_box(box_id, days):
    from models import BlindBox
    with app.app_context():
        box = db.session.get(BlindBox, box_id)
        box.day_key = passport_service.day_key(passport_service.naive_utc(get_utc_now()) - timedelta(days=days))
        db.session.commit()


def test_unopened_box_expires_next_day_and_a_new_box_is_drawn(client):
    from models import BlindBox
    old_id = client.get('/api/blindbox').get_json()['box']['id']
    _age_box(old_id, 1)
    new = client.get('/api/blindbox').get_json()['box']
    assert new['id'] != old_id and new['status'] == 'sealed'
    with app.app_context():
        assert db.session.get(BlindBox, old_id).status == 'expired'


def test_opened_box_waits_a_week_and_can_still_be_completed(client):
    from models import BlindBox
    client.get('/api/blindbox')
    opened = client.post('/api/blindbox/open').get_json()['box']
    _age_box(opened['id'], 3)
    data = client.get('/api/blindbox').get_json()
    assert data['box']['id'] != opened['id']                      # 今天有新的一盒
    pending = [h for h in data['history'] if h['id'] == opened['id']]
    assert pending and pending[0]['status'] == 'opened'            # 前幾天拆的列成「待去」
    res = _toggle(client, opened['cafe']['id'], source='blindbox')
    assert res['blindbox_completed'] is True
    with app.app_context():
        assert db.session.get(BlindBox, opened['id']).status == 'completed'


def test_opened_box_expires_after_keep_days(client):
    from models import BlindBox
    client.get('/api/blindbox')
    opened = client.post('/api/blindbox/open').get_json()['box']
    _age_box(opened['id'], blindbox_service.OPENED_KEEP_DAYS)
    client.get('/api/blindbox')
    with app.app_context():
        assert db.session.get(BlindBox, opened['id']).status == 'expired'
    assert _toggle(client, opened['cafe']['id'])['blindbox_completed'] is False


# ==========================================
# 想去清單與滑卡
# ==========================================

def _swipe(client, cafe_id, direction):
    return client.post('/api/swipe', json={'cafe_id': cafe_id, 'direction': direction})


def test_deck_is_random_and_hides_visited_and_wanted(client):
    _toggle(client, 1)
    _toggle(client, 2, kind='want', source='passport')
    deck = client.get('/api/swipe/deck').get_json()
    ids = {c['cafe_id'] for c in deck['cards']}
    assert ids == {3, 4, 5, 6} and deck['remaining'] == 4 and deck['passed'] == 0
    card = deck['cards'][0]
    assert {'name', 'image_url', 'area', 'cost', 'tags'} <= set(card)


def test_swipe_right_adds_to_want_list_and_left_is_remembered(client):
    from models import ShopStateEvent
    r = _swipe(client, 3, 'right').get_json()
    assert r['success'] and r['want'] is True
    _swipe(client, 4, 'left')
    deck = client.get('/api/swipe/deck').get_json()
    assert {c['cafe_id'] for c in deck['cards']} == {1, 2, 5, 6} and deck['passed'] == 1
    states = client.get('/api/user/shop_states').get_json()
    assert states['3']['want'] is True and '4' not in states
    passport = client.get('/api/passport').get_json()
    assert [w['cafe_id'] for w in passport['want_list']] == [3]
    assert next(b for b in passport['book'] if b['cafe_id'] == 3)['want'] is True
    with app.app_context():
        assert [(e.cafe_id, e.action, e.source) for e in ShopStateEvent.query.order_by(ShopStateEvent.id)] == \
            [(3, 'want', 'swipe'), (4, 'pass', 'swipe')]


def test_remove_from_want_list(client):
    _swipe(client, 3, 'right')
    res = _toggle(client, 3, kind='want', source='passport')
    assert res['want'] is False
    assert client.get('/api/passport').get_json()['want_list'] == []


def test_undo_puts_the_card_back(client):
    _swipe(client, 3, 'left')
    _swipe(client, 5, 'right')
    undone = client.post('/api/swipe/undo').get_json()
    assert undone['card']['cafe_id'] == 5 and undone['direction'] == 'right'
    assert client.get('/api/user/shop_states').get_json().get('5', {}).get('want') is not True
    assert client.post('/api/swipe/undo').get_json()['card']['cafe_id'] == 3
    assert client.post('/api/swipe/undo').status_code == 400


def test_reset_brings_passed_cafes_back(client):
    for cid in range(1, 7):
        _swipe(client, cid, 'left' if cid % 2 else 'right')
    assert client.get('/api/swipe/deck').get_json()['remaining'] == 0
    assert client.post('/api/swipe/reset').get_json()['restored'] == 3
    assert {c['cafe_id'] for c in client.get('/api/swipe/deck').get_json()['cards']} == {1, 3, 5}


def test_swipe_validates_input(client):
    assert _swipe(client, 3, 'up').status_code == 400
    assert _swipe(client, '3', 'right').status_code == 400
    assert _swipe(client, True, 'right').status_code == 400
    assert _swipe(client, 999, 'right').status_code == 400


def test_blindbox_never_picks_a_cafe_swiped_left(client):
    for cid in (1, 2, 3, 4, 5):
        _swipe(client, cid, 'left')
    client.get('/api/blindbox')
    assert client.post('/api/blindbox/open').get_json()['box']['cafe']['id'] == 6


def test_blindbox_never_picks_a_cafe_closed_all_week(client):
    """一週七天都公休（多半已歇業）的店抽到也去不了，連輪完放寬時也不能出現。"""
    from models.cafe import OperatingHours
    with app.app_context():
        db.session.add_all([OperatingHours(cafe_id=6, day_of_week=d, is_closed=1) for d in range(7)])
        db.session.commit()
    for cid in (1, 2, 3, 4):
        _swipe(client, cid, 'left')
    for _ in range(5):
        with app.app_context():
            pick = blindbox_service.pick_cafe(
                user_id=1, rng=random.Random(_))
        assert pick['cafe_id'] == 5


def test_wanted_cafe_can_still_be_drawn(client):
    for cid in (1, 2, 3, 4, 5):
        _toggle(client, cid)
    _swipe(client, 6, 'right')
    client.get('/api/blindbox')
    assert client.post('/api/blindbox/open').get_json()['box']['cafe']['id'] == 6


def test_delete_account_removes_passport_data(client):
    from models import BlindBox, CafeSwipe, ShopStateEvent
    client.get('/api/blindbox')
    _toggle(client, 1)
    _swipe(client, 2, 'left')
    assert client.post('/api/user/delete').get_json()['success']
    with app.app_context():
        assert ShopStateEvent.query.count() == 0 and BlindBox.query.count() == 0
        assert CafeSwipe.query.count() == 0


def test_requires_login():
    app.config['TESTING'] = True
    with app.test_client() as c:
        assert c.get('/api/passport').status_code == 401
        assert c.get('/api/blindbox').status_code == 401
        assert c.get('/api/swipe/deck').status_code == 401
        assert c.post('/api/swipe', json={'cafe_id': 1, 'direction': 'right'}).status_code == 401
