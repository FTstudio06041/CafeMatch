"""首頁改版的後端：營業時間判讀、店家資料、評論即社群、現況回報、首頁推薦。"""

from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest

from app import app, db
from extensions import limiter
from services.cafe_hours import TAIPEI_TZ, describe_day, is_open_at, today_summary, weekly_hours


# ---------- 營業時間（純函式） ----------

def _row(day, open_t=None, close_t=None, closed=0):
    return SimpleNamespace(day_of_week=day, open_time=open_t, close_time=close_t, is_closed=closed)


def _at(day, hour, minute=0):
    """2026-10-12 是週一；day 1~7 = 週一~週日。"""
    return datetime(2026, 10, 11 + day, hour, minute, tzinfo=TAIPEI_TZ)


def test_split_sessions_are_listed_in_order():
    rows = [_row(1, time(17), time(21)), _row(1, time(11), time(14))]
    assert describe_day(rows, 1) == '11:00–14:00、17:00–21:00'
    assert is_open_at(rows, _at(1, 15)) is False
    assert is_open_at(rows, _at(1, 18)) is True


def test_closed_day_and_unknown_day():
    rows = [_row(1, time(9), time(18)), _row(2, closed=1)]
    assert describe_day(rows, 2) == '公休'
    assert describe_day(rows, 3) is None
    assert today_summary(rows, _at(2, 10)) == {'today_hours': '今日公休', 'is_open_now': False}
    # 當天與前一天都沒資料 → 無法判斷，不能說成「休息中」
    assert is_open_at(rows, _at(4, 10)) is None


def test_after_midnight_counts_as_previous_day_session():
    rows = [_row(1, time(18), time(2)), _row(2, closed=1)]
    assert is_open_at(rows, _at(1, 23)) is True
    assert is_open_at(rows, _at(2, 1)) is True       # 週一的時段延續到週二凌晨
    assert is_open_at(rows, _at(2, 3)) is False


def test_timedelta_values_from_mysql_are_understood():
    rows = [_row(5, timedelta(hours=11), timedelta(hours=21))]
    assert describe_day(rows, 5) == '11:00–21:00'
    assert weekly_hours(rows) == [{'day': 5, 'label': '週五', 'text': '11:00–21:00'}]


# ---------- API ----------

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.app_context():
        assert db.engine.url.drivername.startswith('sqlite')
    limiter.enabled = False
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            _seed()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()
    limiter.enabled = True


def _seed():
    from models import Cafes, User
    db.session.add_all([
        Cafes(id=1, name='海邊咖啡', address='花蓮市海岸路 1 號', google_place_id='pid-1', lat=23.98, lng=121.6),
        Cafes(id=2, name='巷弄咖啡', address='花蓮市巷弄 2 號'),
        User(id=1, email='a@example.test', name='小明'),
        User(id=2, email='b@example.test', name='小華'),
        User(id=3, email='admin@example.test', name='管理員', is_admin=True),
    ])
    db.session.commit()


def _login(client, email):
    with client.session_transaction() as session:
        session['user_email'] = email


def test_cafes_payload_has_map_and_rating_fields(client):
    data = client.get('/api/cafes').get_json()
    first = next(c for c in data if c['id'] == 1)
    assert (first['lat'], first['lng']) == (23.98, 121.6)
    assert 'query_place_id=pid-1' in first['map_url']
    for key in ('tag_list', 'today_hours', 'is_open_now', 'weekly_hours',
                'google_rating', 'google_review_count', 'rating', 'review_count', 'report_count'):
        assert key in first


def test_review_requires_login(client):
    assert client.post('/api/cafes/1/reviews', json={'rating': 5}).status_code == 401


@pytest.mark.parametrize('rating', [0, 6, True, 4.5, 'abc', None])
def test_invalid_rating_is_rejected(client, rating):
    _login(client, 'a@example.test')
    resp = client.post('/api/cafes/1/reviews', json={'rating': rating, 'content': 'x'})
    assert resp.status_code == 400


def test_one_review_per_user_per_cafe(client):
    _login(client, 'a@example.test')
    first = client.post('/api/cafes/1/reviews', json={'rating': 4, 'content': '插座很多'}).get_json()
    again = client.post('/api/cafes/1/reviews', json={'rating': 2, 'content': '改觀了'}).get_json()
    assert first['review']['id'] == again['review']['id']
    assert again['review']['rating'] == 2
    assert again['review']['updated_at']
    assert again['summary']['count'] == 1


def test_list_separates_my_review_and_hides_email(client):
    _login(client, 'a@example.test')
    client.post('/api/cafes/1/reviews', json={'rating': 5, 'content': '我的'})
    _login(client, 'b@example.test')
    client.post('/api/cafes/1/reviews', json={'rating': 3, 'content': '別人的'})

    data = client.get('/api/cafes/1/reviews').get_json()
    assert data['my_review']['content'] == '別人的'
    assert [r['content'] for r in data['reviews']] == ['我的']
    assert data['summary'] == {'average': 4.0, 'count': 2,
                               'distribution': {'1': 0, '2': 0, '3': 1, '4': 0, '5': 1}}
    assert 'email' not in str(data)


def test_likes_and_comments_on_reviews(client):
    _login(client, 'a@example.test')
    review_id = client.post('/api/cafes/1/reviews', json={'rating': 5}).get_json()['review']['id']
    _login(client, 'b@example.test')
    assert client.post(f'/api/reviews/{review_id}/like').get_json()['like_count'] == 1
    assert client.post(f'/api/reviews/{review_id}/like').get_json()['liked'] is False

    comment = client.post(f'/api/reviews/{review_id}/comments', json={'content': '週末人多'}).get_json()['comment']
    comments = client.get(f'/api/reviews/{review_id}/comments').get_json()['comments']
    assert [c['content'] for c in comments] == ['週末人多']
    _login(client, 'a@example.test')
    assert client.delete(f'/api/reviews/{review_id}/comments/{comment["id"]}').status_code == 403
    _login(client, 'b@example.test')
    assert client.delete(f'/api/reviews/{review_id}/comments/{comment["id"]}').status_code == 200


