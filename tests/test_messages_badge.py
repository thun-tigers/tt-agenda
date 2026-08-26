def test_navigation_has_no_external_messages_dependency(client, app, monkeypatch):
    from app.extensions import db
    from app.models import User

    class FakeResponse:
        status_code = 200

        def json(self):
            return {'pending_messages_count': 3}

    def fake_get(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr('app.requests.get', fake_get)

    with app.app_context():
        user = User(username='agenda-user', role='user')
        user.set_password('secret')
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        username = user.username
        role = user.role

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = username
        sess['user_role'] = role

    response = client.get('/')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'tt-planning' in html
