"""The game websocket (GameConsumer), end to end through WebsocketCommunicator.

TransactionTestCase for anything that connects: the consumer awaits
database_sync_to_async, and that closes the connection TestCase's wrapping
transaction lives on (CLAUDE.md, backend test conventions).

The roster still lives in raw Redis, and a test run has no Redis. The roster
methods are stubbed out below. The roster-from-db guide moves the roster to the
Player rows; that guide removes the stubs and adds its own tests here.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone

from co2mmute.utils import sign_value
from game.consumers import GameConsumer
from game.models import GameRound, GameSession, Player
from game.routing import websocket_urlpatterns

from ._helpers import (
    TEST_BACKENDS,
    TempMediaRootMixin,
    create_game_session,
    create_host,
    muted,
)


def roster_stubs():
    """Fresh stubs per test, so no call history leaks between tests."""
    return {
        "_register_player_online": AsyncMock(),
        "_mark_player_disconnected": AsyncMock(),
        "_broadcast_roster": AsyncMock(),
        "_set_all_players_status": AsyncMock(),
        "_get_roster": AsyncMock(return_value=[]),
    }


def player_cookie_header(game_id, player_id):
    """Both cookies in the 1.2 format, as one Cookie header."""
    cookies = {
        f"{settings.COOKIE_GAME_PREFIX}{game_id}": sign_value(
            f"{game_id}:test-token", settings.COOKIE_GAME_SALT
        ),
        f"{settings.COOKIE_PLAYER_PREFIX}{game_id}": sign_value(
            f"{game_id}:{player_id}", settings.COOKIE_PLAYER_SALT
        ),
    }
    return "; ".join(f"{name}={value}" for name, value in cookies.items()).encode()


@override_settings(**TEST_BACKENDS)
class RoundStartedReachesTheSocketTests(TempMediaRootMixin, TransactionTestCase):
    """round.started never reached the players.

    The consumer's _start_next_round called send_game_state_message, which
    uses async_to_sync, from inside the event loop. asgiref refuses that with
    `RuntimeError: You cannot use AsyncToSync in the same thread as an async
    event loop`. The round was created, the broadcast never went out, and the
    socket that sent the last ack died with the exception. Clients only saw the
    new round through their 2 s polling (Roadmap.md 2.4, "runden counter").

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
        with muted(), patch.multiple(GameConsumer, **roster_stubs()):
            received = async_to_sync(self.ack_and_listen)()

        types = [message["type"] for message in received]
        self.assertIn("stats.all_acked", types)
        self.assertIn("round.started", types, msg=f"received only {types}")
        started = next(m for m in received if m["type"] == "round.started")
        self.assertEqual(started["data"]["round_number"], 2)
        self.assertEqual(started["game_id"], self.game.game_id)


class ConsumerIsTransportOnlyTests(SimpleTestCase):
    """After the split the consumer turns messages into game.phases calls.

    Everything below moved to game/phases.py or is gone. A method left behind
    here is a second copy of a rule, which is how the counting rule ended up
    written nine times.
    """

    MOVED = (
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
    )

    def test_the_phase_rules_left_the_consumer(self):
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
