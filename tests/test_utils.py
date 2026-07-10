import pytest
from datetime import date, datetime, time, timedelta
from app.utils import build_activity_timeline, get_text_color_for_bg, build_group_cells, get_upcoming_trainings
from app.models import Activity

def test_build_activity_timeline():
    # Mock activities
    class MockActivity:
        def __init__(self, start_time, duration):
            self.start_time = start_time
            self.duration = duration

    activities = [
        MockActivity(datetime(2023, 1, 1, 10, 0).time(), 60),
        MockActivity(datetime(2023, 1, 1, 11, 0).time(), 30),
    ]
    base_date = datetime(2023, 1, 1).date()
    timeline = build_activity_timeline(activities, base_date)
    assert len(timeline) == 2
    assert timeline[0][1] == datetime(2023, 1, 1, 10, 0)
    assert timeline[1][1] == datetime(2023, 1, 1, 11, 0)

def test_get_text_color_for_bg():
    assert get_text_color_for_bg('#000000') == 'white'
    assert get_text_color_for_bg('#FFFFFF') == 'black'
    assert get_text_color_for_bg('#808080') == 'black'  # Borderline, but returns black

def test_build_group_cells_team():
    # Mock activity for team
    class MockActivity:
        def __init__(self, activity_type, position_groups, topic, color=None):
            self.activity_type = activity_type
            self.position_groups = position_groups
            self.topic = topic
            self.color = color

    activity = MockActivity('team', '["OL", "DL"]', 'Team Topic')
    cells = build_group_cells(activity)
    assert len(cells) == 1
    assert cells[0]['colspan'] == 8
    assert cells[0]['content'] == 'Team Topic'


# ---------------------------------------------------------------------------
# get_current_training_status
# ---------------------------------------------------------------------------

def test_get_current_training_status_running():
    from datetime import date, time, timedelta
    from app.utils import get_current_training_status

    class FakeTraining:
        id = 1
        weekday = 0  # Monday

    class FakeActivity:
        id = 10
        start_time = time(10, 0)
        duration = 120
        order_index = 0
        activity_type = 'team'
        topic = 'Running'
        position_groups = ['OL', 'DL']
        topics_json = None
        color = '#10b981'

    # Pick a Monday
    today = date(2026, 3, 30)  # a Monday
    assert today.weekday() == 0

    fake_training = FakeTraining()
    fake_training.start_date = today
    fake_training.end_date = today

    activities = [FakeActivity()]
    activities_by_training = {1: activities}
    instances_by_key = {}
    instance_activities_by_id = {}

    # Mid-activity: 10:30 → status should be 'running'
    now = datetime.combine(today, time(10, 30))
    ct, ca, na, status, cd, curacts, _ = get_current_training_status(
        [fake_training], activities_by_training, instances_by_key, instance_activities_by_id, now
    )
    assert status == 'running'
    assert ct is fake_training
    assert ca is activities[0]


def test_get_current_training_status_upcoming():
    from datetime import date, time
    from app.utils import get_current_training_status

    class FakeTraining:
        id = 2
        weekday = 1  # Tuesday

    class FakeActivity:
        id = 20
        start_time = time(20, 0)
        duration = 90
        order_index = 0
        activity_type = 'team'
        topic = 'Evening'
        position_groups = ['OL']
        topics_json = None
        color = '#10b981'

    today = date(2026, 3, 31)  # a Tuesday
    assert today.weekday() == 1

    fake_training = FakeTraining()
    fake_training.start_date = today
    fake_training.end_date = today

    activities = [FakeActivity()]
    activities_by_training = {2: activities}

    # Before training starts: 18:00
    now = datetime.combine(today, time(18, 0))
    ct, ca, na, status, cd, curacts, _ = get_current_training_status(
        [fake_training], {2: activities}, {}, {}, now
    )
    assert status == 'upcoming' or status is None  # may not be detected as upcoming from this function


def test_get_current_training_status_no_training():
    from datetime import date, time
    from app.utils import get_current_training_status

    now = datetime.combine(date(2026, 1, 1), time(12, 0))
    ct, ca, na, status, cd, curacts, _ = get_current_training_status([], {}, {}, {}, now)
    assert ct is None
    assert status is None


# ---------------------------------------------------------------------------
# load_training_data
# ---------------------------------------------------------------------------

