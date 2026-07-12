import re
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from ..extensions import db
from ..models import User, Training, Activity, TrainingInstance, ActivityInstance, AgendaCategory
from ..utils import get_upcoming_trainings, get_past_trainings

_CATEGORY_KEY_RE = re.compile(r'^[a-z0-9_-]{1,40}$')

bp = Blueprint('api', __name__, url_prefix='/api')


def _authorized():
    expected = current_app.config.get('INTERNAL_API_SECRET')
    provided = request.headers.get('X-TT-Internal-Secret')
    return bool(expected and provided and provided == expected)


def _parse_team_codes(raw_value):
    if not raw_value:
        return []
    team_codes = []
    for item in raw_value.split(','):
        code = (item or '').strip().upper()
        if code and code not in team_codes:
            team_codes.append(code)
    return team_codes


def _load_upcoming_trainings(team_codes=None):
    trainings_query = Training.query
    if team_codes:
        trainings_query = trainings_query.filter(Training.team_code.in_(team_codes))
    trainings_query = trainings_query.order_by(Training.start_date.asc(), Training.weekday.asc(), Training.start_time.asc(), Training.id.asc())

    trainings = trainings_query.all()
    training_ids = [training.id for training in trainings]

    activities_by_training = {training.id: [] for training in trainings}
    if training_ids:
        for activity in (
            Activity.query
            .filter(Activity.training_id.in_(training_ids))
            .order_by(Activity.training_id, Activity.order_index)
            .all()
        ):
            activities_by_training[activity.training_id].append(activity)

    instances_by_key = {}
    instance_activities_by_id = {}
    if training_ids:
        instances = TrainingInstance.query.filter(TrainingInstance.training_id.in_(training_ids)).all()
        instance_ids = [instance.id for instance in instances]
        instances_by_key = {(instance.training_id, instance.date): instance for instance in instances}
        if instance_ids:
            for activity in (
                ActivityInstance.query
                .filter(ActivityInstance.training_instance_id.in_(instance_ids))
                .order_by(ActivityInstance.training_instance_id, ActivityInstance.order_index)
                .all()
            ):
                instance_activities_by_id.setdefault(activity.training_instance_id, []).append(activity)

    limit = request.args.get('limit', type=int)
    if limit is not None and limit <= 0:
        limit = None

    upcoming = get_upcoming_trainings(
        trainings,
        activities_by_training,
        instances_by_key,
        instance_activities_by_id,
        datetime.now(),
        limit=limit,
    )
    return upcoming


def _serialize_training(item):
    training = item['training']
    date = item.get('date')
    occurrence_id = item.get('occurrence_id') or (f'{training.id}:{date.isoformat()}' if date else str(training.id))
    category = AgendaCategory.query.filter_by(key=training.category or 'training').first()
    category_key = category.key if category else (training.category or 'training')
    category_payload = {
        'key': category_key,
        'label': category.label if category else category_key,
        'icon': category.icon if category else 'bi-calendar-event',
        'badge_class': category.badge_class if category else '',
        'required_for': category.attendance_required_for if category else ['player'],
        'allowed_for': category.attendance_allowed_for if category else ['player'],
        'show_presence_tracking': category.show_presence_tracking if category else True,
    }
    overrides = training.participation_rules_json or {}
    if isinstance(overrides, dict):
        for key in ('required_for', 'allowed_for', 'show_presence_tracking'):
            if key in overrides:
                category_payload[key] = overrides[key]
    return {
        'id': occurrence_id,
        'occurrence_id': occurrence_id,
        'training_id': str(item.get('template_id') or training.id),
        'template_id': str(item.get('template_id') or training.id),
        'instance_id': item.get('instance_id'),
        'title': training.name,
        'category': category_key,
        'category_meta': category_payload,
        'team_code': training.team_code,
        'date': date.isoformat() if date else None,
        'time': f"{item['start_time'].strftime('%H:%M')} - {item['end_time'].strftime('%H:%M')}" if item.get('start_time') and item.get('end_time') else None,
        'start_time': item['start_time'].strftime('%H:%M') if item.get('start_time') else None,
        'end_time': item['end_time'].strftime('%H:%M') if item.get('end_time') else None,
        'is_today': item.get('is_today', False),
        'is_running': item.get('is_running', False),
        'is_upcoming': item.get('is_upcoming', False),
        'activities_count': item.get('activities_count', 0),
        'is_individual': item.get('is_individual', False),
        'is_cancelled': item.get('is_cancelled', False),
        'is_free': item.get('is_free', False),
    }


@bp.route('/trainings', methods=['GET'])
def trainings():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401

    team_codes = _parse_team_codes(request.args.get('teams'))
    upcoming = _load_upcoming_trainings(team_codes or None)
    return jsonify({
        'trainings': [_serialize_training(item) for item in upcoming],
        'teams': team_codes,
    })


