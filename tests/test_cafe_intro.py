"""首頁「請 AI 介紹這家店」：獨立路徑，只餵那一家店的資料，不進需求狀態機。"""

import json

import pytest

from app import app, db
from extensions import limiter


@pytest.fixture
def client(monkeypatch):
    app.config['TESTING'] = True
    with app.app_context():
        assert db.engine.url.drivername.startswith('sqlite')
    limiter.enabled = False
    from services import chat_pipeline_service as pipeline
    monkeypatch.setattr(pipeline, 'check_health', lambda: True)
    monkeypatch.setattr(pipeline, 'get_selected_model', lambda: 'test-model')
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            from models import Cafes
            db.session.add(Cafes(id=7, name='吉野咖啡', address='花蓮市成功街 1 號', cost='$200-400', phone='03-1234567'))
            db.session.commit()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()
    limiter.enabled = True


def _events(resp):
    return [json.loads(line) for line in resp.get_data(as_text=True).splitlines() if line.strip()]


def test_intro_feeds_only_that_cafe_and_skips_the_guide(client, monkeypatch):
    from services import ai_service, preference_service

    captured = {}

    def fake_stream(**kwargs):
        captured.update(kwargs)
        yield json.dumps({'response': '吉野咖啡是老屋改建的店。'}, ensure_ascii=False) + '\n'
        yield json.dumps({'response': '', 'done': True}) + '\n'

    def must_not_extract(*a, **kw):
        raise AssertionError('介紹店家不該萃取偏好')

    monkeypatch.setattr(ai_service, 'stream_generate', fake_stream)
    monkeypatch.setattr(preference_service, 'extract_preferences', must_not_extract)

    events = _events(client.post('/api/chat', json={'message': '請幫我介紹「吉野咖啡」', 'history': [], 'intro_cafe_id': 7}))

    assert not any('cafes' in e for e in events), '介紹不是推薦，不該出卡片'
    assert ''.join(e.get('response', '') for e in events) == '吉野咖啡是老屋改建的店。'
    assert '吉野咖啡' in captured['cafe_context'] and '花蓮市成功街 1 號' in captured['cafe_context']
    assert '03-1234567' in captured['cafe_context']
    assert '嚴禁編造' in captured['prompt_text']


def test_unknown_cafe_gets_a_fixed_reply_without_calling_the_model(client, monkeypatch):
    from services import ai_service

    def boom(**kwargs):
        raise AssertionError('找不到店就不該呼叫模型')

    monkeypatch.setattr(ai_service, 'stream_generate', boom)
    events = _events(client.post('/api/chat', json={'message': '介紹一下', 'history': [], 'intro_cafe_id': 999}))
    assert '找不到這家店' in ''.join(e.get('response', '') for e in events)
    assert events[-1].get('done') is True
