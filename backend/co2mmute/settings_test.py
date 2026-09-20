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

# A real key so the phase-0 resolver is satisfied without DEBUG. Test-only, and
# it never leaves this file — the cookie salts derived from it are meaningless
# outside a run.
SECRET_KEY = "test-only-key-not-used-anywhere-else-0123456789"

DEBUG = False

# settings.py derives the secure-cookie flags from its own import-time DEBUG,
# which reads DJANGO_DEBUG (default True). Compose sets it to False, so a local
# run is hardened; a CI runner sets nothing, so the flags froze at False while
# DEBUG above is False — the one combination the hardening test rejects.
# Re-derive them against this module's DEBUG, the way SECRET_KEY and DATABASES
# are re-declared.
SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SECURE_COOKIES", "True") == "True"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE

# MD5 rather than PBKDF2. _helpers.create_host runs in most setUp methods and the
# default hasher is deliberately slow.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# No Redis in a CI runner. _helpers.TEST_BACKENDS applies the same two per class;
# doing it globally means a class that forgets the decorator still runs.
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

# Keep the run readable — a wall of dots, not a wall of INFO. The game signals
# are chatty on the happy path. Anything at ERROR still comes through, and the
# scoped muted() helper in _helpers.py stays the tool for expected error paths.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "ERROR"},
}
