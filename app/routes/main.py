from flask import Blueprint, render_template, request, session, current_app
from datetime import datetime
from ..models import Training, Activity, TrainingInstance, ActivityInstance
from ..extensions import db
from ..utils import login_required, get_active_team_code, get_current_training_status, get_upcoming_trainings, get_timeline_from_activities, load_training_data, WEEKDAYS, POSITION_GROUPS
import logging
import requests

bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)


@bp.route('/health')
def health():
    return {'status': 'ok'}, 200


@bp.route('/')
@login_required
def index():
    try:
        # Webhook pro Session auslösen, falls aktiviert und noch nicht gesendet
        if current_app.config.get('WEBHOOK_ENABLED', False) and 'webhook_sent' not in session:
            username = session.get('username', 'Unknown')
            try:
                response = requests.post(
                    current_app.config['WEBHOOK_URL'],
                    json={
                        "title": "Agenda Session Start",
                        "message": f"Es hat sich gerade der Benutzer {username} in einer neuen Session angemeldet"
                    },
                    timeout=5
                )
                if response.status_code == 200:
                    logger.info(f"Webhook sent successfully for user {username}: {response.status_code}")
                else:
                    logger.error(f"Webhook failed for user {username}: {response.status_code} - {response.text}")
            except requests.RequestException as e:
                logger.error(f"Webhook failed for user {username}: {str(e)}")
            # Flag setzen, um erneuten Aufruf in dieser Session zu verhindern
            session['webhook_sent'] = True
            session.permanent = True  # Sicherstellen, dass die Session permanent ist

        team_code = get_active_team_code()
        trainings = Training.query.filter_by(team_code=team_code).all()
        training_ids = [training.id for training in trainings]
        activities_by_training = {training.id: [] for training in trainings}
        if training_ids:
            activities = Activity.query.filter(Activity.training_id.in_(training_ids)).order_by(Activity.training_id, Activity.order_index).all()
            for activity in activities:
                activities_by_training[activity.training_id].append(activity)

        instances_by_key = {}
        instance_activities_by_id = {}
        if training_ids:
            instances = TrainingInstance.query.filter(TrainingInstance.training_id.in_(training_ids)).all()
            instance_ids = [instance.id for instance in instances]
            instances_by_key = {(instance.training_id, instance.date): instance for instance in instances}
            if instance_ids:
                instance_activities = ActivityInstance.query.filter(ActivityInstance.training_instance_id.in_(instance_ids)).order_by(ActivityInstance.training_instance_id, ActivityInstance.order_index).all()
                for activity in instance_activities:
                    instance_activities_by_id.setdefault(activity.training_instance_id, []).append(activity)

        now = datetime.now()
        today = now.date()

        upcoming_trainings = get_upcoming_trainings(trainings, activities_by_training, instances_by_key, instance_activities_by_id, now)
        current_training, current_activity, next_activity, training_status, current_date, current_activities, _current_start_dt = get_current_training_status(trainings, activities_by_training, instances_by_key, instance_activities_by_id, now)
        
        return render_template('index.html', 
                             trainings=trainings, 
                             weekdays=WEEKDAYS,
                             position_groups=POSITION_GROUPS,
                             upcoming_trainings=upcoming_trainings,
                             current_training=current_training,
                             current_activity=current_activity,
                             next_activity=next_activity,
                             training_status=training_status,
                             display_activities=current_activities,
                             current_date=current_date,
                             now=now)
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        return render_template('error.html'), 500

@bp.route('/live')
@login_required
def live():
    try:
        team_code = get_active_team_code()
        trainings, activities_by_training, instances_by_key, instance_activities_by_id = load_training_data(team_code=team_code)

        now = datetime.now()
        today = now.date()
        current_training = None
        current_activity = None
        next_activity = None
        training_status = None

        selected_training_id = request.args.get('training_id', type=int)
        selected_date_str = request.args.get('date')
        selected_date = None
        if selected_training_id and selected_date_str:
            try:
                selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                selected_date = None

        display_activities = None
        if selected_training_id and selected_date:
            training = db.get_or_404(Training, selected_training_id)
            if training.team_code != team_code:
                return render_template('error.html'), 404
            if training.start_date <= selected_date <= training.end_date and training.weekday == selected_date.weekday():
                instance = instances_by_key.get((training.id, selected_date))
                if instance and instance.status == 'cancelled':
                    timeline, start_dt, end_dt = None, None, None
                else:
                    display_activities = instance_activities_by_id.get(instance.id, []) if instance else activities_by_training.get(training.id, [])
                    timeline, start_dt, end_dt = get_timeline_from_activities(display_activities, selected_date)
            else:
                timeline, start_dt, end_dt = None, None, None

            if timeline:
                current_training = training
                if selected_date == today:
                    if start_dt <= now < end_dt:
                        training_status = 'running'
                        for i, (activity, activity_start, activity_end) in enumerate(timeline):
                            if activity_start <= now < activity_end:
                                current_activity = activity
                                if i + 1 < len(timeline):
                                    next_activity = timeline[i + 1][0]
                                break
                            elif now < activity_start:
                                next_activity = activity
                                break
                    elif now < start_dt:
                        training_status = 'upcoming'
                        next_activity = timeline[0][0]
            return render_template('live.html', 
                                 weekdays=WEEKDAYS,
                                 position_groups=POSITION_GROUPS,
                                 current_training=current_training,
                                 current_activity=current_activity,
                                 next_activity=next_activity,
                                 training_status=training_status,
                                 display_activities=display_activities,
                                 current_date=selected_date,
                                 now=now)

        current_training, current_activity, next_activity, training_status, current_date, current_activities, _current_start_dt = get_current_training_status(trainings, activities_by_training, instances_by_key, instance_activities_by_id, now)

        return render_template('live.html', 
                             weekdays=WEEKDAYS,
                             position_groups=POSITION_GROUPS,
                             current_training=current_training,
                             current_activity=current_activity,
                             next_activity=next_activity,
                             training_status=training_status,
                             display_activities=current_activities,
                             current_date=current_date,
                             now=now)
    except Exception as e:
        logger.error(f"Error in live route: {str(e)}")
        return render_template('error.html'), 500

@bp.route('/test')
def test():
    if not (current_app.debug or current_app.testing):
        return render_template('error.html'), 404
    return '<h1>Flask funktioniert!</h1><p>Gehe zu <a href="/login">/login</a></p>'

@bp.route('/shared-example')
def shared_example():
    """Beispiel-Seite mit TT-Shared Design-System"""
    return render_template('example_shared.html')
