"""Kleine, lokale Berechtigungslogik des Single-Service.

Die Anwendung braucht für den verbleibenden Umfang kein gemeinsames
Plattform-Paket und kein SSO-Claim-Normalisierungsmodell mehr.
"""

VALID_ROLES = {'user', 'admin'}


def normalize_permissions(value):
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip()]
    return [str(item).strip() for item in (value or []) if str(item).strip()]


def has_role_permission(*_args, **_kwargs):
    return False


def is_platform_admin(role=None, permissions=None):
    return str(role or '').lower() == 'admin' or '*' in normalize_permissions(permissions)


def is_service_admin(role=None, permissions=None, **_kwargs):
    return is_platform_admin(role, permissions)
