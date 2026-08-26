from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..extensions import db
from ..models import User
from ..utils import admin_required

bp = Blueprint('users', __name__, url_prefix='/users')


@bp.route('/')
@admin_required
def index():
    query = (request.args.get('q') or '').strip().lower()
    users = User.query.order_by(User.last_name, User.first_name, User.username).all()
    if query:
        users = [user for user in users if query in ' '.join(filter(None, [user.username, user.full_name, user.email])).lower()]
    return render_template('users.html', users=users, query=request.args.get('q', ''))


@bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit(user_id):
    user = db.get_or_404(User, user_id)
    if request.method == 'POST':
        user.first_name = (request.form.get('first_name') or '').strip() or None
        user.last_name = (request.form.get('last_name') or '').strip() or None
        user.email = (request.form.get('email') or '').strip().lower() or None
        user.role = 'admin' if request.form.get('role') == 'admin' else 'user'
        user.account_status = request.form.get('account_status') or 'active'
        user.is_active = user.account_status != 'suspended'
        user.display_name = user.full_name
        db.session.commit()
        flash(f'Benutzer {user.username} gespeichert.', 'success')
        return redirect(url_for('users.index'))
    return render_template('user_edit.html', user=user)


@bp.route('/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == session.get('user_id'):
        flash('Der eigene Account kann nicht gelöscht werden.', 'danger')
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f'Benutzer {user.username} gelöscht.', 'success')
    return redirect(url_for('users.index'))
