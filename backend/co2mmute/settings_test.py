"""Settings for test runs. Roadmap.md 1.5.

    ./manage.py test --settings=co2mmute.settings_test

Deliberately Postgres-backed. settings.py falls back to sqlite whenever DEBUG is
on, and sqlite treats select_for_update() as a no-op — so the row locks that
1.4's capacity check and 1.3's anonymisation depend on would go untested while
the tests still passed.
"""

import os
import tempfile

from co2mmute.settings import *

# resolve secret key in conf.py depends on it.
SECRET_KEY = "test-only-key-not-used-anywhere-else-0123456789"

DEBUG = False


SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SECURE_COOKIES", "True") == "True"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE

# MD5 rather than PBKDF2. its jsut quicker in testing
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# No Redis in a CI runner.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Run tasks inline — there is no worker and no broker.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# GameSession.save() renders a QR code on every create. Keep it out of the repo.
MEDIA_ROOT = tempfile.mkdtemp(prefix="co2mmute-test-media-")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "co2mmute"),
        "USER": os.environ.get("POSTGRES_USER", "co2mmute"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "co2mmute"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Keep the run readable. make dots not info text!
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "ERROR"},
}