def test_only_author_or_admin_can_delete_review(client):
    _login(client, 'a@example.test')
    review_id = client.post('/api/cafes/1/reviews', json={'rating': 5}).get_json()['review']['id']
    _login(client, 'b@example.test')
    assert client.delete(f'/api/reviews/{review_id}').status_code == 403
    _login(client, 'admin@example.test')
    assert client.delete(f'/api/reviews/{review_id}').status_code == 200
    assert client.get('/api/cafes/1/reviews').get_json()['summary']['count'] == 0


def test_cafe_rating_reflects_platform_reviews(client):
    _login(client, 'a@example.test')
    client.post('/api/cafes/2/reviews', json={'rating': 4})
    cafe = next(c for c in client.get('/api/cafes').get_json() if c['id'] == 2)
    assert (cafe['rating'], cafe['review_count']) == (4.0, 1)


def test_report_is_one_per_user_and_expires(client):
    from config.settings import get_utc_now
    from models import CommunityNote

    _login(client, 'a@example.test')
    client.post('/api/cafes/1/reports', json={'content': '現在人很多'})
    client.post('/api/cafes/1/reports', json={'content': '還有空位'})
    reports = client.get('/api/cafes/1/reports').get_json()['reports']
    assert [r['content'] for r in reports] == ['還有空位']

    with app.app_context():
        note = CommunityNote.query.filter_by(cafe_id=1).first()
        note.created_at = get_utc_now() - timedelta(hours=25)
        db.session.commit()
    assert client.get('/api/cafes/1/reports').get_json()['reports'] == []


def test_report_confirm_and_cafe_badge(client):
    _login(client, 'a@example.test')
    report_id = client.post('/api/cafes/1/reports', json={'content': '很安靜'}).get_json()['report']['id']
    _login(client, 'b@example.test')
    assert client.post(f'/api/reports/{report_id}/confirm').get_json()['confirm_count'] == 1
    assert client.delete(f'/api/reports/{report_id}').status_code == 403
    cafe = next(c for c in client.get('/api/cafes').get_json() if c['id'] == 1)
    assert cafe['report_count'] == 1


def test_cafe_reports_do_not_leak_into_global_notes(client):
    from services.note_service import NoteService

    _login(client, 'a@example.test')
    client.post('/api/cafes/1/reports', json={'content': '店家回報'})
    with app.app_context():
        assert NoteService.get_notes() == []
        from models import User
        user = db.session.get(User, 1)
        NoteService.create_or_update_note(user, '全站便利貼', 0)
    # 舊便利貼「每人一張」的更新邏輯不能把店家回報蓋掉
    assert client.get('/api/cafes/1/reports').get_json()['reports'][0]['content'] == '店家回報'


# ---------- 首頁推薦 ----------

def test_recommended_falls_back_to_popular_without_scores(client):
    data = client.get('/api/cafes/recommended').get_json()
    assert data['basis'] == 'popular'
    assert {i['cafe_id'] for i in data['items']} == {1, 2}


def test_recommended_uses_gnn_for_guest_scores(client, monkeypatch):
    from services import gnn_recommender
    from services.cache_service import cache

    cache.cache.clear()
    monkeypatch.setattr(gnn_recommender, 'recommend_by_scores',
                        lambda scores, **kw: [{'cafe_id': 2}])
    data = client.get('/api/cafes/recommended?work=10&env=8&social=2&taste=4&cp=6').get_json()
    assert data['basis'] == 'quiz'
    assert data['items'][0] == {'cafe_id': 2, 'reason': 'quiz'}
    assert data['items'][1] == {'cafe_id': 1, 'reason': 'popular'}


def test_recommended_survives_gnn_failure(client, monkeypatch):
    from services import gnn_recommender
    from services.cache_service import cache

    cache.cache.clear()

    def boom(*a, **kw):
        raise gnn_recommender.GnnUnavailable('no torch')

    monkeypatch.setattr(gnn_recommender, 'recommend_by_scores', boom)
    data = client.get('/api/cafes/recommended?work=1&env=1&social=1&taste=1&cp=1').get_json()
    assert data['basis'] == 'popular'


@pytest.mark.parametrize('raw, ok', [
    ({'work': 1, 'env': 2, 'social': 3, 'taste': 4, 'cp': 5}, True),
    ({'work': 1, 'env': 2, 'social': 3, 'taste': 4}, False),
    ({'work': -1, 'env': 2, 'social': 3, 'taste': 4, 'cp': 5}, False),
    ({'work': 'x', 'env': 2, 'social': 3, 'taste': 4, 'cp': 5}, False),
    ({'work': 0, 'env': 0, 'social': 0, 'taste': 0, 'cp': 0}, False),
])
def test_parse_scores(raw, ok):
    from services.home_recommend_service import parse_scores
    assert (parse_scores(raw) is not None) is ok


def test_popular_ranking_prefers_many_reviews(monkeypatch):
    from datetime import date
    from services import home_recommend_service as svc

    monkeypatch.setattr(svc, 'google_review_stats', lambda: {1: (4.9, 20), 2: (4.7, 2000), 3: (4.0, 500)})
    monkeypatch.setattr(svc, 'POPULAR_POOL', 0)  # 關掉每日輪替，只看排序
    assert svc.popular_cafe_ids([1, 2, 3], limit=3, today=date(2026, 10, 15)) == [2, 1, 3]
