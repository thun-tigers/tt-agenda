def test_index_requires_login(client):
    response = client.get('/')
    assert response.status_code == 302  # Redirect to login

def test_test_route(client):
    response = client.get('/test')
    assert response.status_code == 200
    assert b'Flask funktioniert!' in response.data

def test_login_redirects_to_auth(client, csrf_token):
    token = csrf_token('/login')
    response = client.post('/login', data={'csrf_token': token})
    assert response.status_code == 302  # Redirect after login
    assert response.location == 'http://localhost:8085/?next_service=tt-agenda'

def test_login_requires_csrf(client):
    response = client.post('/login', data={'username': 'test', 'password': 'test'})
    assert response.status_code == 400
