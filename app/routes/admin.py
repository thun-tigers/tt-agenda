from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from datetime import datetime, timedelta, date
import json
from ..models import Training, Activity, TrainingInstance, ActivityInstance, ActivityType, AgendaCategory
from ..extensions import db
from ..utils import admin_required, WEEKDAYS, POSITION_GROUPS, get_active_team_code, get_activity_behavior, get_activity_color, recalculate_times, recalculate_instance_times
from ..forms import validate_training_form, validate_hidden_training_form, sanitize_color

bp = Blueprint('admin', __name__)


def _participation_overrides(form):
    if form.get('override_enabled') != 'on':
        return None
    required = [item.strip().lower() for value in form.getlist('override_required_for') for item in value.split(',') if item.strip()]
    allowed = [item.strip().lower() for value in form.getlist('override_allowed_for') for item in value.split(',') if item.strip()]
    return {
        'required_for': required,
        'allowed_for': allowed or required,
        'show_presence_tracking': form.get('override_presence') == 'on',
    }


def get_database_backend():
    engine = db.engine
    return engine.dialect.name


def get_database_backend_label(backend):
    labels = {
        'postgresql': 'PostgreSQL',
    }
    return labels.get(backend, backend.capitalize())

def training_edit_url(training):
    endpoint = 'admin.edit_hidden_training' if training.is_hidden else 'admin.edit_training'
    return url_for(endpoint, id=training.id)


def _scoped_training_query(is_hidden=None):
    query = Training.query.filter_by(team_code=get_active_team_code())
    if is_hidden is not None:
        query = query.filter_by(is_hidden=is_hidden)
    return query


def _team_scoped_training_or_404(training_id):
    training = db.get_or_404(Training, training_id)
    if training.team_code != get_active_team_code():
        abort(404)
    return training


def _team_scoped_instance_or_404(instance_id):
    instance = db.get_or_404(TrainingInstance, instance_id)
    if instance.training.team_code != get_active_team_code():
        abort(404)
    return instance

@bp.route('/admin')
@admin_required
def admin_overview():
    """Redirect zur Trainings-Verwaltung (alte Overview-Seite wurde entfernt)"""
    return redirect(url_for('admin.admin_trainings'))

@bp.route('/admin/trainings')
@admin_required
def admin_trainings():
    """Alle Trainings in einer Ansicht: Templates, Einmalig, Angepasst"""
    q = request.args.get('q', '').strip()
    type_filter = request.args.get('type', 'all')
    include_ended = request.args.get('include_ended') == '1'
    today = date.today()
    
    # Templates - sortiert nach start_date absteigend (neueste zuerst)
    trainings_query = _scoped_training_query(is_hidden=False)
    if q:
        trainings_query = trainings_query.filter(Training.name.ilike(f"%{q}%"))
    if not include_ended:
        trainings_query = trainings_query.filter(Training.end_date >= today)
    trainings = trainings_query.order_by(Training.start_date.desc()).all() if type_filter in ['all', 'template'] else []
    
    # Einmalig - sortiert nach start_date absteigend (neueste zuerst)
    hidden_query = _scoped_training_query(is_hidden=True)
    if q:
        hidden_query = hidden_query.filter(Training.name.ilike(f"%{q}%"))
    if not include_ended:
        hidden_query = hidden_query.filter(Training.start_date >= today)
    hidden_trainings = hidden_query.order_by(Training.start_date.desc()).all() if type_filter in ['all', 'hidden'] else []
    
    # Angepasst - sortiert nach date absteigend (neueste zuerst)
    instances_query = TrainingInstance.query.join(Training).filter(Training.team_code == get_active_team_code())
    if q:
        instances_query = instances_query.filter(Training.name.ilike(f"%{q}%"))
    if not include_ended:
        instances_query = instances_query.filter(TrainingInstance.date >= today)
    instances = instances_query.order_by(TrainingInstance.date.desc()).all() if type_filter in ['all', 'instance'] else []
    
    return render_template('admin_trainings.html', 
                         trainings=trainings,
                         hidden_trainings=hidden_trainings,
                         instances=instances,
                         weekdays=WEEKDAYS,
                         date=date)

@bp.route('/admin/trainings/partial')
@admin_required
def trainings_partial():
    """HTMX Partial für Trainings-Filter"""
    q = request.args.get('q', '').strip()
    type_filter = request.args.get('type', 'all')
    include_ended = request.args.get('include_ended') == '1'
    today = date.today()
    
    trainings_query = _scoped_training_query(is_hidden=False)
    if q:
        trainings_query = trainings_query.filter(Training.name.ilike(f"%{q}%"))
    if not include_ended:
        trainings_query = trainings_query.filter(Training.end_date >= today)
    trainings = trainings_query.order_by(Training.start_date.desc()).all() if type_filter in ['all', 'template'] else []
    
    hidden_query = _scoped_training_query(is_hidden=True)
    if q:
        hidden_query = hidden_query.filter(Training.name.ilike(f"%{q}%"))
    if not include_ended:
        hidden_query = hidden_query.filter(Training.start_date >= today)
    hidden_trainings = hidden_query.order_by(Training.start_date.desc()).all() if type_filter in ['all', 'hidden'] else []
    
    instances_query = TrainingInstance.query.join(Training).filter(Training.team_code == get_active_team_code())
    if q:
        instances_query = instances_query.filter(Training.name.ilike(f"%{q}%"))
    if not include_ended:
        instances_query = instances_query.filter(TrainingInstance.date >= today)
    instances = instances_query.order_by(TrainingInstance.date.desc()).all() if type_filter in ['all', 'instance'] else []
    
    return render_template('includes/all_trainings_table.html', 
                         trainings=trainings,
                         hidden_trainings=hidden_trainings,
                         instances=instances,
                         weekdays=WEEKDAYS,
                         date=date)

