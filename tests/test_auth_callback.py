"""
Google OAuth 回呼失敗時不能回 500，要導回首頁並帶 ?login_error=1。

重現情境：從 www.cafematch.net 開始登入，但回呼網址是 cafematch.net，
session 裡沒有對應的 state → Authlib 丟 MismatchingStateError。
"""
import os

os.environ.setdefault('SECRET_KEY', 'test_key')
os.environ.setdefault('FLASK_ENV', 'development')

from app import app  # noqa: E402


def _client():
    app.config['TESTING'] = True
    return app.test_client()


def test_callback_with_mismatched_state_redirects_instead_of_500():
    resp = _client().get('/auth/callback?state=fake&code=fake')
    assert resp.status_code == 302
    assert 'login_error=1' in resp.headers['Location']


def test_callback_when_user_cancels_on_google_redirects_instead_of_500():
    resp = _client().get('/auth/callback?error=access_denied&state=fake')
    assert resp.status_code == 302
    assert 'login_error=1' in resp.headers['Location']
