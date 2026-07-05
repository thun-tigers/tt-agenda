from datetime import datetime, timedelta
from flask import session, flash, redirect, url_for, request
from functools import wraps
import json
import logging
import os
from typing import List, Tuple, Optional, Dict, Any
import requests
from .models import Activity, ActivityInstance, Training, TrainingInstance, ActivityType
from .authz import has_role_permission, is_platform_admin, is_service_admin, normalize_permissions
from .extensions import db

logger = logging.getLogger(__name__)

WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
POSITION_GROUP_DEFAULTS = [
    {'key': 'OL', 'label': 'OL', 'sort_order': 1},
    {'key': 'DL', 'label': 'DL', 'sort_order': 2},
    {'key': 'LB', 'label': 'LB', 'sort_order': 3},
    {'key': 'RB', 'label': 'RB', 'sort_order': 4},
    {'key': 'DB', 'label': 'DB', 'sort_order': 5},
    {'key': 'TE', 'label': 'TE', 'sort_order': 6},
    {'key': 'WR', 'label': 'WR', 'sort_order': 7},
    {'key': 'QB', 'label': 'QB', 'sort_order': 8},
]
POSITION_GROUPS = [item['key'] for item in POSITION_GROUP_DEFAULTS]
POSITION_GROUP_LABELS = {item['key']: item['label'] for item in POSITION_GROUP_DEFAULTS}


def _infra_base_url():
    return (
        os.environ.get('TT_INFRA_INTERNAL_URL')
        or os.environ.get('INFRA_INTERNAL_URL')
        or 'http://localhost:8084'
    ).rstrip('/')


def refresh_position_groups():
    try:
        secret = os.environ.get('INTERNAL_API_SECRET') or os.environ.get('SSO_SHARED_SECRET')
        headers = {'X-TT-Internal-Secret': secret} if secret else {}
        response = requests.get(f'{_infra_base_url()}/api/master-data/positions', headers=headers, timeout=4)
        if response.status_code >= 400:
            logger.warning("refresh_position_groups: infra query failed %s %s", response.status_code, response.text)
            return POSITION_GROUPS
        payload = response.json() or {}
        rows = payload.get('positions') or []
        cleaned = []
        labels = {}
        for row in rows:
            key = (row.get('key') or '').strip().upper()
            label = (row.get('label') or key).strip()
            if not key:
                continue
            cleaned.append(key)
            labels[key] = label or key
        if cleaned:
            POSITION_GROUPS[:] = cleaned
            POSITION_GROUP_LABELS.clear()
            POSITION_GROUP_LABELS.update(labels)
        return POSITION_GROUPS
    except Exception:
        logger.warning("refresh_position_groups: infra query failed, using defaults", exc_info=True)
        return POSITION_GROUPS


def get_position_group_defs():
    return [
        {'key': key, 'label': POSITION_GROUP_LABELS.get(key, key), 'sort_order': idx + 1}
        for idx, key in enumerate(POSITION_GROUPS)
    ]


def get_position_groups():
    return POSITION_GROUPS


def get_position_group_labels():
    return POSITION_GROUP_LABELS

ACTIVITY_TYPE_DEFAULTS = [
    {
        'key': 'team',
        'label': 'Team',
        'behavior': 'team',
        'badge_class': 'bg-info',
        'light_color': '#C6B8FF',
        'dark_color': '#8B7BFF',
        'sort_order': 1
    },
    {
        'key': 'prepractice',
        'label': 'Prepractice',
        'behavior': 'team',
        'badge_class': 'bg-warning',
        'light_color': '#FFE0B3',
        'dark_color': '#FB923C',
        'sort_order': 2
    },
    {
        'key': 'individual',
        'label': 'Individual',
        'behavior': 'individual',
        'badge_class': 'bg-success',
        'light_color': '#BFE9D3',
        'dark_color': '#34D399',
        'sort_order': 3
    },
    {
        'key': 'group',
        'label': 'Group',
        'behavior': 'group',
        'badge_class': 'bg-primary',
        'light_color': '#B7D4FF',
        'dark_color': '#60A5FA',
        'sort_order': 4
    }
]

