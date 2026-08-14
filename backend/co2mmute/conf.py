"""Configuration helpers that must be importable from settings.py.

Deliberately free of any `django.conf.settings` import so it can be used while
settings are still being constructed. (`co2mmute.utils` imports settings, which is
why this does not live there.)
"""

from django.core.exceptions import ImproperlyConfigured

# Only ever used with DEBUG on. Never valid in production.
DEV_SECRET_KEY = "django-insecure-placeholder-key"

# Values that have shipped as defaults in this repo, and are therefore public.
# Rejecting them by name stops a stale compose fallback from satisfying the check.
KNOWN_INSECURE_SECRET_KEYS = frozenset(
    {
        DEV_SECRET_KEY,
        "insecure-local-key",
    }
)

# Enough to rule out a hand-typed value ("test", "changeme") without invalidating
# the keys already in use, which are 46 random characters. Django's own deploy
# check uses 50 only because that is the length its generator happens to produce;
# entropy, not length, is what matters, and raising this to 50 would force a key
# rotation that logs every player out of every running game.
MIN_SECRET_KEY_LENGTH = 32


def resolve_secret_key(env_value, *, debug):
    """Return the SECRET_KEY to run with, or refuse to boot without a real one.

    Player cookies are signed with salts derived from this key (see
    ``settings._salt_base``), so a production box on a shared placeholder key has
    forgeable player identities. With DEBUG on we fall back to the dev key; with
    DEBUG off the key must be present, not a known placeholder, and long enough.
    """
    key = (env_value or "").strip()

    if debug:
        return key or DEV_SECRET_KEY

    if not key:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not set and DEBUG is False. Generate one with:\n"
            "  python -c 'from django.core.management.utils import "
            "get_random_secret_key; print(get_random_secret_key())'\n"
            "Changing this key invalidates every player cookie, so any running "
            "game will be logged out."
        )

    if key in KNOWN_INSECURE_SECRET_KEYS:
        raise ImproperlyConfigured(
            f"DJANGO_SECRET_KEY is set to {key!r}, a placeholder published in this "
            "repository. Generate a real key."
        )

    if len(key) < MIN_SECRET_KEY_LENGTH:
        raise ImproperlyConfigured(
            f"DJANGO_SECRET_KEY is only {len(key)} characters; at least "
            f"{MIN_SECRET_KEY_LENGTH} are required."
        )

    return key
