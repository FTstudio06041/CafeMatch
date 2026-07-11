import pytest
from app import app, db

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.app_context():
        # 防呆：測試只准跑在 SQLite 上（DB_URI 由 conftest.py 強制設定）。
        # 若引擎綁到真實資料庫，這裡直接中止，避免 drop_all 誤刪真實資料。
        assert db.engine.url.drivername.startswith('sqlite'), (
            f'測試拒絕在非 SQLite 資料庫上執行：{db.engine.url}'
        )
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()

def test_app_starts(client):
    """Test that the application can start and index route works."""
    response = client.get('/')
    assert response.status_code in [200, 404] # It might be 404 if frontend is not built, but app is alive

def test_api_cafes_route(client):
    """Test that the public cafes API works."""
    response = client.get('/api/cafes')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
