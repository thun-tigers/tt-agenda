def test_logout_requires_post(client):
    response = client.get('/logout')
    assert response.status_code == 405


def test_logout_clears_session(client, csrf_token):
    client.get('/login')
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'logout-user'
        sess['user_role'] = 'user'
    logout_token = csrf_token('/')
    logout_response = client.post('/logout', data={'csrf_token': logout_token})
    assert logout_response.status_code == 302

    with client.session_transaction() as sess:
        assert 'user_id' not in sess
        assert 'username' not in sess
        assert 'user_role' not in sess


def test_registration_rejects_weak_password(client, csrf_token):
    token = csrf_token('/register')
    response = client.post('/register', data={
        'csrf_token': token,
        'first_name': 'Test',
        'last_name': 'User',
        'username': 'weak-user',
        'password': 'short',
        'password_confirmation': 'short',
    })
    assert response.status_code == 200
    assert 'mindestens 12 Zeichen' in response.get_data(as_text=True)


def test_registration_requires_password_confirmation(client, csrf_token):
    token = csrf_token('/register')
    response = client.post('/register', data={
        'csrf_token': token,
        'first_name': 'Test',
        'last_name': 'User',
        'username': 'mismatch-user',
        'password': 'a-strong-password',
        'password_confirmation': 'another-password',
    })
    assert response.status_code == 200
    assert 'stimmen nicht überein' in response.get_data(as_text=True)


def test_registration_creates_pending_user_without_login(client, app, csrf_token):
    response = client.post('/register', data={
        'csrf_token': csrf_token('/register'),
        'first_name': 'Pending',
        'last_name': 'Coach',
        'username': 'pending-coach',
        'password': 'a-strong-password',
        'password_confirmation': 'a-strong-password',
    })
    assert response.status_code == 302
    assert response.location.endswith('/login')

    with app.app_context():
        from app.models import User
        user = User.query.filter_by(username='pending-coach').first()
        assert user.account_status == 'pending'
        assert user.can_login is False
