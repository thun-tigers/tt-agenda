import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('SQLALCHEMY_DATABASE_URI')
        or os.environ.get('DATABASE_URL')
        or 'sqlite:///instance/tt_agenda.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    WEBHOOK_ENABLED = os.environ.get('WEBHOOK_ENABLED', 'false').lower() == 'true'
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://n8n.3624.ch/webhook/messaging')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    AUTO_CREATE_DB = os.environ.get('AUTO_CREATE_DB', 'true').lower() == 'true'
    TT_INFRA_INTERNAL_URL = os.environ.get('TT_INFRA_INTERNAL_URL')
    INTERNAL_API_SECRET = os.environ.get('INTERNAL_API_SECRET')
    PUSHOVER_TOKEN = os.environ.get('PUSHOVER_TOKEN')
    PUSHOVER_USER = os.environ.get('PUSHOVER_USER')
    PUSHOVER_URL = os.environ.get('PUSHOVER_URL', 'https://api.pushover.net/1/messages.json')
    PUSHOVER_TIMEOUT = float(os.environ.get('PUSHOVER_TIMEOUT', '3'))
    # Rate limiting: override with redis://host:port/0 for multi-worker production
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    DEFAULT_ADMIN_USERNAME = os.environ.get('DEFAULT_ADMIN_USERNAME', 'admin')
    DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD')
