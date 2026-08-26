def test_index_requires_login(client):
    response = client.get('/')
    assert response.status_code == 302  # Redirect to login

def test_test_route(client):
    response = client.get('/test')
    assert response.status_code == 200
    assert b'Flask funktioniert!' in response.data

def test_login_renders_local_login_form(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert 'Benutzername' in response.get_data(as_text=True)
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