@bp.route('/admin/activity-types', methods=['GET', 'POST'])
@admin_required
def admin_activity_types():
    activity_types = ActivityType.query.order_by(ActivityType.sort_order).all()
    if request.method == 'POST':
        for activity_type in activity_types:
            activity_type.label = request.form.get(f'label_{activity_type.key}', activity_type.label).strip()
            activity_type.behavior = request.form.get(f'behavior_{activity_type.key}', activity_type.behavior).strip()
            activity_type.badge_class = request.form.get(f'badge_class_{activity_type.key}', activity_type.badge_class).strip()
            light = sanitize_color(request.form.get(f'light_color_{activity_type.key}', ''))
            dark = sanitize_color(request.form.get(f'dark_color_{activity_type.key}', ''))
            if light:
                activity_type.light_color = light
            if dark:
                activity_type.dark_color = dark
            sort_order = request.form.get(f'sort_order_{activity_type.key}', str(activity_type.sort_order)).strip()
            if sort_order.isdigit():
                activity_type.sort_order = int(sort_order)
        db.session.commit()
        flash('Aktivitätstypen aktualisiert.', 'success')
        return redirect(url_for('admin.admin_activity_types'))
    return render_template('admin_activity_types_standalone.html', activity_types=activity_types)


@bp.route('/admin/agenda-categories', methods=['GET', 'POST'])
@admin_required
def admin_agenda_categories():
    categories = AgendaCategory.query.order_by(AgendaCategory.sort_order, AgendaCategory.id).all()
    audience_options = [
        ('player', 'Spieler'),
        ('coach', 'Betreuer / Coach'),
        ('team_manager', 'Teammanager'),
    ]
    if request.method == 'POST':
        for category in categories:
            category.label = (request.form.get(f'label_{category.key}') or category.label).strip()
            category.icon = (request.form.get(f'icon_{category.key}') or category.icon).strip()
            category.attendance_required_for = request.form.getlist(f'required_{category.key}')
            category.attendance_allowed_for = request.form.getlist(f'allowed_{category.key}')
            category.show_presence_tracking = request.form.get(f'presence_{category.key}') == 'on'
        db.session.commit()
        flash('Agenda-Kategorien und Anmeldeprofile aktualisiert.', 'success')
        return redirect(url_for('admin.admin_agenda_categories'))
    return render_template(
        'admin_agenda_categories.html',
        categories=categories,
        audience_options=audience_options,
    )

@bp.route('/admin/backup', methods=['GET'])
@admin_required
def admin_backup():
    """Hinweis auf das zentrale Backup im tt-infra-Service"""
    db_backend_label = get_database_backend_label(get_database_backend())
    return render_template(
        'admin_backup_standalone.html',
        db_backend_label=db_backend_label,
    )

@bp.route('/admin/hidden-trainings/new', methods=['GET', 'POST'])
@admin_required
def new_hidden_training():
    if request.method == 'POST':
        ok, errors = validate_hidden_training_form(request.form)
        if not ok:
            for field_errors in errors.values():
                for msg in field_errors:
                    flash(msg, 'danger')
            return render_template('hidden_training_form.html')
        date_value = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        training = Training(
            team_code=get_active_team_code(),
            name=request.form['name'],
            category=request.form.get('category', 'training'),
            participation_rules_json=_participation_overrides(request.form),
            weekday=date_value.weekday(),
            start_date=date_value,
            end_date=date_value,
            start_time=datetime.strptime(request.form['start_time'], '%H:%M').time(),
            is_hidden=True
        )
        db.session.add(training)
        db.session.commit()
        flash('Einmaliges Training erstellt!', 'success')
        return redirect(url_for('admin.edit_hidden_training', id=training.id))
    return render_template('hidden_training_form.html')

