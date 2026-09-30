"""Shared fixtures for the game test package.

Named with a leading underscore so the test runner does not collect it.
"""

import asyncio
import contextlib
import logging
import re
import shutil
import tempfile

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils.html import strip_tags

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


def create_api_body(**overrides):
    """A valid body for `POST api/game/` — the endpoint behind the create screen.

    A map is created and selected unless the caller names one: "valid" has to
    include a map, or the game cannot be started. Pass `game_map=None`
    explicitly to build the invalid body on purpose.

    It used to be `create_form_data`, a Django form POST. S13 put the screen in
    React, so the body is JSON and the numbers are numbers.
    """
    data = {
        "game_name": "Neues Spiel",
        "game_password": "",
        "game_map": None,
        "max_players": 4,
        "agent_per_player": 1,
        "max_rounds": 3,
        "max_CO2_level": 100,
        "people_per_agent": 1000,
        "idle_end_days": 30,
    }
    if "game_map" not in overrides:
        data["game_map"] = create_game_map().pk
    data.update(overrides)
    return data


def post_create(client, **overrides):
    """`POST api/game/` as JSON, the way the create screen sends it."""
    import json

    return client.post(
        "/api/game/",
        json.dumps(create_api_body(**overrides)),
        content_type="application/json",
    )


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


# ---------------------------------------------------------------------------
# The German detector
# ---------------------------------------------------------------------------
#
# Written for the join funnel (2.6) and kept there until S17, when it turned
# out to be covering two of nine German pages — `/map/upload/` had English
# labels, English help text and English validation errors, live on the site,
# with nothing watching. A detector that only reads the pages it was written
# for is how that survives, so it lives here now and `maps/tests/` uses it too.
ENGLISH_GIVEAWAYS = (
    # Words that cannot appear in German copy. Matched whole-word, so a
    # German word that merely contains one of them is not a hit.
    "choose",
    "continue",
    "configure",
    "display name",
    "enter lobby",
    "enable",
    "idle",
    "incorrect",
    "join",
    "optionally",
    "password",
    "please",
    "profile",
    "share your",
    "already in progress",
    "no session found",
    # Not "session" and not "maximum" on their own: both are German words
    # too ("die Session", "das Maximum"), and flagging them would make the
    # detector an opinion about vocabulary rather than about language. Only
    # the English collocations they came from are hits.
    "session id",
    "session name",
    "session password",
    "maximum players",
    "maximum rounds",
    "maximum co",
    "agents per",
    "people per",
    # S17, for `/map/upload/`. Not "Import", "Upload", "Format" or "Liste":
    # German has all four, and the nav uses them.
    "background image",
    "blank",
    "contain",
    "create a",
    "file",
    "map name",
    "max players",
    "new game",
    "requirements",
    "should",
    "start with",
    "your",
    # S19, for the import's refusals, which S17 never saw because they only
    # appear after a failed upload. "found" alone is the tell in "not found",
    # "found 2"; none of these is a German word.
    "found",
    "missing",
    "must",
    "duplicate",
    "invalid",
    "available",
    "exactly",
    "required",
    "but",
    # S21, for the create endpoint's range and type refusals: Django's and
    # DRF's own defaults ("Ensure this value is less than or equal to 365.",
    # "A valid integer is required."), which no screen had provoked yet.
    "ensure",
    "valid",
    # S22, for the credential pages: Django's own labels and refusals, which
    # reach the page wherever a stock auth form is used unchanged. Not "Login"
    # or "Reset": German copy uses both.
    "username",
    "email address",
    "this field",
    "too short",
    "too common",
    "numeric",
    "similar",
    "sign up",
    "log in",
    "forgot",
    "new password",
    "old password",
    "confirmation",
    "didn",
    "incorrectly",
    "inactive",
    "send",
)


def visible_text(html):
    """What a reader actually sees: no markup, no code, no URLs.

    strip_tags leaves the *contents* of <script> in place, and this codebase
    inlines four of them into base.html — a detector run over the raw page
    would trip over `sessionStorage` rather than over a label. URLs go the
    same way: the share page prints its join link for people to type, and
    `/join/<id>/` is a route, not a sentence. A path is never copy.

    <code> and <pre> go with them, added in S17 for `/map/upload/`: that page
    documents the map file's schema, and `nodes`, `start_node` and
    `speed_limit` are field names. They stay English by the same rule the
    model fields do, so reading them as untranslated copy would make the
    detector an argument for renaming the API.
    """
    without_code = re.sub(
        r"<(script|style|code|pre)\b.*?</\1>", " ", html, flags=re.S | re.I
    )
    without_urls = re.sub(r"\S*(?:https?://|/)\S*", " ", strip_tags(without_code))
    return re.sub(r"\s+", " ", without_urls).strip()


def english_in(text):
    """The English in `text`, or an empty list.

    Whole words only, so a German word that happens to contain an English one
    is not a hit. The point is to catch a string nobody translated, never to
    pin the words of one that somebody did — an assertion on exact copy would
    make every rewording a red pipeline, which is worth less than the copy.
    """
    pattern = re.compile(
        r"\b(?:%s)\b" % "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in ENGLISH_GIVEAWAYS),
        re.I,
    )
    return sorted({match.lower() for match in pattern.findall(text)})
