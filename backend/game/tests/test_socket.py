"""The game websocket (GameConsumer) and the roster behind it.

Two kinds of tests:

- game.roster is sync. What the roster says, and when it is sent, is tested in
  TestCase classes that call it directly and listen on the in-memory layer.
- The socket goes through WebsocketCommunicator under TransactionTestCase: the
  consumer awaits database_sync_to_async, and that closes the connection
  TestCase's wrapping transaction lives on.

NO_REDIS points REDIS_URL at a port nothing listens on. CI has no Redis, and
the game socket must not need one: presence goes through the Django cache,
in-memory here. Only ChatConsumer still talks to Redis directly.

game.roster is imported inside the tests. It doesn't exist before the
roster-from-db guide, and a top-level import would turn the whole file into
one import error.
"""

import asyncio
import json
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.utils import timezone

from co2mmute.utils import sign_value
from game.consumers import GameConsumer
from game.models import (
    GameRound,
    GameSession,
    MapVersionVote,
    Player,
    PlayerMove,
    StatsAck,
)
from game.routing import websocket_urlpatterns
from game.signals import round_completed
from maps.models import GameMap, MapVersion

from ._helpers import (
    TEST_BACKENDS,
    GroupListener,
    TempMediaRootMixin,
    create_game_session,
    create_host,
    muted,
)

# Port 9 is "discard"; nothing answers there, so any raw Redis call fails fast.
NO_REDIS = dict(REDIS_URL="redis://127.0.0.1:9/0")


def roster():
    from game import roster as module

    return module


def player_cookies(game_id, player_id):
    """Both player cookies in the 1.2 format."""
    return {
        f"{settings.COOKIE_GAME_PREFIX}{game_id}": sign_value(
            f"{game_id}:test-token", settings.COOKIE_GAME_SALT
        ),
        f"{settings.COOKIE_PLAYER_PREFIX}{game_id}": sign_value(
            f"{game_id}:{player_id}", settings.COOKIE_PLAYER_SALT
        ),
    }


def cookie_header(cookies):
    return "; ".join(f"{name}={value}" for name, value in cookies.items()).encode()


def player_cookie_header(game_id, player_id):
    return cookie_header(player_cookies(game_id, player_id))


def entry(players, player):
    """The roster entry for one Player row, found by its current player_id."""
    return next((p for p in players if p["player_id"] == player.player_id), None)


class GameWithSeatsMixin(TempMediaRootMixin):
    """A running game: the host's own row, Anna and Ben, no round yet.

    is_active goes in with .update(): GameSession.save() resets it whenever
    game_map is None.
    """

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Roster")
            self.host_row = Player.objects.create(
                game=self.game, name="Host", user=self.host, controlled_by_host=True
            )
            self.anna = Player.objects.create(game=self.game, name="Anna")
            self.ben = Player.objects.create(game=self.game, name="Ben")
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=True, started_at=timezone.now()
        )
        self.game.refresh_from_db()

    def open_round(self, **fields):
        fields.setdefault("status", GameRound.Status.ACTIVE)
        return GameRound.objects.create(game=self.game, round_number=1, **fields)

    def build(self):
        with muted():
            return roster().build(self.game)

    def connect(self, player):
        with muted():
            roster().connected(self.game.game_id, player.pk)

    def disconnect(self, player):
        with muted():
            roster().disconnected(self.game.game_id, player.pk)

    def ping(self, player):
        with muted():
            roster().heartbeat(self.game.game_id, player.pk)


# ─────────────────────────────────────────────────────────────────────────────
# What the roster says
# ─────────────────────────────────────────────────────────────────────────────


