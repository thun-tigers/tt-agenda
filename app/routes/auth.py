import secrets
from urllib.parse import urlencode, urljoin, urlparse

import jwt
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from ..models import User
from ..extensions import limiter, db
from werkzeug.security import generate_password_hash
import logging

bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def get_auth_login_url(next_page=None):
    auth_base_url = current_app.config.get('AUTH_BASE_URL', 'http://localhost:8085').rstrip('/')
    query = {'next_service': 'tt-agenda'}
    if next_page:
        query['next'] = next_page
    return f"{auth_base_url}/?{urlencode(query)}"


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("20/minute", methods=["POST"])
def login():
    next_page = request.args.get('next')
    if next_page and not is_safe_url(next_page):
        next_page = None
    auth_login_url = get_auth_login_url(next_page)
    if request.method == 'POST':
        flash('Die Anmeldung erfolgt zentral über tt-auth.', 'info')
        return redirect(auth_login_url)

    return render_template('login.html', auth_login_url=auth_login_url, next_page=next_page)

@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Sie wurden abgemeldet.', 'info')
    return redirect(get_auth_login_url())


@bp.route('/auth/sso')
@limiter.limit("60/minute")
def sso_login():
    token = request.args.get('token', '').strip()
    if not token:
        flash('SSO-Token fehlt.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        payload = jwt.decode(
            token,
            current_app.config.get('SSO_SHARED_SECRET') or current_app.config.get('SECRET_KEY'),
            algorithms=['HS256'],
            audience=current_app.config.get('SSO_EXPECTED_AUDIENCE', 'tt-agenda'),
        )
    except jwt.ExpiredSignatureError:
        flash('SSO-Token ist abgelaufen. Bitte erneut starten.', 'warning')
        return redirect(url_for('auth.login'))
    except jwt.InvalidTokenError:
        flash('Ungültiger SSO-Token.', 'danger')
        return redirect(url_for('auth.login'))

    username = (payload.get('username') or '').strip()
    role = (payload.get('service_role') or payload.get('role') or 'user').strip().lower()
    if role not in ('admin', 'user'):
        role = 'user'

    if not username:
        flash('SSO-Token enthält keinen Benutzernamen.', 'danger')
        return redirect(url_for('auth.login'))

    auth_user_id = int(payload['sub'])
    user = User.query.filter_by(auth_user_id=auth_user_id).first()
    if not user:
        user = User.query.filter_by(username=username).first()
    if not user:
        if not current_app.config.get('SSO_AUTO_PROVISION_USERS', True):
            flash('SSO-Benutzer ist nicht freigeschaltet.', 'danger')
            return redirect(url_for('auth.login'))
        user = User(username=username, role=role)
        user.password_hash = generate_password_hash(secrets.token_hex(32))
        db.session.add(user)
    if current_app.config.get('SSO_SYNC_ROLE', True):
        user.sync_from_sso_claims(payload)
    db.session.commit()

    session['user_id'] = user.id
    session['auth_user_id'] = user.auth_user_id
    session['username'] = user.username
    session['user_role'] = user.role
    session['platform_role'] = user.platform_role
    session['display_name'] = user.display_name or user.username
    session['profile_complete'] = user.profile_complete
    session['memberships'] = user.memberships_json or []
    session['permissions'] = user.permissions_json or []
    flash('Erfolgreich via SSO angemeldet.', 'success')
    next_page = request.args.get('next')
    if next_page and is_safe_url(next_page):
        return redirect(next_page)
    return redirect(url_for('main.index'))
