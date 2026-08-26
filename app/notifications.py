"""Optionale Benachrichtigungen an externe Dienste."""

import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'


def send_pushover(message: str, title: str, priority: int = 0) -> bool:
    """Send a Pushover message without blocking the current request on failure."""
    token = current_app.config.get('PUSHOVER_TOKEN')
    user = current_app.config.get('PUSHOVER_USER')
    if not token or not user:
        return False

    payload = {'token': token, 'user': user, 'message': message, 'title': title, 'priority': priority}
    if priority == 1:
        payload.update({'retry': 300, 'expire': 3600})

    try:
        response = requests.post(
            current_app.config.get('PUSHOVER_URL', PUSHOVER_URL),
            data=payload,
            timeout=current_app.config.get('PUSHOVER_TIMEOUT', 3),
        )
        if response.ok:
            return True
        logger.warning('Pushover notification failed with HTTP status %s', response.status_code)
    except requests.RequestException:
        logger.warning('Pushover notification could not be delivered', exc_info=True)
    return False


def notify_registration(user) -> bool:
    return send_pushover(
        f'Neue Registrierung von {user.full_name} ({user.username}). Das Konto wartet auf Freigabe.',
        'Neue Benutzerregistrierung',
        priority=1,
    )


def notify_login(user) -> bool:
    return send_pushover(
        f'{user.full_name} ({user.username}) hat sich angemeldet.',
        'Benutzeranmeldung',
    )