@override_settings(**TEST_BACKENDS)
class RosterContentTests(GameWithSeatsMixin, TestCase):
    """The roster comes from the Player rows. Presence is the only thing the
    cache adds; the status follows from the game."""

    def test_every_seat_is_listed_in_join_order_without_a_socket(self):
        players = self.build()

        self.assertEqual(
            [p["player_id"] for p in players],
            [self.host_row.player_id, self.anna.player_id, self.ben.player_id],
        )
        anna = entry(players, self.anna)
        self.assertFalse(anna["online"])
        self.assertEqual(anna["status"], "not_connected")

    def test_an_entry_has_the_shape_the_frontend_reads(self):
        self.connect(self.anna)

        self.assertEqual(
            entry(self.build(), self.anna),
            {
                "player_id": self.anna.player_id,
                "name": "Anna",
                "is_host": False,
                "controlled_by_host": False,
                "online": True,
                "status": "ready",
            },
        )

    def test_only_the_host_row_is_the_host(self):
        players = self.build()

        self.assertEqual(
            [p["player_id"] for p in players if p["is_host"]],
            [self.host_row.player_id],
        )

    def test_a_player_who_left_is_not_listed(self):
        Player.objects.filter(pk=self.ben.pk).update(left_at=timezone.now())

        self.assertIsNone(entry(self.build(), self.ben))

    def test_a_deleted_player_is_not_listed(self):
        with muted():
            self.ben.delete()

        self.assertEqual(len(self.build()), 2)

    def test_statuses_while_a_round_is_open(self):
        game_round = self.open_round()
        with muted():
            PlayerMove.objects.create(
                session_round=game_round, player=self.anna, action="car"
            )
        for seat in (self.host_row, self.anna, self.ben):
            self.connect(seat)

        players = self.build()

        self.assertEqual(entry(players, self.anna)["status"], "waiting")
        self.assertEqual(entry(players, self.ben)["status"], "making_move")
        self.assertEqual(entry(players, self.host_row)["status"], "ready")

    def test_statuses_between_rounds_are_ready(self):
        self.open_round(
            status=GameRound.Status.COMPLETED,
            between_round_phase=GameRound.BetweenRoundPhase.STATS,
        )
        self.connect(self.ben)

        self.assertEqual(entry(self.build(), self.ben)["status"], "ready")

    def test_offline_wins_over_the_round(self):
        self.open_round()

        self.assertEqual(entry(self.build(), self.ben)["status"], "not_connected")

    def test_disconnecting_takes_the_seat_offline(self):
        self.connect(self.anna)
        self.disconnect(self.anna)

        self.assertFalse(entry(self.build(), self.anna)["online"])

    def test_presence_runs_out_without_a_ping(self):
        """What a backend restart leaves behind: nobody calls disconnected().

        Before, the player stayed "online" in Redis for good. The presence key
        has to expire by itself.
        """
        with patch("game.roster.PRESENCE_TTL", 0):
            self.connect(self.anna)

        self.assertFalse(entry(self.build(), self.anna)["online"])

    def test_presence_follows_the_row_not_the_player_id(self):
        """1.7 gives a seat a new player_id. It stays online."""
        self.connect(self.anna)
        Player.objects.filter(pk=self.anna.pk).update(player_id="P-NEU1")
        self.anna.refresh_from_db()

        self.assertTrue(entry(self.build(), self.anna)["online"])

    def test_a_seat_at_the_host_machine_is_there_when_the_host_is(self):
        """It has no socket of its own (1.6)."""
        with muted():
            seat = Player.objects.create(
                game=self.game, name="Ohne Handy", controlled_by_host=True
            )
        self.assertFalse(entry(self.build(), seat)["online"])

        self.connect(self.host_row)

        self.assertTrue(entry(self.build(), seat)["online"])


# ─────────────────────────────────────────────────────────────────────────────
# When the roster is sent
# ─────────────────────────────────────────────────────────────────────────────


