"""Shared fixtures for the game test package.

Named with a leading underscore so the test runner does not collect it.
"""

import contextlib
import logging
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import override_settings

from game.models import GameSession

# Creating a GameSession renders a QR code to MEDIA_ROOT, the signals broadcast
# over the channel layer, and the post_save handler writes to the cache. None of
# those Redis instances exist in a test run, and none of them are what we assert on.
TEST_BACKENDS = dict(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)


@contextlib.contextmanager
def muted():
    """Silence the INFO chatter the game signals emit on the happy path.

    Scoped on purpose — wrap only the calls that are expected to log, so an
    unexpected error somewhere else still shows up in the run. Never disable
    logging for a whole module or class.
    """
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(logging.NOTSET)


class TempMediaRootMixin:
    """Point MEDIA_ROOT at a throwaway directory for the whole test class.

    GameSession.save() writes a QR code image, so without this the test run
    litters the real media directory.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temp_media_root = tempfile.mkdtemp(prefix="co2mmute-tests-")
        cls._media_override = override_settings(MEDIA_ROOT=cls.temp_media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls.temp_media_root, ignore_errors=True)
        super().tearDownClass()


def create_host(username="host", password="password123", **extra):
    return get_user_model().objects.create_user(
        username=username, password=password, **extra
    )


def create_game_session(host, **overrides):
    """A playable session with limits generous enough not to end on its own.

    Override `max_rounds` / `max_CO2_level` when the test is *about* an end
    condition.
    """
    defaults = {
        "game_host": host,
        "game_name": "Test Game",
        "max_players": 4,
        "agent_per_player": 1,
        "max_rounds": 10,
        "max_CO2_level": 10_000,
    }
    defaults.update(overrides)
    return GameSession.objects.create(**defaults)
