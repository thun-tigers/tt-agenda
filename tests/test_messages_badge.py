def test_navigation_shows_pending_messages_badge(client, app, monkeypatch):
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
        user.auth_user_id = 123
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        auth_user_id = user.auth_user_id
        username = user.username
        role = user.role

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['auth_user_id'] = auth_user_id
        sess['username'] = username
        sess['user_role'] = role

    response = client.get('/')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'bg-red-500 text-white text-[9px] font-bold' in html
    assert '>3<' in html