@override_settings(**TEST_BACKENDS)
class RosterBroadcastTests(GameWithSeatsMixin, TestCase):
    """Every change that shows in the roster sends a fresh one to the game.

    The signal-side broadcasts run on commit. Without
    captureOnCommitCallbacks(execute=True) they never run inside a TestCase.
    """

    def listen(self):
        return GroupListener(self.game.game_id)

    def last_roster(self, listener):
        rosters = listener.rosters()
        self.assertTrue(rosters, msg=f"no roster sent, got {listener.messages()}")
        return rosters[-1]

    def test_connecting_sends_the_roster(self):
        listener = self.listen()

        self.connect(self.anna)

        self.assertTrue(entry(self.last_roster(listener), self.anna)["online"])

    def test_disconnecting_sends_the_roster(self):
        self.connect(self.anna)
        listener = self.listen()

        self.disconnect(self.anna)

        self.assertFalse(entry(self.last_roster(listener), self.anna)["online"])

    def test_a_ping_on_a_live_seat_sends_nothing(self):
        self.connect(self.anna)
        listener = self.listen()

        self.ping(self.anna)

        self.assertEqual(listener.rosters(), [])

    def test_a_ping_brings_an_expired_seat_back(self):
        """The key ran out, or another tab of the same player disconnected.
        The others still see the seat offline until someone tells them."""
        self.connect(self.anna)
        cache.clear()
        listener = self.listen()

        self.ping(self.anna)

        self.assertTrue(entry(self.last_roster(listener), self.anna)["online"])

    def test_joining_sends_the_roster(self):
        listener = self.listen()

        with muted(), self.captureOnCommitCallbacks(execute=True):
            cem = Player.objects.create(game=self.game, name="Cem")

        self.assertIsNotNone(entry(self.last_roster(listener), cem))

    def test_leaving_sends_the_roster_without_the_player(self):
        listener = self.listen()

        with muted(), self.captureOnCommitCallbacks(execute=True):
            self.ben.delete()

        players = self.last_roster(listener)
        self.assertIsNone(entry(players, self.ben))
        self.assertIsNotNone(entry(players, self.anna))

    def test_a_move_sends_the_roster(self):
        game_round = self.open_round()
        self.connect(self.anna)
        self.client.cookies.load(player_cookies(self.game.game_id, self.anna.player_id))
        listener = self.listen()

        with muted(), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/game/{self.game.game_id}/player/{self.anna.player_id}/move/",
                {"action": "car", "payload": {}},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PlayerMove.objects.filter(
                session_round=game_round, player=self.anna
            ).exists()
        )
        self.assertEqual(
            entry(self.last_roster(listener), self.anna)["status"], "waiting"
        )

    def test_starting_the_game_sends_the_roster(self):
        """The host's start creates round 1. Everyone is choosing now."""
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=False,
            started_at=None,
            game_map=GameMap.objects.create(name="Leer"),
        )
        self.connect(self.anna)
        self.client.force_login(self.host)
        listener = self.listen()

        with muted(), self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f"/api/game/{self.game.game_id}/",
                {"is_active": True},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            entry(self.last_roster(listener), self.anna)["status"], "making_move"
        )

    def test_a_completed_round_sends_the_roster(self):
        game_round = self.open_round(status=GameRound.Status.COMPLETED)
        with muted():
            PlayerMove.objects.create(
                session_round=game_round, player=self.anna, action="car"
            )
        self.connect(self.anna)
        listener = self.listen()

        with muted():
            round_completed.send(
                sender=GameRound, game_session=self.game, game_round=game_round
            )

        self.assertIn("round.completed", listener.names())
        self.assertEqual(
            entry(self.last_roster(listener), self.anna)["status"], "ready"
        )

    def test_a_new_round_sends_the_roster(self):
        from game import phases

        self.open_round(
            status=GameRound.Status.COMPLETED,
            between_round_phase=GameRound.BetweenRoundPhase.STATS,
        )
        self.connect(self.anna)
        listener = self.listen()

        with muted():
            phases.ack_stats(self.game.game_id, self.anna.player_id)
            phases.ack_stats(self.game.game_id, self.ben.player_id)

        self.assertIn("round.started", listener.names())
        self.assertEqual(
            entry(self.last_roster(listener), self.anna)["status"], "making_move"
        )


@override_settings(**TEST_BACKENDS)
class RevokeTests(GameWithSeatsMixin, TestCase):
    """A removed seat's sockets are told to go, through the seat's own group."""

    def listen_to(self, player):
        return GroupListener(group=roster().player_group(player.pk))

    def revocations(self, listener):
        return [
            message["reason"]
            for message in listener.messages()
            if message.get("type") == "player_revoked"
        ]

    def test_the_host_removing_a_player_revokes_with_removed(self):
        listener = self.listen_to(self.anna)
        self.anna._was_kicked = True

        with muted(), self.captureOnCommitCallbacks(execute=True):
            self.anna.delete()

        self.assertEqual(self.revocations(listener), ["removed"])

    def test_a_player_leaving_revokes_with_left(self):
        listener = self.listen_to(self.anna)

        with muted(), self.captureOnCommitCallbacks(execute=True):
            self.anna.delete()

        self.assertEqual(self.revocations(listener), ["left"])

    def test_nobody_else_is_revoked(self):
        listener = self.listen_to(self.ben)

        with muted(), self.captureOnCommitCallbacks(execute=True):
            self.anna.delete()

        self.assertEqual(self.revocations(listener), [])

    def test_a_removal_that_rolls_back_revokes_nothing(self):
        listener = self.listen_to(self.anna)

        with muted(), self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.anna.delete()
                    raise RuntimeError("rolled back")
            except RuntimeError:
                pass

        self.assertEqual(self.revocations(listener), [])