@bp.route('/trainings/past', methods=['GET'])
def past_trainings():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401

    team_codes = _parse_team_codes(request.args.get('teams'))
    weeks = request.args.get('weeks', type=int) or 4

    trainings_query = Training.query
    if team_codes:
        trainings_query = trainings_query.filter(Training.team_code.in_(team_codes))
    trainings = trainings_query.order_by(Training.start_date.asc()).all()
    training_ids = [t.id for t in trainings]

    activities_by_training = {t.id: [] for t in trainings}
    if training_ids:
        for activity in (
            Activity.query
            .filter(Activity.training_id.in_(training_ids))
            .order_by(Activity.training_id, Activity.order_index)
            .all()
        ):
            activities_by_training[activity.training_id].append(activity)

    instances_by_key = {}
    instance_activities_by_id = {}
    if training_ids:
        instances = TrainingInstance.query.filter(TrainingInstance.training_id.in_(training_ids)).all()
        instance_ids = [i.id for i in instances]
        instances_by_key = {(i.training_id, i.date): i for i in instances}
        if instance_ids:
            for activity in (
                ActivityInstance.query
                .filter(ActivityInstance.training_instance_id.in_(instance_ids))
                .order_by(ActivityInstance.training_instance_id, ActivityInstance.order_index)
                .all()
            ):
                instance_activities_by_id.setdefault(activity.training_instance_id, []).append(activity)

    past = get_past_trainings(trainings, activities_by_training, instances_by_key, instance_activities_by_id, weeks=weeks)
    return jsonify({
        'trainings': [_serialize_training(item) for item in past],
        'teams': team_codes,
        'weeks': weeks,
    })


@bp.route('/trainings/<path:occurrence_id>', methods=['GET'])
def training_detail(occurrence_id):
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401

    team_codes = _parse_team_codes(request.args.get('teams'))
    upcoming = _load_upcoming_trainings(team_codes or None)
    for item in upcoming:
        payload = _serialize_training(item)
        if payload['id'] == occurrence_id:
            return jsonify(payload)

    return jsonify({'error': 'not_found'}), 404


def _cat_to_dict(cat):
    return {
        'key': cat.key,
        'label': cat.label,
        'icon': cat.icon,
        'badge_class': cat.badge_class,
        'sort_order': cat.sort_order,
        'active': cat.active,
        'attendance_required_for': cat.attendance_required_for or [],
        'attendance_allowed_for': cat.attendance_allowed_for or [],
        'show_presence_tracking': cat.show_presence_tracking,
    }


@bp.route('/internal/agenda-categories', methods=['GET'])
def internal_agenda_categories_list():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    cats = AgendaCategory.query.order_by(AgendaCategory.sort_order, AgendaCategory.id).all()
    return jsonify({'categories': [_cat_to_dict(c) for c in cats]})


@bp.route('/internal/agenda-categories', methods=['POST'])
def internal_agenda_categories_create():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    key = (data.get('key') or '').strip().lower()
    label = (data.get('label') or '').strip()
    if not key or not _CATEGORY_KEY_RE.match(key):
        return jsonify({'error': 'invalid_key'}), 400
    if not label:
        return jsonify({'error': 'label_required'}), 400
    if AgendaCategory.query.filter_by(key=key).first():
        return jsonify({'error': 'key_exists'}), 409
    cat = AgendaCategory(
        key=key,
        label=label,
        icon=(data.get('icon') or 'bi-calendar-event').strip(),
        badge_class=(data.get('badge_class') or 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300').strip(),
        sort_order=int(data.get('sort_order') or 0),
        active=bool(data.get('active', True)),
        attendance_required_for=data.get('attendance_required_for') or [],
        attendance_allowed_for=data.get('attendance_allowed_for') or [],
        show_presence_tracking=bool(data.get('show_presence_tracking', True)),
    )
    db.session.add(cat)
    db.session.commit()
    return jsonify({'category': _cat_to_dict(cat)}), 201


@bp.route('/internal/agenda-categories/<string:key>', methods=['PUT'])
def internal_agenda_categories_update(key):
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    cat = AgendaCategory.query.filter_by(key=key).first()
    if not cat:
        return jsonify({'error': 'not_found'}), 404
    data = request.get_json(silent=True) or {}
    label = (data.get('label') or '').strip()
    if not label:
        return jsonify({'error': 'label_required'}), 400
    cat.label = label
    cat.icon = (data.get('icon') or cat.icon).strip()
    cat.badge_class = (data.get('badge_class') or cat.badge_class).strip()
    cat.sort_order = int(data.get('sort_order') if data.get('sort_order') is not None else cat.sort_order)
    cat.active = bool(data.get('active', cat.active))
    cat.attendance_required_for = data.get('attendance_required_for') if data.get('attendance_required_for') is not None else cat.attendance_required_for
    cat.attendance_allowed_for = data.get('attendance_allowed_for') if data.get('attendance_allowed_for') is not None else cat.attendance_allowed_for
    cat.show_presence_tracking = bool(data.get('show_presence_tracking', cat.show_presence_tracking))
    db.session.commit()
    return jsonify({'category': _cat_to_dict(cat)})


@bp.route('/internal/agenda-categories/<string:key>', methods=['DELETE'])
def internal_agenda_categories_delete(key):
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    cat = AgendaCategory.query.filter_by(key=key).first()
    if not cat:
        return jsonify({'error': 'not_found'}), 404
    in_use = Training.query.filter_by(category=key).first()
    if in_use:
        return jsonify({'error': 'in_use'}), 409
    db.session.delete(cat)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@bp.route('/internal/users/<int:auth_user_id>', methods=['DELETE'])
def delete_user(auth_user_id):
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401

    user = User.query.filter_by(auth_user_id=auth_user_id).first()
    if not user:
        return jsonify({'status': 'not_found'}), 404

    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': 'deleted', 'auth_user_id': auth_user_id}), 200
