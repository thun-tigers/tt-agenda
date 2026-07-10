from flask import Flask, abort, request, session
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import Config
from .extensions import db, migrate, limiter
from .utils import (
    ACTIVITY_TYPE_DEFAULTS,
    can_manage_agenda,
    can_view_agenda,
    get_active_team_code,
    get_active_team_name,
    get_activity_color,
    get_activity_type_defs,
    get_activity_type_order,
    get_available_teams,
    POSITION_GROUP_DEFAULTS,
    get_position_group_defs,
    get_position_groups,
    get_position_group_labels,
    refresh_position_groups,
    get_team_like_types,
    AGENDA_CATEGORY_DEFAULTS,
)
from .activity_colors import get_activity_color_map
from datetime import timedelta
from .routes import main, auth, admin, api
from .models import User, ActivityType, AgendaCategory
import json
from dotenv import load_dotenv
import logging
import secrets
import requests
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError
import sys
from pathlib import Path
from jinja2 import FileSystemLoader

def create_app(config_class=Config):
    load_dotenv()  # Load .env file
    
    # Configure logging based on config
    log_level = getattr(logging, config_class.LOG_LEVEL, logging.INFO)
    formatter = logging.Formatter('[%(asctime)s +0000] [%(process)d] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    
    # Create Flask app
    app = Flask(__name__)
    
    # Use app templates only
    app.jinja_loader = FileSystemLoader(str(Path(__file__).parent / "templates"))
    
    app.config.from_object(config_class)

    # Flask session config
    app.config.setdefault('SESSION_COOKIE_SECURE', True)
    app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
    app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')

    if not app.config.get('SECRET_KEY'):
        if app.debug or app.testing:
            app.logger.warning('SECRET_KEY is not set; running in insecure development mode.')
        else:
            raise RuntimeError('SECRET_KEY must be set in production.')
    
    # Log startup config
    app.logger.info(f"Application started with LOG_LEVEL: {config_class.LOG_LEVEL}")
    app.logger.info(f"WEBHOOK_ENABLED: {app.config.get('WEBHOOK_ENABLED', False)}, WEBHOOK_URL: {app.config.get('WEBHOOK_URL', '')}")

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # Register Blueprints
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(api.bp)

    # Zentrales UI-Layout aus tt-common
    from tt_common import register_shared_ui
    register_shared_ui(
        app,
        brand_label='Agenda',
        brand_icon='bi-calendar-week-fill',
        home_endpoint='main.index',
        logout_endpoint='auth.logout',
    )

    @app.context_processor
    def inject_current_user():
        # Das geteilte Layout gated auf current_user; agenda arbeitet
        # sessionbasiert, daher hier aus der Session ableiten.
        if session.get('user_id'):
            return {'current_user': {
                'username': session.get('username'),
                'role': session.get('user_role', 'user'),
            }}
        return {'current_user': None}

    # Context processors and filters
    @app.context_processor
    def inject_colors():
        activity_defs = get_activity_type_defs()
        position_defs = get_position_group_defs()
        return {
            'LIGHT_MODE_COLORS': get_activity_color_map('light'),
            'DARK_MODE_COLORS': get_activity_color_map('dark'),
            'get_activity_color': get_activity_color,
            'timedelta': timedelta,
            'ACTIVITY_TYPE_DEFS': activity_defs,
            'ACTIVITY_TYPE_ORDER': get_activity_type_order(),
            'TEAM_LIKE_TYPES': get_team_like_types(),
            'ACTIVITY_TYPE_BEHAVIORS': {key: value.get('behavior') for key, value in activity_defs.items()},
            'POSITION_GROUP_DEFS': position_defs,
            'POSITION_GROUPS': [item['key'] for item in position_defs],
            'POSITION_GROUP_LABELS': {item['key']: item['label'] for item in position_defs},
            'can_manage_agenda': can_manage_agenda,
            'can_view_agenda': can_view_agenda,
        }

    @app.before_request
    def refresh_shared_master_data():
        refresh_position_groups()

    def generate_csrf_token():
        token = session.get('_csrf_token')
        if not token:
            token = secrets.token_urlsafe(32)
            session['_csrf_token'] = token
        return token

    @app.context_processor
    def inject_csrf_token():
        return {'csrf_token': generate_csrf_token}

    @app.context_processor
    def inject_platform_links():
        auth_base_url = (app.config.get('AUTH_BASE_URL') or 'http://localhost:8085').rstrip('/')
        teams = get_available_teams()
        active_team_code = get_active_team_code()
        return {
            'auth_base_url': auth_base_url,
            'auth_dashboard_url': f'{auth_base_url}/',
            'available_teams': teams,
            'active_team_code': active_team_code,
            'active_team_name': get_active_team_name(),
        }

    @app.context_processor
    def inject_pending_messages_count():
        auth_user_id = session.get('auth_user_id')
        if not auth_user_id:
            user_id = session.get('user_id')
            if user_id:
                user = db.session.get(User, user_id)
                auth_user_id = user.auth_user_id if user else None
        return {'pending_messages_count': _fetch_pending_messages_count(app, auth_user_id)}

    @app.before_request
    def csrf_protect():
        if request.path.startswith('/api/internal/'):
            return  # Interne Service-zu-Service APIs sind via Secret geschützt
        if request.path in {'/admin/backup/download', '/admin/backup/restore'}:
            return
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            token = session.get('_csrf_token')
            if request.is_json:
                payload = request.get_json(silent=True) or {}
                request_token = request.headers.get('X-CSRFToken') or payload.get('csrf_token')
            else:
                request_token = request.form.get('csrf_token')
            if not token or not request_token or token != request_token:
                abort(400)

    @app.template_filter('parse_groups')
    def parse_groups(groups_json):
        if isinstance(groups_json, (list, dict)):
            return groups_json
        try:
            return json.loads(groups_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @app.template_filter('from_json')
    def from_json(json_string):
        if isinstance(json_string, (list, dict)):
            return json_string
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError):
            return {}

    @app.template_filter('get_activity_color')
    def get_activity_color_filter(activity_type):
        return get_activity_color(activity_type)

    @app.template_filter('build_group_cells')
    def build_group_cells_filter(activity):
        from .utils import build_group_cells
        return build_group_cells(activity)

    def ensure_activity_types():
        if not ACTIVITY_TYPE_DEFAULTS:
            return
        defaults_by_key = {item['key']: item for item in ACTIVITY_TYPE_DEFAULTS}
        rows = ActivityType.query.all()
        existing_keys = {row.key for row in rows}
        missing = [item for item in ACTIVITY_TYPE_DEFAULTS if item['key'] not in existing_keys]
        if missing:
            for item in missing:
                db.session.add(ActivityType(**item))
            db.session.commit()
            rows = ActivityType.query.all()

        changed = False
        for row in rows:
            defaults = defaults_by_key.get(row.key)
            if not defaults:
                continue
            for field in ('label', 'behavior', 'badge_class', 'sort_order'):
                if getattr(row, field, None) in (None, ''):
                    setattr(row, field, defaults[field])
                    changed = True
            if row.light_color in (None, '', '#E8E8E8') and defaults.get('light_color'):
                row.light_color = defaults['light_color']
                changed = True
            if row.dark_color in (None, '', '#4A4A4A') and defaults.get('dark_color'):
                row.dark_color = defaults['dark_color']
                changed = True
        if changed:
            db.session.commit()

    def ensure_user_auth_claim_columns():
        inspector = inspect(db.engine)
        if 'user' not in inspector.get_table_names():
            return
        existing_columns = {column['name'] for column in inspector.get_columns('user')}
        dialect = db.engine.dialect.name
        bool_false = 'false' if dialect == 'postgresql' else '0'
        statements = []
        if 'auth_user_id' not in existing_columns:
            statements.append('ALTER TABLE "user" ADD COLUMN auth_user_id INTEGER')
        if 'platform_role' not in existing_columns:
            statements.append("ALTER TABLE \"user\" ADD COLUMN platform_role VARCHAR(20) DEFAULT 'user'")
        if 'display_name' not in existing_columns:
            statements.append('ALTER TABLE "user" ADD COLUMN display_name VARCHAR(120)')
        if 'email' not in existing_columns:
            statements.append('ALTER TABLE "user" ADD COLUMN email VARCHAR(255)')
        if 'profile_complete' not in existing_columns:
            statements.append(f'ALTER TABLE "user" ADD COLUMN profile_complete BOOLEAN NOT NULL DEFAULT {bool_false}')
        if 'memberships_json' not in existing_columns:
            statements.append("ALTER TABLE \"user\" ADD COLUMN memberships_json TEXT NOT NULL DEFAULT '[]'")
        if 'permissions_json' not in existing_columns:
            statements.append("ALTER TABLE \"user\" ADD COLUMN permissions_json TEXT NOT NULL DEFAULT '[]'")
        if 'claims_json' not in existing_columns:
            statements.append("ALTER TABLE \"user\" ADD COLUMN claims_json TEXT NOT NULL DEFAULT '{}'")
        for statement in statements:
            db.session.execute(text(statement))
        if statements:
            db.session.commit()
            app.logger.info('Applied agenda user auth-claim schema updates.')

    def ensure_training_team_column():
        inspector = inspect(db.engine)
        if 'training' not in inspector.get_table_names():
            return

        existing_columns = {column['name'] for column in inspector.get_columns('training')}
        dialect = db.engine.dialect.name

        statements = []
        if 'team_code' not in existing_columns:
            statements.append("ALTER TABLE training ADD COLUMN team_code VARCHAR(32)")
        if 'category' not in existing_columns:
            statements.append("ALTER TABLE training ADD COLUMN category VARCHAR(20)")

        for statement in statements:
            db.session.execute(text(statement))

        if statements:
            db.session.commit()

        # Backfill existing/null values and enforce NOT NULL semantics
        db.session.execute(text("UPDATE training SET team_code = 'SENIORS' WHERE team_code IS NULL OR team_code = ''"))
        db.session.execute(text("UPDATE training SET category = 'training' WHERE category IS NULL OR category = ''"))
        if dialect == 'postgresql':
            db.session.execute(text("ALTER TABLE training ALTER COLUMN team_code SET DEFAULT 'SENIORS'"))
            db.session.execute(text("ALTER TABLE training ALTER COLUMN team_code SET NOT NULL"))
            db.session.execute(text("ALTER TABLE training ALTER COLUMN category SET DEFAULT 'training'"))
            db.session.execute(text("ALTER TABLE training ALTER COLUMN category SET NOT NULL"))
        db.session.commit()

    with app.app_context():
        if app.config.get('AUTO_CREATE_DB'):
            try:
                db.create_all()
            except OperationalError as exc:
                if 'already exists' not in str(exc).lower():
                    raise
                app.logger.warning('DB init race condition detected; continuing.')
            ensure_user_auth_claim_columns()
            ensure_training_team_column()
            # Backward-compat shim for existing deployments that do not run
            # `flask db upgrade`. New installations use Alembic migrations.
            if db.engine.dialect.name == 'sqlite':
                table_exists = db.session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_type'")
                ).fetchone()
                if table_exists:
                    result = db.session.execute(text("PRAGMA table_info(activity_type)")).fetchall()
                    existing_columns = {row[1] for row in result}
                    if 'light_color' not in existing_columns:
                        db.session.execute(text("ALTER TABLE activity_type ADD COLUMN light_color VARCHAR(7) NOT NULL DEFAULT '#E8E8E8'"))
                    if 'dark_color' not in existing_columns:
                        db.session.execute(text("ALTER TABLE activity_type ADD COLUMN dark_color VARCHAR(7) NOT NULL DEFAULT '#4A4A4A'"))

                result = db.session.execute(text("PRAGMA table_info(training)")).fetchall()
                existing_columns = {row[1] for row in result}
                if 'is_hidden' not in existing_columns:
                    db.session.execute(text("ALTER TABLE training ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT 0"))
                if 'category' not in existing_columns:
                    db.session.execute(text("ALTER TABLE training ADD COLUMN category VARCHAR(20) NOT NULL DEFAULT 'training'"))
                db.session.commit()
            ensure_activity_types()
            for category_data in AGENDA_CATEGORY_DEFAULTS:
                category = AgendaCategory.query.filter_by(key=category_data['key']).first()
                if not category:
                    category = AgendaCategory(
                        key=category_data['key'],
                        label=category_data['label'],
                        icon=category_data['icon'],
                        badge_class=category_data['badge_class'],
                        sort_order=category_data['sort_order'],
                        attendance_required_for=category_data['required_for'],
                        attendance_allowed_for=category_data['allowed_for'],
                        show_presence_tracking=category_data['show_presence_tracking'],
                    )
                    db.session.add(category)
            db.session.commit()
            refresh_position_groups()
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    return app


def _fetch_pending_messages_count(app, auth_user_id):
    if not auth_user_id:
        return 0

    members_base = (app.config.get('TT_MEMBERS_INTERNAL_URL') or 'http://tt-members:5000').rstrip('/')
    secret = app.config.get('INTERNAL_API_SECRET') or app.config.get('SSO_SHARED_SECRET') or app.config.get('SECRET_KEY')
    if not secret:
        return 0

    try:
        response = requests.get(
            f'{members_base}/api/internal/messages/count',
            params={'auth_user_id': auth_user_id},
            headers={'X-TT-Internal-Secret': secret},
            timeout=2,
        )
        if response.status_code != 200:
            return 0
        payload = response.json() or {}
        return max(0, int(payload.get('pending_messages_count') or 0))
    except Exception:
        return 0