# ─────────────────────────────────────────────────────────────────────────────
# Over a real socket
# ─────────────────────────────────────────────────────────────────────────────


async def read_until(communicator, stop, timeout=2):
    """Collect outputs until stop(output) is true.

    Sends are decoded to dicts; a close stays {"type": "websocket.close", ...}.
    A timeout cancels the application (asgiref does that), so it is a failure
    here, not a way to wait.
    """
    seen = []
    while True:
        try:
            output = await communicator.receive_output(timeout)
        except asyncio.TimeoutError:
            raise AssertionError(f"gave up waiting, got {seen}") from None
        if output["type"] == "websocket.send":
            output = json.loads(output["text"])
        seen.append(output)
        if stop(output):
            return seen


def is_roster_where(player, **fields):
    """A stop condition: a roster.update whose entry for player matches fields."""

    def stop(output):
        if output.get("type") != "roster.update":
            return False
        found = entry(output["players"], player)
        if "listed" in fields:
            return (found is not None) == fields["listed"]
        return found is not None and all(found[k] == v for k, v in fields.items())

    return stop


def is_type(name):
    return lambda output: output.get("type") == name


@override_settings(**TEST_BACKENDS, **NO_REDIS)
class SocketTests(GameWithSeatsMixin, TransactionTestCase):
    """What a connected client sees. The whole stack from the production ASGI
    app down: session + auth middleware, the URL router, the consumer."""

    def socket(self, cookies):
        return WebsocketCommunicator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
            f"/ws/game/{self.game.game_id}/",
            headers=[(b"cookie", cookie_header(cookies))],
        )

    def player_socket(self, player):
        return self.socket(player_cookies(self.game.game_id, player.player_id))

    def host_cookies(self):
        """A logged-in host session. Sync: call it before the async scenario."""
        self.client.force_login(self.host)
        session = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        return {settings.SESSION_COOKIE_NAME: session}

    def run_async(self, scenario):
        with muted():
            async_to_sync(scenario)()

    def test_connecting_lists_everyone_and_the_player_online(self):
        async def scenario():
            anna = self.player_socket(self.anna)
            connected, _ = await anna.connect()
            self.assertTrue(connected)

            seen = await read_until(anna, is_roster_where(self.anna, online=True))
            players = seen[-1]["players"]
            self.assertFalse(entry(players, self.ben)["online"])
            self.assertTrue(entry(players, self.host_row)["is_host"])
            await anna.disconnect()

        self.run_async(scenario)

    def test_the_others_see_a_player_go_offline(self):
        async def scenario():
            anna = self.player_socket(self.anna)
            ben = self.player_socket(self.ben)
            await anna.connect()
            await ben.connect()
            await read_until(ben, is_roster_where(self.anna, online=True))

            await anna.disconnect()

            await read_until(ben, is_roster_where(self.anna, online=False))
            await ben.disconnect()

        self.run_async(scenario)

    def test_a_ping_is_answered(self):
        async def scenario():
            anna = self.player_socket(self.anna)
            await anna.connect()

            await anna.send_json_to({"type": "ping"})

            await read_until(anna, is_type("pong"))
            await anna.disconnect()

        self.run_async(scenario)

    def game_state(self):
        async def scenario():
            anna = self.player_socket(self.anna)
            await anna.connect()
            seen = await read_until(anna, is_type("game.state"))
            await anna.disconnect()
            return seen[-1]["data"]

        with muted():
            return async_to_sync(scenario)()

    def test_the_game_state_of_a_running_game_is_not_paused(self):
        """Roadmap.md 1.6: a client that connects during the break must know."""
        self.assertIsNone(self.game_state()["pausedAt"])

    def test_the_game_state_says_the_game_is_paused(self):
        paused_at = timezone.now()
        GameSession.objects.filter(pk=self.game.pk).update(paused_at=paused_at)

        self.assertEqual(self.game_state()["pausedAt"], paused_at.isoformat())

    def kick(self, player):
        player._was_kicked = True
        player.delete()

    def test_a_removed_player_is_told_and_disconnected(self):
        async def scenario():
            anna = self.player_socket(self.anna)
            ben = self.player_socket(self.ben)
            await anna.connect()
            await ben.connect()
            await read_until(ben, is_roster_where(self.anna, online=True))

            await database_sync_to_async(self.kick)(self.anna)

            seen = await read_until(anna, is_type("websocket.close"))
            revoked = [m for m in seen if m.get("type") == "player.revoked"]
            self.assertEqual(revoked[0]["data"], {"reason": "removed"})
            self.assertEqual(seen[-1]["code"], 4403)

            # Ben stays, and sees Anna gone.
            await read_until(ben, is_roster_where(self.anna, listed=False))
            await ben.send_json_to({"type": "ping"})
            await read_until(ben, is_type("pong"))

            await anna.disconnect()
            await ben.disconnect()

        self.run_async(scenario)

    def test_a_player_who_leaves_is_told_why(self):
        async def scenario():
            anna = self.player_socket(self.anna)
            await anna.connect()
            await read_until(anna, is_type("roster.update"))

            await database_sync_to_async(self.anna.delete)()

            seen = await read_until(anna, is_type("player.revoked"))
            self.assertEqual(seen[-1]["data"], {"reason": "left"})
            await anna.disconnect()

        self.run_async(scenario)

    def test_the_host_is_their_own_row(self):
        """The host's socket used to be keyed by username[:5], a name no
        Player row has."""

        cookies = self.host_cookies()

        async def scenario():
            host = self.socket(cookies)
            connected, _ = await host.connect()
            self.assertTrue(connected)

            seen = await read_until(
                host, is_roster_where(self.host_row, online=True, is_host=True)
            )
            hosts = [p for p in seen[-1]["players"] if p["is_host"]]
            self.assertEqual(len(hosts), 1)
            await host.disconnect()

        self.run_async(scenario)

    def test_a_game_without_a_host_row_still_lets_the_host_in(self):
        """Games from before December 2025 have no host row."""
        with muted():
            self.host_row.delete()

        cookies = self.host_cookies()

        async def scenario():
            host = self.socket(cookies)
            connected, _ = await host.connect()
            self.assertTrue(connected)

            seen = await read_until(host, is_type("roster.update"))
            self.assertFalse([p for p in seen[-1]["players"] if p["is_host"]])
            await host.disconnect()

        self.run_async(scenario)


