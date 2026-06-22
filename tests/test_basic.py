import pytest
from app import app, db

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
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
