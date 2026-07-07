import logging
import secrets

import jwt
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from tt_common.sso import get_auth_login_url, get_auth_logout_url, is_safe_url

from ..authz import normalize_auth_payload
from ..extensions import db, limiter
from ..models import User
from ..sso_replay import is_replayed_sso_token

bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("20/minute", methods=["POST"])
def login():
    next_page = request.args.get('next')
    if next_page and not is_safe_url(next_page):
        next_page = None
    auth_login_url = get_auth_login_url('tt-agenda', next_page)
    if request.method == 'POST':
        flash('Die Anmeldung erfolgt zentral über tt-auth.', 'info')
        return redirect(auth_login_url)
    return render_template('login.html', auth_login_url=auth_login_url, next_page=next_page)


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(get_auth_logout_url())


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

    if is_replayed_sso_token(payload):
        flash('SSO-Token wurde bereits verwendet. Bitte erneut anmelden.', 'danger')
        return redirect(url_for('auth.login'))

    auth = normalize_auth_payload(payload)
    claims = auth['claims']
    username = (claims.get('username') or '').strip()
    role = auth['service_role']

    if not username:
        flash('SSO-Token enthält keinen Benutzernamen.', 'danger')
        return redirect(url_for('auth.login'))

    auth_user_id = int(claims['sub'])
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
        user.sync_from_sso_claims(claims)
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
    session['role_permissions'] = (user.claims_json or {}).get('role_permissions') or {}
    session['claims_json'] = user.claims_json or {}

    memberships = session.get('memberships') or []
    available_codes = sorted({
        (membership.get('team_code') or '').strip().upper()
        for membership in memberships
        if (membership.get('team_code') or '').strip()
    })
    if not available_codes:
        available_codes = ['SENIORS']

    token_team = (claims.get('active_team_code') or '').strip().upper()
    if token_team and token_team in available_codes:
        session['active_team_code'] = token_team
    elif session.get('active_team_code') in available_codes:
        pass
    else:
        session['active_team_code'] = available_codes[0]

    next_page = request.args.get('next')
    if next_page and is_safe_url(next_page):
        return redirect(next_page)
    return redirect(url_for('main.index'))


@bp.route('/team/switch', methods=['POST'])
def switch_team():
    if 'user_id' not in session:
        flash('Bitte melden Sie sich an.', 'warning')
        return redirect(url_for('auth.login'))

    target = (request.form.get('team_code') or '').strip().upper()
    next_url = (request.form.get('next') or '').strip()
    memberships = session.get('memberships') or []
    allowed = {
        (membership.get('team_code') or '').strip().upper()
        for membership in memberships
        if (membership.get('team_code') or '').strip()
    }
    if not allowed:
        allowed = {'SENIORS'}

    if target and target in allowed:
        session['active_team_code'] = target
    else:
        flash('Ungültige Mannschaftsauswahl.', 'warning')

    if next_url and is_safe_url(next_url):
        return redirect(next_url)
    return redirect(request.referrer or url_for('main.index'))