def _activity_type_defaults_by_key():
    return {item['key']: item for item in ACTIVITY_TYPE_DEFAULTS}

def get_activity_type_defs():
    try:
        rows = ActivityType.query.order_by(ActivityType.sort_order).all()
    except Exception:
        logger.warning("get_activity_type_defs: DB query failed, using defaults", exc_info=True)
        rows = []

    if not rows:
        defaults = _activity_type_defaults_by_key()
        return {
            key: {
                'label': value['label'],
                'behavior': value['behavior'],
                'badge_class': value['badge_class']
            }
            for key, value in defaults.items()
        }

    return {
        row.key: {
            'label': row.label,
            'behavior': row.behavior,
            'badge_class': row.badge_class
        }
        for row in rows
    }

def get_activity_type_order():
    try:
        rows = ActivityType.query.order_by(ActivityType.sort_order).all()
    except Exception:
        logger.warning("get_activity_type_order: DB query failed, using defaults", exc_info=True)
        rows = []

    if not rows:
        return [item['key'] for item in sorted(ACTIVITY_TYPE_DEFAULTS, key=lambda d: d['sort_order'])]

    return [row.key for row in rows]

def get_team_like_types():
    defs = get_activity_type_defs()
    return [key for key, value in defs.items() if value.get('behavior') == 'team']

def get_activity_behavior(activity_type: str) -> str:
    try:
        row = ActivityType.query.filter_by(key=activity_type).first()
    except Exception:
        logger.warning("get_activity_behavior: DB query failed for '%s'", activity_type, exc_info=True)
        row = None
    if row and row.behavior:
        return row.behavior
    defaults = _activity_type_defaults_by_key()
    return defaults.get(activity_type, {}).get('behavior', 'team')

try:
    from .activity_colors import get_activity_color, LIGHT_MODE_COLORS, DARK_MODE_COLORS
except ImportError:
    # Fallback colors if activity_colors.py is missing
    LIGHT_MODE_COLORS = {'team': '#A8D5E2', 'prepractice': '#FFD6CC', 'individual': '#D4E4C5', 'group': '#FFE5B4'}
    DARK_MODE_COLORS = {'team': '#4A90A4', 'prepractice': '#C97A6B', 'individual': '#7A9B6B', 'group': '#C9A86B'}

    def get_activity_color(activity_type, theme='light'):
        color_map = DARK_MODE_COLORS if theme == 'dark' else LIGHT_MODE_COLORS
        return color_map.get(activity_type, '#E8E8E8' if theme == 'light' else '#4A4A4A')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Bitte melden Sie sich an.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def get_user_permissions():
    return normalize_permissions(session.get('permissions'))


def get_user_memberships():
    memberships = session.get('memberships') or []
    return memberships if isinstance(memberships, list) else []


def get_available_teams():
    memberships = get_user_memberships()
    teams = {}
    for membership in memberships:
        code = (membership.get('team_code') or '').strip().upper()
        name = (membership.get('team_name') or '').strip()
        if not code:
            continue
        teams[code] = name or code

    if not teams:
        teams = {'SENIORS': 'Seniors'}

    return [{'code': code, 'name': teams[code]} for code in sorted(teams.keys())]


def get_active_team_code():
    teams = get_available_teams()
    available_codes = {team['code'] for team in teams}
    active = (session.get('active_team_code') or '').strip().upper()

    if active in available_codes:
        return active

    fallback = teams[0]['code']
    session['active_team_code'] = fallback
    return fallback


def get_active_team_name():
    active = get_active_team_code()
    teams = get_available_teams()
    for team in teams:
        if team['code'] == active:
            return team['name']
    return active


def can_manage_agenda():
    permissions = get_user_permissions()
    claims = session.get('claims_json') or {}
    role_permissions = claims.get('role_permissions') or {}
    if is_platform_admin(session.get('platform_role'), permissions):
        return True
    if is_service_admin(session.get('user_role'), permissions, role_permissions=role_permissions, service_name='agenda'):
        return True
    if (
        has_role_permission(role_permissions, 'create', 'agenda')
        or has_role_permission(role_permissions, 'write', 'agenda')
        or has_role_permission(role_permissions, 'update', 'agenda')
        or has_role_permission(role_permissions, 'delete', 'agenda')
        or has_role_permission(role_permissions, 'approve', 'agenda')
    ):
        return True
    if 'agenda:admin' in permissions or 'agenda:write' in permissions:
        return True
    return any(
        permission.startswith('team:') and (permission.endswith(':write') or permission.endswith(':admin'))
        for permission in permissions
    )


