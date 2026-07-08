import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('SQLALCHEMY_DATABASE_URI')
        or os.environ.get('DATABASE_URL')
        or 'postgresql+psycopg://tt_agenda:tt_agenda_password@tt-postgres-agenda:5432/tt_agenda'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    AUTH_BASE_URL = os.environ.get('AUTH_BASE_URL', 'http://localhost:8085').rstrip('/')
    WEBHOOK_ENABLED = os.environ.get('WEBHOOK_ENABLED', 'false').lower() == 'true'
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://n8n.3624.ch/webhook/messaging')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    AUTO_CREATE_DB = os.environ.get('AUTO_CREATE_DB', 'true').lower() == 'true'
    SSO_SHARED_SECRET = os.environ.get('SSO_SHARED_SECRET') or SECRET_KEY
    SSO_EXPECTED_AUDIENCE = os.environ.get('SSO_EXPECTED_AUDIENCE', 'tt-agenda')
    SSO_REPLAY_STORAGE_URI = os.environ.get('SSO_REPLAY_STORAGE_URI', '')
    SSO_REPLAY_TTL_SECONDS = int(os.environ.get('SSO_REPLAY_TTL_SECONDS', 300))
    SSO_AUTO_PROVISION_USERS = os.environ.get('SSO_AUTO_PROVISION_USERS', 'true').lower() == 'true'
    SSO_SYNC_ROLE = os.environ.get('SSO_SYNC_ROLE', 'true').lower() == 'true'
    TT_MEMBERS_INTERNAL_URL = os.environ.get('TT_MEMBERS_INTERNAL_URL')
    INTERNAL_API_SECRET = os.environ.get('INTERNAL_API_SECRET') or SSO_SHARED_SECRET
    TT_INFRA_INTERNAL_URL = os.environ.get('TT_INFRA_INTERNAL_URL')
    # Rate limiting: override with redis://host:port/0 for multi-worker production
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
