from datetime import date, time

from app.extensions import db
from app.models import Training, TrainingInstance, ActivityInstance


def test_copy_training_instance_picks_next_free_date(client, app, login_as, csrf_token):
    login_response = login_as(username='admin', password='adminpw', role='admin')
    assert login_response.status_code == 200

    with app.app_context():
        training = Training(
            name='Admin Test',
            weekday=0,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            start_time=time(19, 0),
            is_hidden=False
        )
        db.session.add(training)
        db.session.flush()

        original = TrainingInstance(
            training_id=training.id,
            date=date(2025, 1, 6),
            status='active',
            start_time=time(19, 0)
        )
        blocker = TrainingInstance(
            training_id=training.id,
            date=date(2025, 1, 13),
            status='active',
            start_time=time(19, 0)
        )
        db.session.add(original)
        db.session.add(blocker)
        db.session.flush()

        db.session.add(ActivityInstance(
            training_instance_id=original.id,
            activity_type='team',
            start_time=time(19, 0),
            duration=45,
            position_groups='["OL","DL"]',
            topic='Install',
            order_index=0,
            topics_json=None,
            color='#10b981'
        ))
        db.session.commit()
        original_id = original.id
        training_id = training.id

    token = csrf_token('/admin/trainings')
    response = client.post(f'/training-instance/{original_id}/copy', data={'csrf_token': token})
    assert response.status_code == 302

    with app.app_context():
        instances = TrainingInstance.query.filter_by(training_id=training_id).order_by(TrainingInstance.date.asc()).all()
        assert len(instances) == 3
        copied = instances[-1]
        assert copied.date == date(2025, 1, 20)
        copied_activities = ActivityInstance.query.filter_by(training_instance_id=copied.id).all()
        assert len(copied_activities) == 1
        assert copied_activities[0].topic == 'Install'


def test_copy_training_instance_requires_admin(client, app, csrf_token):
    with app.app_context():
        training = Training(
            name='No Admin',
            weekday=2,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            start_time=time(18, 30),
            is_hidden=False
        )
        db.session.add(training)
        db.session.flush()
        instance = TrainingInstance(
            training_id=training.id,
            date=date(2025, 1, 8),
            status='active',
            start_time=time(18, 30)
        )
        db.session.add(instance)
        db.session.commit()
        instance_id = instance.id

    token = csrf_token('/login')
    response = client.post(f'/training-instance/{instance_id}/copy', data={'csrf_token': token})
    assert response.status_code == 302
    assert '/login' in response.location


def test_admin_trainings_hides_ended_by_default(client, app, login_as):
    login_response = login_as(username='admin2', password='adminpw', role='admin')
    assert login_response.status_code == 200

    with app.app_context():
        active = Training(
            name='ACTIVE TRAINING',
            weekday=2,
            start_date=date(2025, 1, 1),
            end_date=date(2099, 12, 31),
            start_time=time(19, 0),
            is_hidden=False
        )
        ended = Training(
            name='ENDED TRAINING',
            weekday=2,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            start_time=time(19, 0),
            is_hidden=False
        )
        db.session.add(active)
        db.session.add(ended)
        db.session.commit()

    response = client.get('/admin/trainings')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'ACTIVE TRAINING' in body
    assert 'ENDED TRAINING' not in body


def test_admin_trainings_can_show_ended(client, app, login_as):
    login_response = login_as(username='admin3', password='adminpw', role='admin')
    assert login_response.status_code == 200

    with app.app_context():
        ended = Training(
            name='ENDED VISIBLE TRAINING',
            weekday=4,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            start_time=time(18, 0),
            is_hidden=False
        )
        db.session.add(ended)
        db.session.commit()

    response = client.get('/admin/trainings?include_ended=1')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'ENDED VISIBLE TRAINING' in body


# ---------------------------------------------------------------------------
# Training CRUD
# ---------------------------------------------------------------------------

