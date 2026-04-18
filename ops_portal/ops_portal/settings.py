"""
Django settings for ops_portal project.

Environment-driven values (see `.env.example` at the repo root):
    DJANGO_SECRET_KEY        Django session signing key (rotate for prod)
    DJANGO_DEBUG             'True' / 'False'
    DJANGO_ALLOWED_HOSTS     Comma-separated host list
    SERVICENOW_BASE          Your ServiceNow instance URL
    EDGE_EXE_PATH            Full path to msedge.exe (Windows only)

Load order: env variables → this file → optional `local_settings.py`
(imported at the bottom if present).
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------
# Load .env (repo root) if python-dotenv is available.
# Must happen BEFORE any os.environ.get() call below.
# ------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent / '.env')
except ImportError:
    # python-dotenv not installed — fall back to vars already in the shell
    pass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(name: str, default: list) -> list:
    raw = os.environ.get(name, '')
    if not raw.strip():
        return list(default)
    return [p.strip() for p in raw.split(',') if p.strip()]


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# The fallback below is Django's own 'insecure' placeholder for local dev.
# Override via the DJANGO_SECRET_KEY env var for any real deployment.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-18+eyr)p29q%h)d9*(0o_9)aplmso&l^cyzj%aup%e1q4f0%pu',
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = _env_bool('DJANGO_DEBUG', True)

ALLOWED_HOSTS = _env_list('DJANGO_ALLOWED_HOSTS', [])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # local apps
    'core',
    'servicenow',
    'tachyon',
    # celery results backend
    'django_celery_results',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ops_portal.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.ui_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'ops_portal.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']   # source files served in development
STATIC_ROOT = BASE_DIR / 'staticfiles'     # collectstatic output for production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ============================================================
# Browser automation (core app)
# ============================================================
EDGE_EXE_PATH = os.environ.get(
    'EDGE_EXE_PATH',
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)
BROWSER_SESSION_DIR = BASE_DIR / '.browser_sessions'
BROWSER_STARTUP_TIMEOUT = int(os.environ.get('BROWSER_STARTUP_TIMEOUT', 30))
BROWSER_PROFILE_BASE = os.environ.get('BROWSER_PROFILE_BASE') or None
# ↑ defaults to %LOCALAPPDATA%\CopilotOps\EdgeProfiles when None
EDGE_PORT_BASES = {
    "grafana": 9400,
    "harness": 9500,
    "sploc":   9600,
    "copilot": 9700,
}
EDGE_PORT_RANGE = 50


# =========================
# Celery (filesystem broker)
# =========================
BROKER_DIR = BASE_DIR / "celery_data" / "broker"

CELERY_BROKER_URL = "filesystem://"
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "data_folder_in": str(BROKER_DIR),
    "data_folder_out": str(BROKER_DIR),
    "data_folder_processed": str(BASE_DIR / "celery_data" / "processed"),
}

CELERY_RESULT_BACKEND = "django-db"
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_EXPIRES = int(os.environ.get('CELERY_RESULT_EXPIRES', 3600))


# =========================
# AI-assisted creation
# =========================
AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_MODEL = os.environ.get('AI_MODEL', 'claude-sonnet-4-20250514')


# =========================
# ServiceNow
# =========================
SERVICENOW_BASE = os.environ.get(
    'SERVICENOW_BASE',
    'https://your-instance.service-now.com',
)

SERVICENOW_CHANGE_TABLE = "change_request"
SERVICENOW_CHANGE_FIELDS = "number,sys_id,assignment_group,assigned_to,state,short_description"

SERVICENOW_INCIDENT_TABLE = "incident"
SERVICENOW_INCIDENT_TASK_TABLE = "incident_task"

SERVICENOW_INCIDENT_FIELDS = (
    "sys_id,number,short_description,description,state,priority,"
    "impact,urgency,assignment_group,assigned_to,sys_updated_on"
)
SERVICENOW_INCIDENT_TASK_FIELDS = (
    "sys_id,number,short_description,state,assignment_group,assigned_to,sys_updated_on"
)

SERVICENOW_ATTACHMENT_FIELDS = (
    "sys_id,file_name,content_type,size_bytes,download_link,"
    "sys_created_on,sys_created_by"
)


# =========================
# Tachyon
# =========================
TACHYON_BASE = os.environ.get(
    'TACHYON_BASE',
    'https://your-tachyon-instance.net',
)

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

TACHYON_UPLOAD_TMP_DIR = str(MEDIA_ROOT / "tachyon_uploads")
TACHYON_UPLOAD_MAX_BYTES = 10 * 1024 * 1024

TACHYON_FETCH_TIMEOUT_MS = 60000
TACHYON_SCRIPT_TIMEOUT_SECONDS = 90
TACHYON_DEFAULT_USER_ID = "uxxxxxx"


# ============================================================
# Local overrides (gitignored)
# ============================================================
# Drop any machine-specific settings in `ops_portal/local_settings.py`.
# That file is gitignored so it won't be committed.
try:
    from .local_settings import *  # noqa: F401,F403
except ImportError:
    pass
