from pathlib import Path
import os
import tempfile

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEVELOPMENT = os.environ.get("DJANGO_ENV") == "development"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEVELOPMENT:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required")
    SECRET_KEY = "local-development-only-insecure-key"
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
if not ALLOWED_HOSTS:
    if not DEVELOPMENT:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is required")
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "menus",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
database_path = os.environ.get("DJANGO_DB_PATH")
if not database_path:
    raise ImproperlyConfigured("DJANGO_DB_PATH is required")
if not Path(database_path).is_absolute():
    raise ImproperlyConfigured("DJANGO_DB_PATH must be absolute")
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": database_path}}
test_database_path = os.environ.get("DJANGO_TEST_DB_PATH")
if test_database_path:
    test_path = Path(test_database_path)
    if (not DEVELOPMENT or not test_path.is_absolute()
            or not test_path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
            or test_path.exists()):
        raise ImproperlyConfigured("DJANGO_TEST_DB_PATH must be a new temporary path in development mode")
    DATABASES["default"]["TEST"] = {"NAME": test_database_path}
LANGUAGE_CODE = "ca"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": ("django.contrib.staticfiles.storage.StaticFilesStorage" if DEVELOPMENT else "whitenoise.storage.CompressedManifestStaticFilesStorage")}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
