from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..extensions import db, limiter
from ..models import User
from ..forms import validate_password_strength
from ..notifications import notify_login, notify_registration

bp = Blueprint('auth', __name__)


def _safe_next(target):
    if not target:
        return None
    base = urlparse(request.host_url)
    candidate = urlparse(urljoin(request.host_url, target))
    return target if candidate.scheme in {'http', 'https'} and candidate.netloc == base.netloc else None


def _start_session(user):
    session.clear()
    session.update({
        'user_id': user.id,
        'username': user.username,
        'user_role': user.role,
        'display_name': user.full_name,
        'profile_complete': user.profile_complete,
        'memberships': user.teams,
    })
    codes = [str(item.get('team_code', '')).upper() for item in user.teams if item.get('team_code')]
    session['active_team_code'] = codes[0] if codes else 'SENIORS'


@bp.route('/auth')
@bp.route('/auth/')
def auth_entrypoint():
    """Kompatibler Einstieg für die bisherige /auth/-URL."""
    return redirect(url_for('auth.login'))


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('20/minute', methods=['POST'])
def login():
    next_page = _safe_next(request.args.get('next') or request.form.get('next'))
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(request.form.get('password') or '') and user.can_login:
            _start_session(user)
            notify_login(user)
            return redirect(next_page or url_for('main.index'))
        if user and user.check_password(request.form.get('password') or '') and user.account_status == 'pending':
            flash('Dein Konto wartet noch auf die Freigabe durch einen Coach oder Administrator.', 'warning')
        elif user and user.check_password(request.form.get('password') or '') and user.account_status == 'suspended':
            flash('Dein Konto ist gesperrt. Bitte wende dich an einen Administrator.', 'danger')
        else:
            flash('Benutzername oder Passwort ist nicht korrekt.', 'danger')
    return render_template('login.html', next_page=next_page or '')


@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit('10/hour', methods=['POST'])
def register():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip().lower() or None
        password = request.form.get('password') or ''
        password_confirmation = request.form.get('password_confirmation') or ''
        first_name = (request.form.get('first_name') or '').strip() or None
        last_name = (request.form.get('last_name') or '').strip() or None
        if not username or not password or not first_name or not last_name:
            flash('Bitte fülle alle Pflichtfelder aus.', 'danger')
        elif len(username) > 80:
            flash('Der Benutzername darf höchstens 80 Zeichen lang sein.', 'danger')
        elif (password_error := validate_password_strength(password)):
            flash(password_error, 'danger')
        elif password != password_confirmation:
            flash('Die Passwörter stimmen nicht überein.', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Dieser Benutzername ist bereits vergeben.', 'danger')
        elif email and User.query.filter_by(email=email).first():
            flash('Diese E-Mail-Adresse wird bereits verwendet.', 'danger')
        else:
            user = User(
                username=username, email=email, first_name=first_name, last_name=last_name,
                display_name=f'{first_name} {last_name}', account_status='pending',
                profile_complete=True, memberships_json=[{'team_code': 'SENIORS', 'team_name': 'Seniors', 'member_role': 'player'}],
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            notify_registration(user)
            flash('Registrierung erfolgreich. Dein Konto wird nun durch einen Coach oder Administrator geprüft.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('register.html')


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@bp.route('/team/switch', methods=['POST'])
def switch_team():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    target = (request.form.get('team_code') or '').strip().upper()
    allowed = {str(item.get('team_code', '')).upper() for item in session.get('memberships', [])}
    if target == '__ALL__' or target in allowed:
        session['active_team_code'] = target
    return redirect(_safe_next(request.form.get('next')) or url_for('main.index'))


@bp.route('/profile', methods=['GET', 'POST'])
def profile():
    user = db.session.get(User, session.get('user_id')) if session.get('user_id') else None
    if not user:
        return redirect(url_for('auth.login', next=request.path))
    if request.method == 'POST':
        user.first_name = (request.form.get('first_name') or '').strip() or None
        user.last_name = (request.form.get('last_name') or '').strip() or None
        user.email = (request.form.get('email') or '').strip().lower() or None
        user.position = (request.form.get('position') or '').strip() or None
        user.phone = (request.form.get('phone') or '').strip() or None
        user.display_name = user.full_name
        new_password = request.form.get('password') or ''
        if new_password:
            password_error = validate_password_strength(new_password)
            if password_error:
                flash(password_error, 'danger')
                return render_template('profile.html', user=user), 400
            if new_password != (request.form.get('password_confirmation') or ''):
                flash('Die Passwörter stimmen nicht überein.', 'danger')
                return render_template('profile.html', user=user), 400
            user.set_password(new_password)
        db.session.commit()
        _start_session(user)
        flash('Profil gespeichert.', 'success')
        return redirect(url_for('auth.profile'))
    return render_template('profile.html', user=user)