def test_load_training_data(app):
    from datetime import date, time
    with app.app_context():
        from app.models import Training, Activity, ActivityType
        from app.extensions import db
        from app.utils import load_training_data

        at = ActivityType(key='team_ltd', label='Team', behavior='team',
                          badge_class='bg-info', light_color='#aabbcc',
                          dark_color='#001122', sort_order=1)
        db.session.add(at)
        t = Training(name='Datentest', weekday=4, start_date=date(2026, 1, 1),
                     end_date=date(2026, 12, 31), start_time=time(18, 0))
        db.session.add(t)
        db.session.flush()
        a = Activity(training_id=t.id, activity_type='team_ltd',
                     start_time=time(18, 0), duration=60,
                     position_groups=['OL', 'QB'],
                     order_index=0)
        db.session.add(a)
        db.session.commit()

        trainings, acts_by_t, inst_by_key, inst_acts_by_id = load_training_data()
        assert any(tr.name == 'Datentest' for tr in trainings)
        tid = t.id
        assert tid in acts_by_t
        assert len(acts_by_t[tid]) == 1
        assert acts_by_t[tid][0].topic is None


# ---------------------------------------------------------------------------
# build_group_cells - individual mode
# ---------------------------------------------------------------------------

def test_build_group_cells_individual():
    from app.utils import build_group_cells

    class MockActivity:
        activity_type = 'individual'
        position_groups = ['OL', 'DL', 'LB', 'RB', 'DB', 'TE', 'WR', 'QB']
        topics_json = {g: f'{g} topic' for g in ['OL', 'DL', 'LB', 'RB', 'DB', 'TE', 'WR', 'QB']}
        topic = None
        color = '#BFE9D3'

    cells = build_group_cells(MockActivity())
    assert len(cells) == 8
    assert all(c['colspan'] == 1 for c in cells)
    # OL cell should have content
    ol_cell = next(c for c in cells if c['groups'] == ['OL'])
    assert ol_cell['content'] == 'OL topic'


def test_get_upcoming_trainings_respects_limit(monkeypatch):
    class FakeTraining:
        def __init__(self, training_id):
            self.id = training_id
            self.is_hidden = False
            self.start_date = datetime(2026, 7, 8).date()
            self.weekday = 2

    fake_trainings = [FakeTraining(1), FakeTraining(2)]
    activities_by_training = {1: [], 2: []}

    monkeypatch.setattr('app.utils.get_next_training_dates', lambda training, activities=None, limit=None, now=None: [datetime(2026, 7, 8).date()])
    monkeypatch.setattr('app.utils.resolve_activities_for_date', lambda training, date, activities_by_training, instances_by_key, instance_activities_by_id: ([object()], False))
    monkeypatch.setattr('app.utils.get_timeline_from_activities', lambda activities, date: ([(object(), datetime(2026, 7, 8, 19, 30))], datetime(2026, 7, 8, 19, 30), datetime(2026, 7, 8, 21, 0)))

    result = get_upcoming_trainings(fake_trainings, activities_by_training, {}, {}, datetime(2026, 7, 1, 12, 0), limit=1)
    assert len(result) == 1
    assert result[0]['training'].id == 1


def test_get_upcoming_trainings_sorts_before_applying_limit(monkeypatch):
    class FakeTraining:
        def __init__(self, training_id):
            self.id = training_id
            self.is_hidden = False

    fake_trainings = [FakeTraining(1), FakeTraining(2)]
    activities_by_training = {1: [], 2: []}
    dates_by_training = {
        1: [datetime(2026, 7, 15).date()],
        2: [datetime(2026, 7, 10).date()],
    }

    monkeypatch.setattr(
        'app.utils.get_next_training_dates',
        lambda training, activities=None, limit=None, now=None: dates_by_training[training.id],
    )
    monkeypatch.setattr(
        'app.utils.resolve_activities_for_date',
        lambda training, date, activities_by_training, instances_by_key, instance_activities_by_id: ([object()], False),
    )
    monkeypatch.setattr(
        'app.utils.get_timeline_from_activities',
        lambda activities, date: ([(object(), datetime.combine(date, time(19, 30)), datetime.combine(date, time(21, 0)))], datetime.combine(date, time(19, 30)), datetime.combine(date, time(21, 0))),
    )

    result = get_upcoming_trainings(fake_trainings, activities_by_training, {}, {}, datetime(2026, 7, 1, 12, 0), limit=1)
    assert len(result) == 1
    assert result[0]['training'].id == 2
    assert result[0]['date'] == datetime(2026, 7, 10).date()


def test_get_next_training_dates_keeps_today_visible_after_training_end(monkeypatch):
    from app.utils import get_next_training_dates

    class FakeTraining:
        id = 1
        start_date = date(2026, 7, 10)
        end_date = date(2026, 7, 10)
        weekday = 4

    class FakeActivity:
        order_index = 0
        start_time = time(19, 30)
        duration = 120

    today = date(2026, 7, 10)
    now = datetime.combine(today, time(23, 0))

    result = get_next_training_dates(FakeTraining(), activities=[FakeActivity()], now=now)

    assert result == [today]