@bp.route('/admin/hidden-trainings/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_hidden_training(id):
    training = _team_scoped_training_or_404(id)
    if request.method == 'POST':
        ok, errors = validate_hidden_training_form(request.form)
        if not ok:
            for field_errors in errors.values():
                for msg in field_errors:
                    flash(msg, 'danger')
            activities = Activity.query.filter_by(training_id=id).order_by(Activity.order_index).all()
            return render_template('hidden_training_edit.html', training=training, activities=activities)
        date_value = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        training.name = request.form['name']
        training.category = request.form.get('category', 'training')
        training.participation_rules_json = _participation_overrides(request.form)
        training.weekday = date_value.weekday()
        training.start_date = date_value
        training.end_date = date_value
        training.start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
        training.is_hidden = True
        db.session.commit()
        recalculate_times(id)
        flash('Einmaliges Training aktualisiert!', 'success')
        return redirect(url_for('admin.edit_hidden_training', id=id))

    activities = Activity.query.filter_by(training_id=id).order_by(Activity.order_index).all()
    return render_template('hidden_training_edit.html', training=training, activities=activities)

@bp.route('/admin/hidden-trainings/<int:id>/delete', methods=['POST'])
@admin_required
def delete_hidden_training(id):
    training = _team_scoped_training_or_404(id)
    db.session.delete(training)
    db.session.commit()
    flash('Einmaliges Training gelöscht!', 'success')
    return redirect(url_for('admin.admin_trainings'))

@bp.route('/admin/backup/download', methods=['GET'])
@admin_required
def admin_backup_download():
    flash('Der direkte Datenbank-Download ist entfernt. Bitte nutze das zentrale Backup im tt-infra-Service.', 'warning')
    return redirect(url_for('admin.admin_backup'))

@bp.route('/admin/backup/restore', methods=['POST'])
@admin_required
def admin_backup_restore():
    flash('Der In-App-Restore ist entfernt. Bitte spiele Backups zentral im tt-infra-Service ein.', 'warning')
    return redirect(url_for('admin.admin_backup'))

@bp.route('/training/new', methods=['GET', 'POST'])
@admin_required
def new_training():
    if request.method == 'POST':
        ok, errors = validate_training_form(request.form)
        if not ok:
            for field_errors in errors.values():
                for msg in field_errors:
                    flash(msg, 'danger')
            return render_template('training_form.html', weekdays=WEEKDAYS)
        training = Training(
            team_code=get_active_team_code(),
            name=request.form['name'],
            category=request.form.get('category', 'training'),
            participation_rules_json=_participation_overrides(request.form),
            weekday=int(request.form['weekday']),
            start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d').date(),
            start_time=datetime.strptime(request.form['start_time'], '%H:%M').time()
        )
        db.session.add(training)
        db.session.commit()
        flash('Training erfolgreich erstellt!', 'success')
        return redirect(url_for('admin.edit_training', id=training.id))
    return render_template('training_form.html', weekdays=WEEKDAYS)

@bp.route('/training/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_training(id):
    training = _team_scoped_training_or_404(id)
    if training.is_hidden:
        return redirect(url_for('admin.edit_hidden_training', id=id))
    if request.method == 'POST':
        ok, errors = validate_training_form(request.form)
        if not ok:
            for field_errors in errors.values():
                for msg in field_errors:
                    flash(msg, 'danger')
            activities = Activity.query.filter_by(training_id=id).order_by(Activity.order_index).all()
            instances = TrainingInstance.query.filter_by(training_id=id).order_by(TrainingInstance.date.asc()).all()
            return render_template('training_edit.html', training=training, activities=activities, instances=instances, activities_json=json.dumps([]), weekdays=WEEKDAYS, position_groups=POSITION_GROUPS)
        old_start_time = training.start_time
        new_start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
        
        training.name = request.form['name']
        training.category = request.form.get('category', 'training')
        training.participation_rules_json = _participation_overrides(request.form)
        training.weekday = int(request.form['weekday'])
        training.start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        training.end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        training.start_time = new_start_time
        db.session.commit()
        
        if old_start_time != new_start_time:
            recalculate_times(id)
            flash('Training und Aktivitätszeiten erfolgreich aktualisiert!', 'success')
        else:
            flash('Training erfolgreich aktualisiert!', 'success')
        
        return redirect(url_for('admin.edit_training', id=id))
    activities = Activity.query.filter_by(training_id=id).order_by(Activity.order_index).all()
    instances = TrainingInstance.query.filter_by(training_id=id).order_by(TrainingInstance.date.asc()).all()
    activities_json = [{
        'id': a.id,
        'activity_type': a.activity_type,
        'duration': a.duration,
        'position_groups': a.position_groups,
        'topic': a.topic,
        'topics_json': a.topics_json,
        'color': a.color if hasattr(a, 'color') and a.color else get_activity_color(a.activity_type, 'light')
    } for a in activities]
    return render_template('training_edit.html', training=training, activities=activities, instances=instances, activities_json=json.dumps(activities_json), weekdays=WEEKDAYS, position_groups=POSITION_GROUPS)

def _parse_instance_date(training):
    date_str = request.form.get('date')
    if not date_str:
        flash('Datum fehlt.', 'warning')
        return None
    try:
        instance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Ungültiges Datum.', 'danger')
        return None
    if instance_date.weekday() != training.weekday:
        flash('Datum passt nicht zum Wochentag des Trainings.', 'warning')
        return None
    if not (training.start_date <= instance_date <= training.end_date):
        flash('Datum liegt außerhalb des Trainingszeitraums.', 'warning')
        return None
    return instance_date

def _next_available_instance_date(training_id, base_date, max_weeks=260):
    candidate = base_date + timedelta(days=7)
    for _ in range(max_weeks):
        exists = TrainingInstance.query.filter_by(training_id=training_id, date=candidate).first()
        if not exists:
            return candidate
        candidate += timedelta(days=7)
    return None

@bp.route('/training/<int:id>/instance/create', methods=['POST'])
@admin_required
def create_training_instance(id):
    training = _team_scoped_training_or_404(id)
    instance_date = _parse_instance_date(training)
    if not instance_date:
        return redirect(training_edit_url(training))

    existing = TrainingInstance.query.filter_by(training_id=id, date=instance_date).first()
    if existing:
        if existing.status == 'cancelled':
            existing.status = 'active'
            if not existing.activities:
                template_activities = Activity.query.filter_by(training_id=id).order_by(Activity.order_index).all()
                for activity in template_activities:
                    copied = ActivityInstance(
                        training_instance_id=existing.id,
                        activity_type=activity.activity_type,
                        start_time=activity.start_time,
                        duration=activity.duration,
                        position_groups=activity.position_groups,
                        topic=activity.topic,
                        order_index=activity.order_index,
                        topics_json=activity.topics_json,
                        color=activity.color
                    )
                    db.session.add(copied)
            db.session.commit()
            flash('Angepasster Termin reaktiviert.', 'success')
        else:
            flash('Angepasster Termin existiert bereits.', 'warning')
        return redirect(url_for('admin.edit_training_instance', id=existing.id))

    instance = TrainingInstance(
        training_id=id,
        date=instance_date,
        status='active',
        start_time=training.start_time
    )
    db.session.add(instance)
    db.session.flush()

    template_activities = Activity.query.filter_by(training_id=id).order_by(Activity.order_index).all()
    for activity in template_activities:
        copied = ActivityInstance(
            training_instance_id=instance.id,
            activity_type=activity.activity_type,
            start_time=activity.start_time,
            duration=activity.duration,
            position_groups=activity.position_groups,
            topic=activity.topic,
            order_index=activity.order_index,
            topics_json=activity.topics_json,
            color=activity.color
        )
        db.session.add(copied)

    db.session.commit()
    flash('Angepasster Termin erstellt.', 'success')
    return redirect(url_for('admin.edit_training_instance', id=instance.id))

@bp.route('/training/<int:id>/instance/cancel', methods=['POST'])
@admin_required
def cancel_training_instance(id):
    training = _team_scoped_training_or_404(id)
    instance_date = _parse_instance_date(training)
    if not instance_date:
        return redirect(training_edit_url(training))

    instance = TrainingInstance.query.filter_by(training_id=id, date=instance_date).first()
    if instance:
        instance.status = 'cancelled'
    else:
        instance = TrainingInstance(
            training_id=id,
            date=instance_date,
            status='cancelled',
            start_time=training.start_time
        )
        db.session.add(instance)

    db.session.commit()
    flash('Termin abgesagt.', 'success')
    return redirect(training_edit_url(training))

@bp.route('/training/instance/<int:id>/delete', methods=['POST'])
@admin_required
def delete_training_instance(id):
    instance = _team_scoped_instance_or_404(id)
    training = instance.training
    db.session.delete(instance)
    db.session.commit()
    flash('Angepasster Termin entfernt.', 'success')
    return redirect(training_edit_url(training))

@bp.route('/training/instance/<int:id>/edit', methods=['GET'])
@admin_required
def edit_training_instance(id):
    instance = _team_scoped_instance_or_404(id)
    activities = ActivityInstance.query.filter_by(training_instance_id=id).order_by(ActivityInstance.order_index).all()
    return render_template('training_instance_edit.html', training=instance.training, instance=instance, activities=activities, weekdays=WEEKDAYS, position_groups=POSITION_GROUPS)

@bp.route('/training/instance/<int:instance_id>/activity/add', methods=['GET', 'POST'])
@admin_required
def add_instance_activity(instance_id):
    instance = _team_scoped_instance_or_404(instance_id)
    if request.method == 'POST':
        activity_type = request.form.get('activity_type')
        duration = int(request.form.get('duration', 60))
        color = get_activity_color(activity_type, 'light')

        max_order = db.session.query(db.func.max(ActivityInstance.order_index)).filter_by(training_instance_id=instance_id).scalar() or -1

        if max_order == -1:
            if activity_type == 'prepractice':
                start_datetime = datetime.combine(datetime.today(), instance.start_time)
                start_datetime -= timedelta(minutes=duration)
                start_time = start_datetime.time()
            else:
                start_time = instance.start_time
        else:
            last_activity = ActivityInstance.query.filter_by(training_instance_id=instance_id).order_by(ActivityInstance.order_index.desc()).first()
            start_datetime = datetime.combine(datetime.today(), last_activity.start_time)
            start_datetime += timedelta(minutes=last_activity.duration)
            start_time = start_datetime.time()

        topics_json = None
        position_groups = []

        behavior = get_activity_behavior(activity_type)
        if behavior == 'team':
            position_groups = POSITION_GROUPS
            topic = request.form.get('topic', '')
        elif behavior == 'individual':
            position_groups = POSITION_GROUPS
            mode = request.form.get('individual_mode', 'same')
            topics_per_group = {}
            if mode == 'same':
                common_topic = request.form.get('individual_common_topic', '')
                for group in POSITION_GROUPS:
                    topics_per_group[group] = common_topic
            else:
                for group in POSITION_GROUPS:
                    topics_per_group[group] = request.form.get(f'individual_topic_{group}', '')
            topics_json = topics_per_group
            topic = None
        elif behavior == 'group':
            combinations = []
            all_selected_groups = set()
            i = 0
            max_iterations = 100
            found_any = False

            while i < max_iterations:
                combo_groups = request.form.getlist(f'combo_{i}_groups')
                combo_topic = request.form.get(f'combo_{i}_topic', '').strip()

                if not combo_groups and not combo_topic:
                    if found_any:
                        break
                    i += 1
                    continue

                found_any = True

                if combo_groups and combo_topic:
                    combinations.append({'groups': combo_groups, 'topic': combo_topic})
                    all_selected_groups.update(combo_groups)

                i += 1

            position_groups = list(all_selected_groups) if all_selected_groups else []
            topics_json = combinations if combinations else None
            topic = None

        activity = ActivityInstance(
            training_instance_id=instance_id,
            activity_type=activity_type,
            start_time=start_time,
            duration=duration,
            position_groups=position_groups,
            topic=topic,
            order_index=max_order + 1,
            topics_json=topics_json,
            color=color
        )
        db.session.add(activity)
        db.session.commit()

        recalculate_instance_times(instance_id)
        flash('Aktivität erfolgreich hinzugefügt!', 'success')
        return redirect(url_for('admin.edit_training_instance', id=instance_id))

    return render_template('activity_form.html', training=instance.training, instance=instance, activity=None, position_groups=POSITION_GROUPS, individual_mode_same=True, individual_common_topic='', individual_topics={})

@bp.route('/training/instance/activity/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_instance_activity(id):
    activity = db.get_or_404(ActivityInstance, id)
    instance = activity.training_instance
    training = instance.training
    if training.team_code != get_active_team_code():
        abort(404)

    individual_mode_same = True
    individual_common_topic = ''
    individual_topics = {}
    if activity and get_activity_behavior(activity.activity_type) == 'individual' and activity.topics_json:
        topics = activity.topics_json
        if isinstance(topics, dict):
            individual_topics = topics
            topic_values = list(topics.values())
            if topic_values:
                first_topic = topic_values[0]
                individual_mode_same = all(t == first_topic for t in topic_values)
                individual_common_topic = first_topic if individual_mode_same else ''

    if request.method == 'POST':
        activity_type = request.form.get('activity_type')
        duration = int(request.form.get('duration', 60))

        topics_json = None
        position_groups = []

        behavior = get_activity_behavior(activity_type)
        if behavior == 'team':
            position_groups = POSITION_GROUPS
            activity.topic = request.form.get('topic', '')
        elif behavior == 'individual':
            position_groups = POSITION_GROUPS
            mode = request.form.get('individual_mode', 'same')
            topics_per_group = {}
            if mode == 'same':
                common_topic = request.form.get('individual_common_topic', '')
                for group in POSITION_GROUPS:
                    topics_per_group[group] = common_topic
            else:
                for group in POSITION_GROUPS:
                    topics_per_group[group] = request.form.get(f'individual_topic_{group}', '')
            topics_json = topics_per_group
            activity.topic = None
        elif behavior == 'group':
            combinations = []
            all_selected_groups = set()
            combo_count = int(request.form.get('combo_count', 0))
            max_iterations = max(combo_count + 5, 100)
            found_any = False

            i = 0
            while i < max_iterations:
                combo_groups = request.form.getlist(f'combo_{i}_groups')
                combo_topic = request.form.get(f'combo_{i}_topic', '').strip()

                if not combo_groups and not combo_topic:
                    if found_any and i >= combo_count:
                        break
                    i += 1
                    continue

                found_any = True

                if combo_groups and combo_topic:
                    combinations.append({'groups': combo_groups, 'topic': combo_topic})
                    all_selected_groups.update(combo_groups)

                i += 1

            position_groups = list(all_selected_groups) if all_selected_groups else []
            topics_json = combinations if combinations else None
            activity.topic = None

        activity.activity_type = activity_type
        activity.duration = duration
        activity.position_groups = position_groups
        activity.topics_json = topics_json
        activity.color = get_activity_color(activity_type, 'light')

        db.session.commit()
        recalculate_instance_times(instance.id)
        flash('Aktivität erfolgreich aktualisiert!', 'success')
        return redirect(url_for('admin.edit_training_instance', id=instance.id))

    return render_template('activity_form.html', training=training, instance=instance, activity=activity, position_groups=POSITION_GROUPS, individual_mode_same=individual_mode_same, individual_common_topic=individual_common_topic, individual_topics=individual_topics)

@bp.route('/training/instance/activity/<int:id>/delete', methods=['POST'])
@admin_required
def delete_instance_activity(id):
    activity = db.get_or_404(ActivityInstance, id)
    if activity.training_instance.training.team_code != get_active_team_code():
        abort(404)
    instance_id = activity.training_instance_id

    db.session.delete(activity)
    db.session.commit()

    recalculate_instance_times(instance_id)
    flash('Aktivität erfolgreich gelöscht!', 'success')

    return redirect(url_for('admin.edit_training_instance', id=instance_id))

@bp.route('/training/instance/activity/<int:id>/move_up', methods=['POST'])
@admin_required
def move_instance_activity_up(id):
    activity = db.get_or_404(ActivityInstance, id)
    if activity.training_instance.training.team_code != get_active_team_code():
        abort(404)
    instance_id = activity.training_instance_id

    prev_activity = ActivityInstance.query.filter(
        ActivityInstance.training_instance_id == instance_id,
        ActivityInstance.order_index < activity.order_index
    ).order_by(ActivityInstance.order_index.desc()).first()

    if prev_activity:
        activity.order_index, prev_activity.order_index = prev_activity.order_index, activity.order_index
        db.session.commit()
        recalculate_instance_times(instance_id)
        flash('Aktivität nach oben verschoben', 'success')
    else:
        activities = ActivityInstance.query.filter_by(training_instance_id=instance_id).order_by(ActivityInstance.order_index).all()
        for i, act in enumerate(activities):
            act.order_index = i
        db.session.commit()

    return redirect(url_for('admin.edit_training_instance', id=instance_id))

@bp.route('/training/instance/activity/<int:id>/move_down', methods=['POST'])
@admin_required
def move_instance_activity_down(id):
    activity = db.get_or_404(ActivityInstance, id)
    if activity.training_instance.training.team_code != get_active_team_code():
        abort(404)
    instance_id = activity.training_instance_id

    next_activity = ActivityInstance.query.filter(
        ActivityInstance.training_instance_id == instance_id,
        ActivityInstance.order_index > activity.order_index
    ).order_by(ActivityInstance.order_index.asc()).first()

    if next_activity:
        activity.order_index, next_activity.order_index = next_activity.order_index, activity.order_index
        db.session.commit()
        recalculate_instance_times(instance_id)
        flash('Aktivität nach unten verschoben', 'success')
    else:
        activities = ActivityInstance.query.filter_by(training_instance_id=instance_id).order_by(ActivityInstance.order_index).all()
        for i, act in enumerate(activities):
            act.order_index = i
        db.session.commit()

    return redirect(url_for('admin.edit_training_instance', id=instance_id))

@bp.route('/training/<int:id>/delete', methods=['POST'])
@admin_required
def delete_training(id):
    training = _team_scoped_training_or_404(id)
    db.session.delete(training)
    db.session.commit()
    flash('Training erfolgreich gelöscht!', 'success')
    return redirect(url_for('main.index'))

@bp.route('/training/<int:id>/copy', methods=['POST'])
@admin_required
def copy_training(id):
    original_training = _team_scoped_training_or_404(id)
    
    new_training = Training(
        team_code=get_active_team_code(),
        name=f"{original_training.name} (Kopie)",
        category=original_training.category,
        weekday=original_training.weekday,
        start_date=original_training.start_date,
        end_date=original_training.end_date,
        start_time=original_training.start_time
    )
    db.session.add(new_training)
    db.session.flush()
    
    original_activities = Activity.query.filter_by(training_id=id).order_by(Activity.order_index).all()
    for activity in original_activities:
        new_activity = Activity(
            training_id=new_training.id,
            activity_type=activity.activity_type,
            start_time=activity.start_time,
            duration=activity.duration,
            position_groups=activity.position_groups,
            topic=activity.topic,
            order_index=activity.order_index,
            topics_json=activity.topics_json,
            color=activity.color
        )
        db.session.add(new_activity)
    
    db.session.commit()
    flash(f'Training "{original_training.name}" wurde erfolgreich kopiert!', 'success')
    return redirect(url_for('admin.admin_trainings'))

@bp.route('/hidden-training/<int:id>/copy', methods=['POST'])
@admin_required
def copy_hidden_training(id):
    """Kopiert ein einmaliges Training"""
    original_training = _team_scoped_training_or_404(id)
    
    new_training = Training(
        team_code=get_active_team_code(),
        name=f"{original_training.name} (Kopie)",
        category=original_training.category,
        weekday=original_training.weekday,
        start_date=original_training.start_date,
        end_date=original_training.end_date,
        start_time=original_training.start_time,
        is_hidden=True
    )
    db.session.add(new_training)
    db.session.flush()
    
    original_activities = Activity.query.filter_by(training_id=id).order_by(Activity.order_index).all()
    for activity in original_activities:
        new_activity = Activity(
            training_id=new_training.id,
            activity_type=activity.activity_type,
            start_time=activity.start_time,
            duration=activity.duration,
            position_groups=activity.position_groups,
            topic=activity.topic,
            order_index=activity.order_index,
            topics_json=activity.topics_json,
            color=activity.color
        )
        db.session.add(new_activity)
    
    db.session.commit()
    flash(f'Einmaliges Training "{original_training.name}" wurde erfolgreich kopiert!', 'success')
    return redirect(url_for('admin.admin_trainings'))

@bp.route('/training-instance/<int:id>/copy', methods=['POST'])
@admin_required
def copy_training_instance(id):
    """Kopiert eine angepasste Trainingsinstanz"""
    original_instance = _team_scoped_instance_or_404(id)
    next_date = _next_available_instance_date(original_instance.training_id, original_instance.date)
    if not next_date:
        flash('Kein freier Termin zum Kopieren gefunden.', 'danger')
        return redirect(url_for('admin.admin_trainings'))
    
    new_instance = TrainingInstance(
        training_id=original_instance.training_id,
        date=next_date,
        start_time=original_instance.start_time,
        status=original_instance.status
    )
    db.session.add(new_instance)
    db.session.flush()
    
    original_activities = ActivityInstance.query.filter_by(training_instance_id=id).order_by(ActivityInstance.order_index).all()
    for activity in original_activities:
        new_activity = ActivityInstance(
            training_instance_id=new_instance.id,
            activity_type=activity.activity_type,
            start_time=activity.start_time,
            duration=activity.duration,
            position_groups=activity.position_groups,
            topic=activity.topic,
            order_index=activity.order_index,
            topics_json=activity.topics_json,
            color=activity.color
        )
        db.session.add(new_activity)
    
    db.session.commit()
    flash(f'Angepasster Termin für "{original_instance.training.name}" wurde erfolgreich auf {next_date.strftime("%d.%m.%Y")} kopiert!', 'success')
    return redirect(url_for('admin.admin_trainings'))

@bp.route('/activity/add', methods=['GET', 'POST'])
@admin_required
def add_activity():
    training_id_raw = request.args.get('training_id') or (request.form.get('training_id') if request.method == 'POST' else None)
    try:
        training_id = int(training_id_raw) if training_id_raw is not None else None
    except (TypeError, ValueError):
        training_id = None

    if not training_id:
        flash('Training-ID fehlt', 'error')
        return redirect(url_for('main.index'))
    
    training = _team_scoped_training_or_404(training_id)
    
    if request.method == 'POST':
        activity_type = request.form.get('activity_type')
        duration = int(request.form.get('duration', 60))
        color = get_activity_color(activity_type, 'light')
        
        max_order = db.session.query(db.func.max(Activity.order_index)).filter_by(training_id=training_id).scalar() or -1

        if max_order == -1:
            if activity_type == 'prepractice':
                start_datetime = datetime.combine(datetime.today(), training.start_time)
                start_datetime -= timedelta(minutes=duration)
                start_time = start_datetime.time()
            else:
                start_time = training.start_time
        else:
            last_activity = Activity.query.filter_by(training_id=training_id).order_by(Activity.order_index.desc()).first()
            start_datetime = datetime.combine(datetime.today(), last_activity.start_time)
            start_datetime += timedelta(minutes=last_activity.duration)
            start_time = start_datetime.time()

        topics_json = None
        position_groups = []
        
        behavior = get_activity_behavior(activity_type)
        if behavior == 'team':
            position_groups = POSITION_GROUPS
            topic = request.form.get('topic', '')
        elif behavior == 'individual':
            position_groups = POSITION_GROUPS
            mode = request.form.get('individual_mode', 'same')
            topics_per_group = {}
            if mode == 'same':
                common_topic = request.form.get('individual_common_topic', '')
                for group in POSITION_GROUPS:
                    topics_per_group[group] = common_topic
            else:
                for group in POSITION_GROUPS:
                    topics_per_group[group] = request.form.get(f'individual_topic_{group}', '')
            topics_json = topics_per_group
            topic = None
        elif behavior == 'group':
            combinations = []
            all_selected_groups = set()
            i = 0
            max_iterations = 100
            found_any = False
            
            while i < max_iterations:
                combo_groups = request.form.getlist(f'combo_{i}_groups')
                combo_topic = request.form.get(f'combo_{i}_topic', '').strip()
                
                if not combo_groups and not combo_topic:
                    if found_any:
                        break
                    i += 1
                    continue
                
                found_any = True
                
                if combo_groups and combo_topic:
                    combinations.append({'groups': combo_groups, 'topic': combo_topic})
                    all_selected_groups.update(combo_groups)
                
                i += 1
            
            position_groups = list(all_selected_groups) if all_selected_groups else []
            topics_json = combinations if combinations else None
            topic = None

        activity = Activity(
            training_id=training_id,
            activity_type=activity_type,
            start_time=start_time,
            duration=duration,
            position_groups=position_groups,
            topic=topic,
            order_index=max_order + 1,
            topics_json=topics_json,
            color=color
        )
        db.session.add(activity)
        db.session.commit()

        recalculate_times(training_id)
        flash('Aktivität erfolgreich hinzugefügt!', 'success')
        return redirect(training_edit_url(training))
    
    return render_template('activity_form.html', training=training, training_edit_url=training_edit_url(training), activity=None, position_groups=POSITION_GROUPS, individual_mode_same=True, individual_common_topic='', individual_topics={})

@bp.route('/activity/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_activity(id):
    activity = db.get_or_404(Activity, id)
    training = activity.training
    if training.team_code != get_active_team_code():
        abort(404)
    
    individual_mode_same = True
    individual_common_topic = ''
    individual_topics = {}
    if activity and get_activity_behavior(activity.activity_type) == 'individual' and activity.topics_json:
        topics = activity.topics_json
        if isinstance(topics, dict):
            individual_topics = topics
            topic_values = list(topics.values())
            if topic_values:
                first_topic = topic_values[0]
                individual_mode_same = all(t == first_topic for t in topic_values)
                individual_common_topic = first_topic if individual_mode_same else ''
    
    if request.method == 'POST':
        activity_type = request.form.get('activity_type')
        duration = int(request.form.get('duration', 60))
        
        topics_json = None
        position_groups = []
        
        behavior = get_activity_behavior(activity_type)
        if behavior == 'team':
            position_groups = POSITION_GROUPS
            activity.topic = request.form.get('topic', '')
        elif behavior == 'individual':
            position_groups = POSITION_GROUPS
            mode = request.form.get('individual_mode', 'same')
            topics_per_group = {}
            if mode == 'same':
                common_topic = request.form.get('individual_common_topic', '')
                for group in POSITION_GROUPS:
                    topics_per_group[group] = common_topic
            else:
                for group in POSITION_GROUPS:
                    topics_per_group[group] = request.form.get(f'individual_topic_{group}', '')
            topics_json = topics_per_group
            activity.topic = None
        elif behavior == 'group':
            combinations = []
            all_selected_groups = set()
            combo_count = int(request.form.get('combo_count', 0))
            max_iterations = max(combo_count + 5, 100)
            found_any = False
            
            i = 0
            while i < max_iterations:
                combo_groups = request.form.getlist(f'combo_{i}_groups')
                combo_topic = request.form.get(f'combo_{i}_topic', '').strip()
                
                if not combo_groups and not combo_topic:
                    if found_any and i >= combo_count:
                        break
                    i += 1
                    continue
                
                found_any = True
                
                if combo_groups and combo_topic:
                    combinations.append({'groups': combo_groups, 'topic': combo_topic})
                    all_selected_groups.update(combo_groups)
                
                i += 1
            
            position_groups = list(all_selected_groups) if all_selected_groups else []
            topics_json = combinations if combinations else None
            activity.topic = None

        activity.activity_type = activity_type
        activity.duration = duration
        activity.position_groups = position_groups
        activity.topics_json = topics_json
        activity.color = get_activity_color(activity_type, 'light')

        db.session.commit()
        recalculate_times(activity.training_id)
        flash('Aktivität erfolgreich aktualisiert!', 'success')
        return redirect(training_edit_url(training))
    
    return render_template('activity_form.html', training=training, training_edit_url=training_edit_url(training), activity=activity, position_groups=POSITION_GROUPS, individual_mode_same=individual_mode_same, individual_common_topic=individual_common_topic, individual_topics=individual_topics)

@bp.route('/activity/<int:id>/update', methods=['POST'])
@admin_required
def update_activity(id):
    activity = db.get_or_404(Activity, id)
    if activity.training.team_code != get_active_team_code():
        abort(404)
    data = request.json

    activity.activity_type = data['activity_type']
    activity.duration = int(data['duration'])
    activity.position_groups = data['position_groups']
    activity.topic = data.get('topic', '')
    activity.color = data.get('color', activity.color if hasattr(activity, 'color') else '#10b981')

    topics_json = None
    behavior = get_activity_behavior(data['activity_type'])
    if behavior == 'individual':
        topics_json = data.get('topics_per_group', {})
    elif behavior == 'group':
        topics_json = data.get('group_combinations', [])
    activity.topics_json = topics_json

    db.session.commit()
    recalculate_times(activity.training_id)

    return jsonify({'success': True})

@bp.route('/activity/reorder', methods=['POST'])
@admin_required
def reorder_activities():
    data = request.json
    training_id = data['training_id']
    activity_ids = data['activity_ids']

    training = _team_scoped_training_or_404(training_id)

    for index, activity_id in enumerate(activity_ids):
        activity = db.session.get(Activity, activity_id)
        if activity:
            activity.order_index = index

    db.session.commit()
    recalculate_times(training.id)

    return jsonify({'success': True})

@bp.route('/activity/<int:id>/delete', methods=['POST'])
@admin_required
def delete_activity(id):
    activity = db.get_or_404(Activity, id)
    if activity.training.team_code != get_active_team_code():
        abort(404)
    training_id = activity.training_id
    training = activity.training  # Referenz vor dem Löschen sichern

    db.session.delete(activity)
    db.session.commit()

    recalculate_times(training_id)
    flash('Aktivität erfolgreich gelöscht!', 'success')

    if request.is_json:
        return jsonify({'success': True})
    return redirect(training_edit_url(training))

@bp.route('/activity/<int:id>/move_up', methods=['POST'])
@admin_required
def move_activity_up(id):
    activity = db.get_or_404(Activity, id)
    if activity.training.team_code != get_active_team_code():
        abort(404)
    training_id = activity.training_id
    
    # Finde die Aktivität, die direkt vor der aktuellen liegt (höchster order_index kleiner als aktueller)
    prev_activity = Activity.query.filter(
        Activity.training_id == training_id,
        Activity.order_index < activity.order_index
    ).order_by(Activity.order_index.desc()).first()
    
    if prev_activity:
        # Tausche order_index
        activity.order_index, prev_activity.order_index = prev_activity.order_index, activity.order_index
        db.session.commit()
        recalculate_times(training_id)
        flash('Aktivität nach oben verschoben', 'success')
    else:
        # Fallback: Wenn wir ganz oben sind oder die Indizes kaputt sind, reparieren wir sie
        activities = Activity.query.filter_by(training_id=training_id).order_by(Activity.order_index).all()
        for i, act in enumerate(activities):
            act.order_index = i
        db.session.commit()
    
    return redirect(training_edit_url(activity.training))

@bp.route('/activity/<int:id>/move_down', methods=['POST'])
@admin_required
def move_activity_down(id):
    activity = db.get_or_404(Activity, id)
    if activity.training.team_code != get_active_team_code():
        abort(404)
    training_id = activity.training_id
    
    # Finde die Aktivität, die direkt nach der aktuellen liegt (kleinster order_index größer als aktueller)
    next_activity = Activity.query.filter(
        Activity.training_id == training_id,
        Activity.order_index > activity.order_index
    ).order_by(Activity.order_index.asc()).first()
    
    if next_activity:
        # Tausche order_index
        activity.order_index, next_activity.order_index = next_activity.order_index, activity.order_index
        db.session.commit()
        recalculate_times(training_id)
        flash('Aktivität nach unten verschoben', 'success')
    else:
        # Fallback: Indizes reparieren
        activities = Activity.query.filter_by(training_id=training_id).order_by(Activity.order_index).all()
        for i, act in enumerate(activities):
            act.order_index = i
        db.session.commit()
    
    return redirect(training_edit_url(activity.training))
