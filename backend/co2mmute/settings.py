import hashlib
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "template"
FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"
STATIC_DIR = BASE_DIR / "static"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-placeholder-key")

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        (
            "http://localhost,http://127.0.0.1,http://localhost:8080,"
            "http://127.0.0.1:8080,http://nginx,"
            "https://localhost,https://127.0.0.1,https://localhost:8080,"
            "https://127.0.0.1:8080"
        ),
    ).split(",")
    if origin.strip()
]

BASE_URL = os.environ.get("DJANGO_BASE_URL", "https://localhost")

LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO" if DEBUG else "INFO").upper()
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "filters": {
        "only_special": {
            "()": "logging.Filter",
            "name": "special",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
        },
        "special_info_file": {
            "class": "logging.FileHandler",
            "level": "INFO",
            "formatter": "verbose",
            "filters": ["only_special"],
            "filename": str(LOG_DIR / "special-info.log"),
        },
        "warnings_file": {
            "class": "logging.FileHandler",
            "level": "WARNING",
            "formatter": "verbose",
            "filename": str(LOG_DIR / "warnings-errors.log"),
        },
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "include_html": True,
        },
    },
    "loggers": {
        "": {
            "handlers": ["console", "warnings_file", "mail_admins"],
            "level": LOG_LEVEL,
        },
        "special": {
            "handlers": ["special_info_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
# Application definition

INSTALLED_APPS = [
    "daphne",
    # Default Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "corsheaders",
    "channels",
    "django_prose_editor",
    # Custom apps
    "game",
    "maps",
    "content",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "co2mmute.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEMPLATE_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "co2mmute.wsgi.application"
ASGI_APPLICATION = "co2mmute.asgi.application"


# Database

DATABASES = (
    {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "co2mmute"),
            "USER": os.environ.get("POSTGRES_USER", "co2mmute"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "co2mmute"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
        }
    }
    if not DEBUG
    else {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

GAME_SESSION_CACHE_TIMEOUT = int(os.environ.get("GAME_SESSION_CACHE_TIMEOUT", 15 * 60))
# OPEN MAPS SHIT
# OVERPASS_API_URL = os.environ.get(
#     "OVERPASS_API_URL",
#     "http://overpass-api:80/api/interpreter",
# )


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
    {
        "NAME": "co2mmute.utils.CustomPasswordValidator",
    },
]


# Internationalization

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [path for path in [FRONTEND_DIST_DIR, STATIC_DIR] if path.exists()]

# Media (user-uploaded files)
MEDIA_URL = os.environ.get("DJANGO_MEDIA_URL", "/media/")
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))

CKEDITOR_UPLOAD_PATH = "uploads/"

# ensure editor only has basic formatting options
# CKEDITOR_CONFIGS = {
#     "content-only": {
#         "toolbar": [
#             ["Bold", "Italic", "Underline", "Strike", "Subscript", "Superscript"],
#             ["NumberedList", "BulletedList", "Outdent", "Indent", "Blockquote"],
#             ["Link", "Unlink"],
#             ["RemoveFormat"],
#         ],
#         "height": 300,
#         "width": "100%",
#         "removeButtons": "Styles, Format, BGColor, JustifyLeft, JustifyCenter, JustifyRight, JustifyBlock, "
#         "Image, Table, HorizontalRule, SpecialChar, PasteFromWord, Source",
#         "forcePasteAsPlainText": True,
#     }
# }

# ensure media dir exists in local/dev runs
try:
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
except Exception:
    # In containerized environments the directory may be managed by volumes; ignore failures
    pass

# Default primary key field type

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# When running behind a proxy (nginx) that terminates TLS, use the
# X-Forwarded-Proto header to let Django know the original request scheme
# so absolute URLs generated by Django/DRF use https instead of http.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

MAX_RETRIES = 5
COOKIE_GAME_PREFIX = "game_access_"
COOKIE_PLAYER_PREFIX = "player_"

# Derive cookie salts deterministically from SECRET_KEY to prevent hardcoded exposure
_salt_base = hashlib.sha256(SECRET_KEY.encode()).hexdigest()
COOKIE_GAME_SALT = f"{_salt_base}:game-access"
COOKIE_PLAYER_SALT = f"{_salt_base}:player-id"

# Cookie TTL in seconds (14 days for persistent sessions)
COOKIE_AGE = 14 * 24 * 60 * 60

PROSE_ATTACHMENTS_ALLOWED = False
PROSE_MEDIA_ROOT = None
PROSE_MEDIA_URL = None