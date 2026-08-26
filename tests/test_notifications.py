def test_registration_sends_important_pushover_notification(client, app, monkeypatch, csrf_token):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return type('Response', (), {'ok': True, 'status_code': 200})()

    monkeypatch.setattr('app.notifications.requests.post', fake_post)
    response = client.post('/register', data={
        'csrf_token': csrf_token('/register'),
        'first_name': 'New',
        'last_name': 'Coach',
        'username': 'new-coach',
        'password': 'a-strong-password',
        'password_confirmation': 'a-strong-password',
    })
    assert response.status_code == 302
    assert calls[0][0] == 'https://pushover.test/messages.json'
    assert calls[0][1]['data']['priority'] == 1
    assert calls[0][1]['data']['retry'] == 300


def test_login_sends_normal_pushover_notification(client, app, login_as, monkeypatch, csrf_token):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs['data'])
        return type('Response', (), {'ok': True, 'status_code': 200})()

    monkeypatch.setattr('app.notifications.requests.post', fake_post)
    login_as(username='login-coach', password='adminpw', role='user')
    response = client.post('/login', data={
        'csrf_token': csrf_token('/login'),
        'username': 'login-coach',
        'password': 'adminpw',
    }, follow_redirects=False)
    assert response.status_code == 302
    assert calls[0]['priority'] == 0
    assert 'login-coach' in calls[0]['message']
