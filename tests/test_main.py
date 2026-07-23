def test_index_requires_login(client):
    response = client.get('/')
    assert response.status_code == 302  # Redirect to login

def test_test_route(client):
    response = client.get('/test')
    assert response.status_code == 200
    assert b'Flask funktioniert!' in response.data

def test_login_redirects_to_auth(client):
    response = client.get('/login')
    assert response.status_code == 302  # Redirect to tt-auth, kein Zwischenschritt
    assert response.location == 'http://localhost:8085/?next_service=tt-agenda'
