from .extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
import json
from sqlalchemy.types import TypeDecorator, Text


class JsonType(TypeDecorator):
    """Speichert Python-Objekte (list/dict) als JSON-String in der Datenbank.
    Bestehende JSON-Strings in der DB werden korrekt deserialisiert.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            # Bereits serialisiert (Rückwärtskompatibilität)
            return value
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if not value:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

class Training(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_code = db.Column(db.String(32), nullable=False, default='SENIORS', index=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(20), nullable=False, default='training', index=True)
    participation_rules_json = db.Column(JsonType, nullable=True, default=dict)
    weekday = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    activities = db.relationship('Activity', backref='training', lazy=True, cascade='all, delete-orphan')
    instances = db.relationship('TrainingInstance', backref='training', lazy=True, cascade='all, delete-orphan')


class AgendaCategory(db.Model):
    __tablename__ = 'agenda_category'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40), unique=True, nullable=False)
    label = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), nullable=False, default='bi-calendar-event')
    badge_class = db.Column(db.String(200), nullable=False, default='bg-slate-100 text-slate-700')
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    attendance_required_for = db.Column(JsonType, nullable=False, default=list)
    attendance_allowed_for = db.Column(JsonType, nullable=False, default=list)
    show_presence_tracking = db.Column(db.Boolean, nullable=False, default=True)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    training_id = db.Column(db.Integer, db.ForeignKey('training.id'), nullable=False)
    activity_type = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    position_groups = db.Column(JsonType, nullable=False, default=list)
    topic = db.Column(db.String(200))
    order_index = db.Column(db.Integer, default=0)
    topics_json = db.Column(JsonType)
    color = db.Column(db.String(7), default='#10b981')

class TrainingInstance(db.Model):
    __table_args__ = (db.UniqueConstraint('training_id', 'date', name='uq_training_instance_date'),)
    id = db.Column(db.Integer, primary_key=True)
    training_id = db.Column(db.Integer, db.ForeignKey('training.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), default='active', nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    activities = db.relationship('ActivityInstance', backref='training_instance', lazy=True, cascade='all, delete-orphan')

class ActivityInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    training_instance_id = db.Column(db.Integer, db.ForeignKey('training_instance.id'), nullable=False)
    activity_type = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    position_groups = db.Column(JsonType, nullable=False, default=list)
    topic = db.Column(db.String(200))
    order_index = db.Column(db.Integer, default=0)
    topics_json = db.Column(JsonType)
    color = db.Column(db.String(7), default='#10b981')

class ActivityType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40), unique=True, nullable=False)
    label = db.Column(db.String(100), nullable=False)
    behavior = db.Column(db.String(20), nullable=False)
    badge_class = db.Column(db.String(50), nullable=False)
    light_color = db.Column(db.String(7), nullable=False, default='#E8E8E8')
    dark_color = db.Column(db.String(7), nullable=False, default='#4A4A4A')
    sort_order = db.Column(db.Integer, default=0, nullable=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    account_status = db.Column(db.String(20), nullable=False, default='active')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    display_name = db.Column(db.String(120))
    email = db.Column(db.String(255))
    profile_complete = db.Column(db.Boolean, nullable=False, default=False)
    memberships_json = db.Column(JsonType, nullable=False, default=list)
    position = db.Column(db.String(40))
    phone = db.Column(db.String(40))
    notes = db.Column(db.Text)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return ' '.join(part for part in (self.first_name, self.last_name) if part) or self.display_name or self.username

    @property
    def can_login(self):
        return self.is_active and self.account_status == 'active'

    @property
    def teams(self):
        return self.memberships_json if isinstance(self.memberships_json, list) else []
