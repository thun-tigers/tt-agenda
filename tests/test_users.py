def test_user_list_shows_delete_action_for_other_users(client, app, login_as):
    login_as(username='admin', password='adminpw', role='admin')
    from app.extensions import db
    from app.models import User

    with app.app_context():
        user = User(username='delete-me', role='user')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

    response = client.get('/users/')
    assert response.status_code == 200
    assert '/users/' in response.get_data(as_text=True)
    assert 'delete-me' in response.get_data(as_text=True)
    assert 'Löschen' in response.get_data(as_text=True)


def test_user_cannot_delete_own_account(client, app, login_as, csrf_token):
    login_as(username='self-admin', password='adminpw', role='admin')
    with client.session_transaction() as session:
        user_id = session['user_id']

    response = client.post(
        f'/users/{user_id}/delete',
        data={'csrf_token': csrf_token('/users/')},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert 'eigene Account' in response.get_data(as_text=True)

    with app.app_context():
        from app.models import User
        assert User.query.get(user_id) is not None
