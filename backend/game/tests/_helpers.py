"""Shared fixtures for the game test package.

Named with a leading underscore so the test runner does not collect it.
"""

import asyncio
import contextlib
import logging
import shutil
import tempfile

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings

from co2mmute.utils import sanitize_group_name, sign_value
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

    Re-entrant: it restores whatever was active before rather than switching
    logging fully back on, so a muted() nested inside another one does not
    un-mute the rest of the outer block.
    """
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous)


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


def log_in_as_player(client, game_id, player_id):
    """Give a test client both player cookies, in the 1.2 format."""
    client.cookies[f"{settings.COOKIE_GAME_PREFIX}{game_id}"] = sign_value(
        f"{game_id}:test-token", settings.COOKIE_GAME_SALT
    )
    client.cookies[f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"] = sign_value(
        f"{game_id}:{player_id}", settings.COOKIE_PLAYER_SALT
    )


def create_game_map(name="Test Map"):
    """A map, so a created game is one that could actually be started.

    GameSession.save() forces is_active back to False whenever game_map is
    None, so a mapless game is unstartable — which is why the create form is
    being made to require one.
    """
    from maps.models import GameMap

    return GameMap.objects.create(name=name)


def create_form_data(**overrides):
    """A valid POST body for GameSessionCreateView (game/create/).

    A map is created and selected unless the caller names one: "valid" has to
    include a map, or the game cannot be started. Pass `game_map=""` explicitly
    to build the invalid body on purpose.
    """
    data = {
        "game_name": "Neues Spiel",
        "game_password": "",
        "game_map": "",
        "max_players": 4,
        "agent_per_player": 1,
        "max_rounds": 3,
        "max_CO2_level": 100,
        "people_per_agent": 1000,
        "idle_end_days": 30,
        "lobby_open": "",
    }
    if "game_map" not in overrides:
        data["game_map"] = create_game_map().pk
    data.update(overrides)
    return data


class GroupListener:
    """Sits in a channel group, the way a connected GameConsumer does.

    By default the game's group (gamestate_<game_id>); pass group= for another
    one, e.g. a seat's player_<pk>. Works on the in-memory channel layer from
    TEST_BACKENDS. Messages are read once, on first access: the layer's queues
    bind to the event loop that first waits on them, and every async_to_sync
    call brings a new loop.
    """

    def __init__(self, game_id=None, group=None):
        self.layer = get_channel_layer()
        self.channel = async_to_sync(self.layer.new_channel)()
        group = group or f"gamestate_{sanitize_group_name(game_id)}"
        async_to_sync(self.layer.group_add)(group, self.channel)
        self._messages = None

    def messages(self):
        """Everything sent to the group, as the raw channel-layer messages."""
        if self._messages is None:

            async def drain():
                messages = []
                while True:
                    try:
                        messages.append(
                            await asyncio.wait_for(
                                self.layer.receive(self.channel), timeout=0.05
                            )
                        )
                    except asyncio.TimeoutError:
                        return messages

            self._messages = async_to_sync(drain)()
        return self._messages

    def events(self):
        """(event, data) for the game.state / between-round events, in order."""
        return [
            (message.get("event"), message.get("data", {}))
            for message in self.messages()
            if "event" in message
        ]

    def names(self):
        return [name for name, _ in self.events()]

    def data(self, name):
        """The payload of the last event with this name."""
        matching = [data for event, data in self.events() if event == name]
        if not matching:
            raise AssertionError(f"no {name!r} event, got {self.names()}")
        return matching[-1]

    def rosters(self):
        """The player lists of every roster_update, in order."""
        return [
            message["players"]
            for message in self.messages()
            if message.get("type") == "roster_update"
        ]