@override_settings(**TEST_BACKENDS, **NO_REDIS)
class HostSocketSpeaksForSeatsTests(GameWithSeatsMixin, TransactionTestCase):
    """A host socket acks and votes for the seats played at the host machine.
    Roadmap.md 1.6. It used to drop every ack and vote the host sent.

    A player's socket still only ever votes for its own seat, whatever
    player_id the message carries.
    """

    def setUp(self):
        super().setUp()
        with muted():
            self.cem = Player.objects.create(
                game=self.game, name="Cem", controlled_by_host=True
            )
        game_map = GameMap.objects.create(name="Testkarte")
        base = MapVersion.objects.create(
            game_map=game_map, name="Basis", base_version=True
        )
        self.option = MapVersion.objects.create(
            game_map=game_map, name="Option", source_version=base
        )
        base.compatible_versions.add(self.option)
        GameSession.objects.filter(pk=self.game.pk).update(
            game_map=game_map, map_updates=True, active_map_version=base
        )
        self.round = GameRound.objects.create(
            game=self.game,
            round_number=1,
            status=GameRound.Status.COMPLETED,
            between_round_phase=GameRound.BetweenRoundPhase.VOTING,
            vote_option_ids=[self.option.pk],
        )

    def socket(self, cookies):
        return WebsocketCommunicator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
            f"/ws/game/{self.game.game_id}/",
            headers=[(b"cookie", cookie_header(cookies))],
        )

    def host_cookies(self):
        self.client.force_login(self.host)
        session = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        return {settings.SESSION_COOKIE_NAME: session}

    def send_and_read(self, cookies, message, until):
        """Connect, send one message, read until `until`, hang up."""

        async def scenario():
            communicator = self.socket(cookies)
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to(message)
            seen = await read_until(communicator, until)
            await communicator.disconnect()
            return seen

        with muted():
            return async_to_sync(scenario)()

    def test_the_host_votes_for_a_seat_at_the_host_machine(self):
        seen = self.send_and_read(
            self.host_cookies(),
            {
                "type": "vote.submit",
                "version_id": self.option.pk,
                "player_id": self.cem.player_id,
            },
            is_type("vote.recorded"),
        )

        self.assertEqual(seen[-1]["data"]["player_id"], self.cem.player_id)
        self.assertTrue(
            MapVersionVote.objects.filter(
                player=self.cem, map_version=self.option
            ).exists()
        )

    def test_the_host_cannot_vote_for_a_student(self):
        seen = self.send_and_read(
            self.host_cookies(),
            {
                "type": "vote.submit",
                "version_id": self.option.pk,
                "player_id": self.anna.player_id,
            },
            is_type("error"),
        )

        self.assertTrue(seen)
        self.assertFalse(MapVersionVote.objects.exists())

    def test_a_player_votes_for_themselves_whatever_the_message_says(self):
        """A guard, green from the start."""
        seen = self.send_and_read(
            player_cookies(self.game.game_id, self.anna.player_id),
            {
                "type": "vote.submit",
                "version_id": self.option.pk,
                "player_id": self.cem.player_id,
            },
            is_type("vote.recorded"),
        )

        self.assertEqual(seen[-1]["data"]["player_id"], self.anna.player_id)
        self.assertFalse(MapVersionVote.objects.filter(player=self.cem).exists())

    def test_the_host_ack_covers_the_seats_at_the_host_machine(self):
        GameRound.objects.filter(pk=self.round.pk).update(
            between_round_phase=GameRound.BetweenRoundPhase.STATS
        )
        StatsAck.objects.create(game_round=self.round, player=self.anna)
        StatsAck.objects.create(game_round=self.round, player=self.ben)

        self.send_and_read(
            self.host_cookies(),
            {"type": "player.stats_ack"},
            is_type("stats.all_acked"),
        )

        self.assertTrue(StatsAck.objects.filter(player=self.cem).exists())