def can_view_agenda():
    if can_manage_agenda():
        return True
    permissions = get_user_permissions()
    claims = session.get('claims_json') or {}
    role_permissions = claims.get('role_permissions') or {}
    if has_role_permission(role_permissions, 'read', 'agenda'):
        return True
    if 'agenda:read' in permissions or 'profile:read' in permissions:
        return True
    return any(permission.startswith('team:') and permission.endswith(':read') for permission in permissions)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Bitte melden Sie sich an.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if not can_manage_agenda():
            flash('Sie haben keine Berechtigung für diese Aktion.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def build_activity_timeline(activities: List[Activity], base_date: datetime.date) -> List[Tuple[Activity, datetime, datetime]]:
    """Erstellt eine Timeline mit Datetimes, inkl. Mitternachts-Überlauf."""
    timeline = []
    current_date = base_date
    last_start = None

    for activity in activities:
        activity_start = datetime.combine(current_date, activity.start_time)
        if last_start and activity_start <= last_start:
            current_date += timedelta(days=1)
            activity_start = datetime.combine(current_date, activity.start_time)

        activity_end = activity_start + timedelta(minutes=activity.duration)
        timeline.append((activity, activity_start, activity_end))
        last_start = activity_start

    return timeline

def get_training_timeline(training: Training, base_date: datetime.date) -> Tuple[Optional[List[Activity]], Optional[List[Tuple[Activity, datetime, datetime]]], Optional[datetime], Optional[datetime]]:
    """Lädt Aktivitäten und berechnet die Timeline für ein Datum."""
    activities = Activity.query.filter_by(training_id=training.id).order_by(Activity.order_index).all()
    if not activities:
        return None, None, None, None

    timeline, start_dt, end_dt = get_timeline_from_activities(activities, base_date)
    if not timeline:
        return activities, None, None, None

    return activities, timeline, start_dt, end_dt

def get_timeline_from_activities(activities: List[Activity], base_date: datetime.date) -> Tuple[Optional[List[Tuple[Activity, datetime, datetime]]], Optional[datetime], Optional[datetime]]:
    """Berechnet die Timeline aus einer gegebenen Aktivitätsliste."""
    if not activities:
        return None, None, None
    timeline = build_activity_timeline(activities, base_date)
    if not timeline:
        return None, None, None
    return timeline, timeline[0][1], timeline[-1][2]

def get_next_training_dates(training, activities: Optional[List[Activity]] = None, limit=3, now: Optional[datetime] = None):
    """Berechnet die nächsten Trainingstermine für ein Training."""
    now = now or datetime.now()
    today = now.date()
    dates = []

    if training.end_date < today:
        return dates

    start = max(today, training.start_date)
    days_ahead = (training.weekday - start.weekday()) % 7
    current = start + timedelta(days=days_ahead)
    target_limit = float('inf') if limit is None else limit

    while current <= training.end_date and len(dates) < target_limit:
        if current == today:
            if activities is None:
                activities = Activity.query.filter_by(training_id=training.id).order_by(Activity.order_index, Activity.id).all()
            if activities:
                timeline = build_activity_timeline(activities, today)
                if timeline and now < timeline[-1][2]:
                    dates.append(current)
        else:
            dates.append(current)
        current += timedelta(days=7)

    return dates

def resolve_activities_for_date(training: Training, date: datetime.date, activities_by_training: Dict[int, List[Activity]], instances_by_key: Dict[tuple, TrainingInstance], instance_activities_by_id: Dict[int, List[ActivityInstance]]):
    instance = instances_by_key.get((training.id, date))
    if instance:
        if instance.status == 'cancelled':
            return [], True
        return instance_activities_by_id.get(instance.id, []), False
    return activities_by_training.get(training.id, []), False

def load_training_data(team_code=None):
    """Lädt alle Trainings, Aktivitäten und Instanzen effizient aus der DB.

    Gibt ein 4-Tuple zurück:
      (trainings, activities_by_training, instances_by_key, instance_activities_by_id)
    """
    trainings_query = Training.query
    if team_code:
        trainings_query = trainings_query.filter_by(team_code=team_code)
    trainings = trainings_query.all()
    training_ids = [t.id for t in trainings]

    activities_by_training: Dict[int, List[Activity]] = {t.id: [] for t in trainings}
    if training_ids:
        for activity in Activity.query.filter(
            Activity.training_id.in_(training_ids)
        ).order_by(Activity.training_id, Activity.order_index).all():
            activities_by_training[activity.training_id].append(activity)

    instances_by_key: Dict[tuple, TrainingInstance] = {}
    instance_activities_by_id: Dict[int, List[ActivityInstance]] = {}
    if training_ids:
        instances = TrainingInstance.query.filter(
            TrainingInstance.training_id.in_(training_ids)
        ).all()
        instance_ids = [i.id for i in instances]
        instances_by_key = {(i.training_id, i.date): i for i in instances}
        if instance_ids:
            for activity in ActivityInstance.query.filter(
                ActivityInstance.training_instance_id.in_(instance_ids)
            ).order_by(ActivityInstance.training_instance_id, ActivityInstance.order_index).all():
                instance_activities_by_id.setdefault(activity.training_instance_id, []).append(activity)

    return trainings, activities_by_training, instances_by_key, instance_activities_by_id


def get_current_training_status(trainings: List[Training], activities_by_training: Dict[int, List[Activity]], instances_by_key: Dict[tuple, TrainingInstance], instance_activities_by_id: Dict[int, List[ActivityInstance]], now: datetime):
    """Ermittelt laufendes oder nächstes Training basierend auf vorhandenen Aktivitäten."""
    today = now.date()
    yesterday = today - timedelta(days=1)
    today_weekday = today.weekday()

    current_training = None
    current_activity = None
    next_activity = None
    training_status = None
    upcoming_start = None
    current_date = None
    current_activities = None
    current_start_dt = None

    for training in trainings:
        activities = activities_by_training.get(training.id, [])
        for candidate_date in (yesterday, today):
            if training.weekday != candidate_date.weekday():
                continue
            if not (training.start_date <= candidate_date <= training.end_date):
                continue

            activities, is_cancelled = resolve_activities_for_date(training, candidate_date, activities_by_training, instances_by_key, instance_activities_by_id)
            if is_cancelled:
                continue
            timeline, start_dt, end_dt = get_timeline_from_activities(activities, candidate_date)
            if not timeline:
                continue

            if start_dt <= now < end_dt:
                current_training = training
                training_status = 'running'
                for i, (activity, activity_start, activity_end) in enumerate(timeline):
                    if activity_start <= now < activity_end:
                        current_activity = activity
                        if i + 1 < len(timeline):
                            next_activity = timeline[i + 1][0]
                        break
                    if now < activity_start:
                        next_activity = activity
                        break
                current_date = candidate_date
                current_activities = activities
                current_start_dt = start_dt
                return current_training, current_activity, next_activity, training_status, current_date, current_activities, current_start_dt

        if training.weekday == today_weekday and training.start_date <= today <= training.end_date:
            activities, is_cancelled = resolve_activities_for_date(training, today, activities_by_training, instances_by_key, instance_activities_by_id)
            if is_cancelled:
                continue
            timeline, start_dt, _end_dt = get_timeline_from_activities(activities, today)
            if timeline and now < start_dt:
                if upcoming_start is None or start_dt < upcoming_start:
                    current_training = training
                    training_status = 'upcoming'
                    next_activity = timeline[0][0]
                    current_activity = None
                    upcoming_start = start_dt
                    current_date = today
                    current_activities = activities
                    current_start_dt = start_dt

    return current_training, current_activity, next_activity, training_status, current_date, current_activities, current_start_dt

def get_upcoming_trainings(trainings: List[Training], activities_by_training: Dict[int, List[Activity]], instances_by_key: Dict[tuple, TrainingInstance], instance_activities_by_id: Dict[int, List[ActivityInstance]], now: datetime):
    """Baut die Liste aller kommenden Trainings für die Übersicht."""
    today = now.date()
    upcoming_trainings = []

    for training in trainings:
        template_activities = activities_by_training.get(training.id, [])
        next_dates = get_next_training_dates(training, activities=template_activities, limit=None, now=now)
        for date in next_dates:
            instance = instances_by_key.get((training.id, date))
            activities, is_cancelled = resolve_activities_for_date(training, date, activities_by_training, instances_by_key, instance_activities_by_id)
            display_activities = activities
            if is_cancelled:
                display_activities = instance_activities_by_id.get(instance.id, []) if instance else []
                if not display_activities:
                    display_activities = template_activities
            timeline, start_dt, end_dt = get_timeline_from_activities(display_activities, date)
            if not timeline:
                continue

            is_today = date == today
            is_running = is_today and start_dt <= now < end_dt
            is_upcoming = is_today and now < start_dt
            occurrence_id = f'{training.id}:{date.isoformat()}'

            upcoming_trainings.append({
                'training': training,
                'template_id': training.id,
                'instance_id': instance.id if instance else None,
                'occurrence_id': occurrence_id,
                'date': date,
                'start_time': start_dt.time(),
                'end_time': end_dt.time(),
                'is_today': is_today,
                'is_running': is_running,
                'is_upcoming': is_upcoming,
                'activities_count': len(display_activities),
                'is_individual': bool(instance and instance.status == 'active'),
                'is_cancelled': is_cancelled,
                'is_free': bool(training.is_hidden)
            })

    upcoming_trainings.sort(key=lambda x: (x['date'], x['start_time']))
    return upcoming_trainings

def get_text_color_for_bg(bg_color):
    """Berechnet die passende Textfarbe (schwarz/weiß) basierend auf der Hintergrundfarbe."""
    if not bg_color or not bg_color.startswith('#'):
        return 'black'
    try:
        rgb = bg_color[1:]
        r = int(rgb[0:2], 16)
        g = int(rgb[2:4], 16)
        b = int(rgb[4:6], 16)
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        return 'white' if brightness < 128 else 'black'
    except:
        return 'black'

def build_group_cells(activity: Activity) -> List[Dict[str, Any]]:
    all_groups = get_position_groups()
    group_tone_map = {
        'OL': 0,
        'DL': 1,
        'LB': 2,
        'RB': 3,
        'DB': 4,
        'WR': 5,
        'TE': 6,
        'QB': 7
    }
    cells = []
    activity_color = activity.color if hasattr(activity, 'color') and activity.color else get_activity_color(activity.activity_type, 'light')
    text_color = get_text_color_for_bg(activity_color)

    def with_tone_class(base_class: str, groups: List[str]) -> str:
        if not groups:
            return base_class
        tone = group_tone_map.get(groups[0])
        if tone is None:
            return base_class
        return f"{base_class} group-tone-{tone}".strip()

    behavior = get_activity_behavior(activity.activity_type)
    if behavior == 'team':
        position_groups_list = activity.position_groups if activity.position_groups else all_groups
        cells.append({
            'colspan': 8,
            'class': 'table-success text-center',
            'content': activity.topic or '',
            'color': activity_color,
            'text_color': text_color,
            'groups': position_groups_list
        })
    elif behavior == 'individual':
        cells.extend(_build_individual_cells(activity, all_groups, activity_color, text_color, with_tone_class))
    elif behavior == 'group':
        cells.extend(_build_group_cells(activity, all_groups, activity_color, text_color, with_tone_class))

    return cells

def _build_individual_cells(activity: Activity, all_groups: List[str], activity_color: str, text_color: str, with_tone_class) -> List[Dict[str, Any]]:
    cells = []
    topics = activity.topics_json if activity.topics_json else {}
    for group in all_groups:
        if group == 'WR':
            cells.append({
                'colspan': 1,
                'groups': ['WR'],
                'class': with_tone_class('table-success', ['WR']),
                'content': topics.get('WR', topics.get('TE', '')),
                'color': activity_color,
                'text_color': text_color
            })
        elif group == 'TE':
            cells.append({
                'colspan': 1,
                'groups': ['TE'],
                'class': with_tone_class('table-success', ['TE']),
                'content': topics.get('TE', topics.get('WR', '')),
                'color': activity_color,
                'text_color': text_color
            })
        else:
            cells.append({
                'colspan': 1,
                'groups': [group],
                'class': with_tone_class('table-success', [group]),
                'content': topics.get(group, ''),
                'color': activity_color,
                'text_color': text_color
            })
    return cells

def _build_group_cells(activity: Activity, all_groups: List[str], activity_color: str, text_color: str, with_tone_class) -> List[Dict[str, Any]]:
    cells = []
    combinations = activity.topics_json if activity.topics_json else []
    group_to_combo = {g: combo for combo in combinations for g in combo['groups']}
    rendered = set()

    for group in all_groups:
        if group in rendered:
            continue

        combo = group_to_combo.get(group)
        if combo:
            consecutive_groups = _find_consecutive_groups(group, all_groups, group_to_combo, rendered)
            cells.append({
                'colspan': len(consecutive_groups),
                'groups': consecutive_groups,
                'class': with_tone_class('table-success', consecutive_groups),
                'content': combo['topic'],
                'color': activity_color,
                'text_color': text_color
            })
        else:
            cells.append({
                'colspan': 1,
                'groups': [group],
                'class': '',
                'content': ' ',
                'color': None,
                'text_color': None
            })
            rendered.add(group)

    return cells

def _find_consecutive_groups(start_group: str, all_groups: List[str], group_to_combo: Dict[str, Dict], rendered: set) -> List[str]:
    consecutive_groups = [start_group]
    rendered.add(start_group)
    combo = group_to_combo[start_group]

    idx = all_groups.index(start_group) + 1
    while idx < len(all_groups):
        next_group = all_groups[idx]
        if next_group in rendered or group_to_combo.get(next_group) != combo:
            break
        consecutive_groups.append(next_group)
        rendered.add(next_group)
        idx += 1

    return consecutive_groups

def recalculate_times(training_id):
    training = db.session.get(Training, training_id)
    activities = Activity.query.filter_by(training_id=training_id).order_by(Activity.order_index).all()

    if not activities:
        return

    first_activity = activities[0]
    if first_activity.activity_type == 'prepractice':
        start_datetime = datetime.combine(datetime.today(), training.start_time)
        start_datetime -= timedelta(minutes=first_activity.duration)
        first_activity.start_time = start_datetime.time()

        current_datetime = datetime.combine(datetime.today(), first_activity.start_time)
        current_datetime += timedelta(minutes=first_activity.duration)

        for activity in activities[1:]:
            activity.start_time = current_datetime.time()
            current_datetime += timedelta(minutes=activity.duration)
    else:
        current_time = training.start_time
        for activity in activities:
            activity.start_time = current_time
            current_datetime = datetime.combine(datetime.today(), current_time)
            current_datetime += timedelta(minutes=activity.duration)
            current_time = current_datetime.time()

    db.session.commit()

def recalculate_instance_times(instance_id):
    instance = db.session.get(TrainingInstance, instance_id)
    if not instance:
        return
    activities = ActivityInstance.query.filter_by(training_instance_id=instance_id).order_by(ActivityInstance.order_index).all()

    if not activities:
        return

    first_activity = activities[0]
    if first_activity.activity_type == 'prepractice':
        start_datetime = datetime.combine(datetime.today(), instance.start_time)
        start_datetime -= timedelta(minutes=first_activity.duration)
        first_activity.start_time = start_datetime.time()

        current_datetime = datetime.combine(datetime.today(), first_activity.start_time)
        current_datetime += timedelta(minutes=first_activity.duration)

        for activity in activities[1:]:
            activity.start_time = current_datetime.time()
            current_datetime += timedelta(minutes=activity.duration)
    else:
        current_time = instance.start_time
        for activity in activities:
            activity.start_time = current_time
            current_datetime = datetime.combine(datetime.today(), current_time)
            current_datetime += timedelta(minutes=activity.duration)
            current_time = current_datetime.time()

    db.session.commit()