def test_create_training(client, app, login_as, csrf_token):
    login_as(username='crud_admin', password='pw', role='admin')
    token = csrf_token('/training/new')
    resp = client.post('/training/new', data={
        'csrf_token': token,
        'name': 'Neues Training',
        'weekday': '1',
        'start_date': '2026-01-01',
        'end_date': '2026-12-31',
        'start_time': '19:00',
    }, follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        from app.models import Training
        t = Training.query.filter_by(name='Neues Training').first()
        assert t is not None
        assert t.category == 'training'
        assert t.weekday == 1


def test_create_training_validates_dates(client, app, login_as, csrf_token):
    """Enddatum vor Startdatum soll abgelehnt werden."""
    login_as(username='valid_admin', password='pw', role='admin')
    token = csrf_token('/training/new')
    resp = client.post('/training/new', data={
        'csrf_token': token,
        'name': 'Bad Dates',
        'weekday': '0',
        'start_date': '2026-12-31',
        'end_date': '2026-01-01',
        'start_time': '18:00',
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Enddatum' in body or 'liegt' in body

    with app.app_context():
        from app.models import Training
        assert Training.query.filter_by(name='Bad Dates').first() is None


def test_delete_training(client, app, login_as, csrf_token):
    login_as(username='del_admin', password='pw', role='admin')
    from datetime import date, time
    with app.app_context():
        from app.models import Training
        from app.extensions import db
        t = Training(name='ZuLöschen', weekday=3, start_date=date(2026, 1, 1),
                     end_date=date(2026, 12, 31), start_time=time(18, 0))
        db.session.add(t)
        db.session.commit()
        tid = t.id

    token = csrf_token('/admin/trainings')
    resp = client.post(f'/training/{tid}/delete', data={'csrf_token': token},
                       follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        from app.models import Training
        from app.extensions import db
        assert db.session.get(Training, tid) is None


def test_edit_training(client, app, login_as, csrf_token):
    login_as(username='edit_admin', password='pw', role='admin')
    from datetime import date, time
    with app.app_context():
        from app.models import Training
        from app.extensions import db
        t = Training(name='AltName', weekday=0, start_date=date(2026, 1, 1),
                     end_date=date(2026, 12, 31), start_time=time(18, 0))
        db.session.add(t)
        db.session.commit()
        tid = t.id

    token = csrf_token(f'/training/{tid}/edit')
    resp = client.post(f'/training/{tid}/edit', data={
        'csrf_token': token,
        'name': 'NeuerName',
        'weekday': '2',
        'start_date': '2026-01-01',
        'end_date': '2026-12-31',
        'start_time': '20:00',
    }, follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        from app.models import Training
        from app.extensions import db
        t = db.session.get(Training, tid)
        assert t.name == 'NeuerName'
        assert t.weekday == 2


# ---------------------------------------------------------------------------
# Activity CRUD (für versteckte Trainings, da einfachste Route)
# ---------------------------------------------------------------------------

def test_create_and_delete_activity_for_hidden_training(client, app, login_as, csrf_token):
    login_as(username='act_admin', password='pw', role='admin')
    from datetime import date, time
    with app.app_context():
        from app.models import Training, Activity, ActivityType
        from app.extensions import db
        # ActivityType muss existieren
        at = ActivityType(key='team', label='Team', behavior='team',
                          badge_class='bg-info', light_color='#aabbcc',
                          dark_color='#001122', sort_order=1)
        db.session.add(at)
        t = Training(name='HiddenTest', weekday=0, start_date=date(2026, 4, 7),
                     end_date=date(2026, 4, 7), start_time=time(18, 0), is_hidden=True)
        db.session.add(t)
        db.session.commit()
        tid = t.id

    # Aktivität hinzufügen (korrekte Route: /activity/add?training_id=<tid>)
    token = csrf_token(f'/admin/hidden-trainings/{tid}/edit')
    resp = client.post(f'/activity/add?training_id={tid}', data={
        'csrf_token': token,
        'training_id': str(tid),
        'activity_type': 'team',
        'duration': '60',
        'topic': 'Testthema',
        'color': '#10b981',
    }, follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        from app.models import Activity
        acts = Activity.query.filter_by(training_id=tid).all()
        assert len(acts) == 1
        assert acts[0].topic == 'Testthema'
        aid = acts[0].id

    # Aktivität löschen
    token2 = csrf_token(f'/admin/hidden-trainings/{tid}/edit')
    resp2 = client.post(f'/activity/{aid}/delete', data={'csrf_token': token2},
                        follow_redirects=False)
    assert resp2.status_code == 302

    with app.app_context():
        from app.models import Activity
        from app.extensions import db
        assert db.session.get(Activity, aid) is None


# ---------------------------------------------------------------------------
# JSON-Feld-Normalisierung (TypeDecorator)
# ---------------------------------------------------------------------------

def test_json_type_stores_and_reads_list(app):
    """position_groups wird als Liste gespeichert und direkt als Liste gelesen."""
    from datetime import date, time
    with app.app_context():
        from app.models import Training, Activity
        from app.extensions import db
        from app.models import ActivityType
        at = ActivityType(key='team2', label='Team', behavior='team',
                          badge_class='bg-info', light_color='#aabbcc',
                          dark_color='#001122', sort_order=1)
        db.session.add(at)
        t = Training(name='JsonTest', weekday=1, start_date=date(2026, 1, 1),
                     end_date=date(2026, 12, 31), start_time=time(18, 0))
        db.session.add(t)
        db.session.flush()
        a = Activity(training_id=t.id, activity_type='team2',
                     start_time=time(18, 0), duration=60,
                     position_groups=['OL', 'DL'],
                     topics_json={'OL': 'Run Block', 'DL': 'Rush Pass'},
                     order_index=0)
        db.session.add(a)
        db.session.commit()
        aid = a.id

        loaded = db.session.get(Activity, aid)
        assert isinstance(loaded.position_groups, list)
        assert 'OL' in loaded.position_groups
        assert isinstance(loaded.topics_json, dict)
        assert loaded.topics_json.get('OL') == 'Run Block'