@override_settings(**TEST_BACKENDS, **NO_REDIS)
class HandoverSocketTests(GameWithSeatsMixin, TransactionTestCase):
    """Roadmap.md 1.7: when a seat moves, the old device's socket is told and
    closed. Taking over and handing on both give the seat a new player_id,
    so the old cookie can't come back either.

    game.seats is imported inside the tests; the handover part of it doesn't
    exist before the seat-handover guide.
    """

    def socket(self, cookies):
        return WebsocketCommunicator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
            f"/ws/game/{self.game.game_id}/",
            headers=[(b"cookie", cookie_header(cookies))],
        )

    def player_socket(self, player_id):
        return self.socket(player_cookies(self.game.game_id, player_id))

    def run_async(self, scenario):
        with muted():
            async_to_sync(scenario)()

    async def assert_revoked(self, communicator, reason):
        seen = await read_until(communicator, is_type("websocket.close"))
        revoked = [m for m in seen if m.get("type") == "player.revoked"]
        self.assertEqual(revoked[0]["data"], {"reason": reason})
        self.assertEqual(seen[-1]["code"], 4403)

    def test_taking_a_seat_over_closes_the_students_socket(self):
        from game.seats import take_over

        async def scenario():
            anna = self.player_socket(self.anna.player_id)
            await anna.connect()
            await read_until(anna, is_type("roster.update"))

            await database_sync_to_async(take_over)(self.anna)

            await self.assert_revoked(anna, "taken_over")
            await anna.disconnect()

        self.run_async(scenario)

    def test_a_handed_on_seat_moves_to_the_new_device(self):
        from game.seats import issue_code, redeem_code

        async def scenario():
            old_phone = self.player_socket(self.anna.player_id)
            await old_phone.connect()
            await read_until(old_phone, is_type("roster.update"))

            code = await database_sync_to_async(issue_code)(self.anna)
            seat, _old_id = await database_sync_to_async(redeem_code)(code)

            await self.assert_revoked(old_phone, "handed_over")
            new_phone = self.player_socket(seat.player_id)
            connected, _ = await new_phone.connect()
            self.assertTrue(connected)
            await read_until(new_phone, is_roster_where(seat, online=True))

            await old_phone.disconnect()
            await new_phone.disconnect()

        self.run_async(scenario)

    def test_the_old_cookie_no_longer_connects(self):
        from game.seats import take_over

        old_id = self.anna.player_id
        with muted():
            take_over(self.anna)

        async def scenario():
            old_phone = self.player_socket(old_id)
            connected, code = await old_phone.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4403)

        self.run_async(scenario)

    def test_the_other_players_stay(self):
        from game.seats import take_over

        async def scenario():
            ben = self.player_socket(self.ben.player_id)
            await ben.connect()
            await read_until(ben, is_type("roster.update"))

            await database_sync_to_async(take_over)(self.anna)

            await read_until(ben, is_type("player.taken_over"))
            await ben.send_json_to({"type": "ping"})
            await read_until(ben, is_type("pong"))
            await ben.disconnect()

        self.run_async(scenario)


