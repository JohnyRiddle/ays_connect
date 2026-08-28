import os
from datetime import timedelta
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-local-development-key-change-before-production")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend,testserver").split(",")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "corsheaders", "rest_framework", "drf_spectacular", "accounts", "organizations", "employees", "access_control", "audit", "events", "work_tasks", "service_requests", "sla", "tasks", "checklists", "sensors", "incidents", "analytics", "notifications", "knowledge_base", "learning",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
              "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": dj_database_url.config(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60)}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Asia/Novosibirsk"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
}
SPECTACULAR_SETTINGS = {"TITLE": "AYS Connect API", "VERSION": "1.6.0", "SERVE_INCLUDE_SCHEMA": False}
KNOWLEDGE_MAX_FILE_SIZE_MB = int(os.getenv("KNOWLEDGE_MAX_FILE_SIZE_MB", "50"))
ATTACHMENT_MAX_SIZE = int(os.getenv("ATTACHMENT_MAX_SIZE", os.getenv("TASK_ATTACHMENT_MAX_SIZE", str(25 * 1024 * 1024))))
ATTACHMENT_ALLOWED_TYPES = tuple(filter(None, os.getenv(
    "ATTACHMENT_ALLOWED_TYPES", os.getenv(
    "TASK_ATTACHMENT_ALLOWED_TYPES",
    "application/pdf,image/jpeg,image/png,image/webp,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,application/zip",
)).split(",")))
TASK_ATTACHMENT_MAX_SIZE = ATTACHMENT_MAX_SIZE
TASK_ATTACHMENT_ALLOWED_TYPES = ATTACHMENT_ALLOWED_TYPES
TASK_RECURRENCE_HORIZON_HOURS = int(os.getenv("TASK_RECURRENCE_HORIZON_HOURS", "24"))
TASK_MAX_OCCURRENCES_PER_RULE_PER_RUN = int(os.getenv("TASK_MAX_OCCURRENCES_PER_RULE_PER_RUN", "100"))
TASK_MAX_TOTAL_OCCURRENCES_PER_RUN = int(os.getenv("TASK_MAX_TOTAL_OCCURRENCES_PER_RUN", "500"))
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(minutes=15), "REFRESH_TOKEN_LIFETIME": timedelta(days=1), "ROTATE_REFRESH_TOKENS": True}