@override_settings(**TEST_BACKENDS, **NO_REDIS)
class RoundStartedReachesTheSocketTests(TempMediaRootMixin, TransactionTestCase):
    """round.started never reached the players (fixed by the phase-module guide).

    The consumer's _start_next_round called send_game_state_message, which
    uses async_to_sync, from inside the event loop. asgiref refuses that with
    `RuntimeError: You cannot use AsyncToSync in the same thread as an async
    event loop`. The round was created, the broadcast never went out, and the
    socket that sent the last ack died with the exception.

    No session middleware in front of the router: the host check in
    resolve_player needs one and is skipped, so the cookies decide.
    """

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Socket")
            self.player = Player.objects.create(game=self.game, name="Anna")
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=True, started_at=timezone.now()
        )
        GameRound.objects.create(
            game=self.game,
            round_number=1,
            status=GameRound.Status.COMPLETED,
            between_round_phase=GameRound.BetweenRoundPhase.STATS,
        )

    async def ack_and_listen(self):
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            f"/ws/game/{self.game.game_id}/",
            headers=[
                (
                    b"cookie",
                    player_cookie_header(self.game.game_id, self.player.player_id),
                )
            ],
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        received = []
        try:
            await communicator.send_json_to({"type": "player.stats_ack"})
            while True:
                message = await communicator.receive_json_from(timeout=2)
                received.append(message)
                if message["type"] == "round.started":
                    break
        except asyncio.TimeoutError:
            pass
        finally:
            await communicator.disconnect()
        return received

    def test_the_last_stats_ack_announces_the_next_round(self):
        with muted():
            received = async_to_sync(self.ack_and_listen)()

        types = [message["type"] for message in received]
        self.assertIn("stats.all_acked", types)
        self.assertIn("round.started", types, msg=f"received only {types}")
        started = next(m for m in received if m["type"] == "round.started")
        self.assertEqual(started["data"]["round_number"], 2)
        self.assertEqual(started["game_id"], self.game.game_id)


class ConsumerIsTransportOnlyTests(SimpleTestCase):
    """The consumer turns messages into game.phases / game.roster calls.

    Everything below moved to game/phases.py, game/roster.py or is gone. A
    method left behind here is a second copy of a rule, which is how the
    counting rule ended up written nine times.
    """

    MOVED = (
        # phase-module
        "_check_all_stats_acked",
        "_advance_from_stats",
        "_check_between_round_completion_after_leave",
        "_get_voteable_versions_async",
        "_set_round_phase",
        "_record_vote",
        "_get_vote_progress",
        "_tally_votes",
        "_resolve_stalemate_votes",
        "_reopen_voting_after_stalemate",
        "_apply_stalemate_leave_as_is",
        "_get_stalemate_vote_progress",
        "_start_next_round",
        "_stats_ack_key",
        # roster-from-db
        "_roster_key",
        "_player_status_key",
        "_register_player_online",
        "_mark_player_disconnected",
        "_get_roster",
        "_broadcast_roster",
        "_set_all_players_status",
        "player_status_update",
    )

    def test_the_phase_and_roster_rules_left_the_consumer(self):
        left_behind = [name for name in self.MOVED if hasattr(GameConsumer, name)]

        self.assertEqual(left_behind, [])

    def test_the_ballot_helpers_have_one_home(self):
        import game.consumers as consumers
        import game.signals as signals

        for module in (consumers, signals):
            for name in ("_is_rollback_target", "_get_delta_img_url"):
                self.assertFalse(
                    hasattr(module, name),
                    msg=f"{module.__name__}.{name} should live in game.phases",
                )

    def test_the_status_side_channel_is_gone(self):
        """Statuses follow from the game now. Nothing sends them one by one."""
        import co2mmute.utils as utils

        self.assertFalse(hasattr(utils, "send_player_status_update"))
