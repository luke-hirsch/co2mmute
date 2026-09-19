from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from co2mmute.utils import sign_value
from game.models import GameRound, GameSession, Player, PlayerMove
from game.signals import round_completed

from ._helpers import (
    TEST_BACKENDS,
    GroupListener,
    TempMediaRootMixin,
    create_game_session,
    create_host,
    muted,
)


@override_settings(**TEST_BACKENDS)
class RoundCompletionTests(TempMediaRootMixin, TestCase):
    """`handle_round_completed` must survive a round that does not end the game.

    The end-of-game branch returns early, so the tail of the handler — where the
    between-round STATS phase is entered — only runs when the game continues.
    That tail is the least-travelled path in the handler and the one that broke.

    The signal is sent explicitly rather than by letting a `PlayerMove` save
    trigger it, so these stay valid after `Roadmap.md` 1.1 changes *who* calls the
    handler. Two players with one move submitted keeps the `post_save` receiver
    from firing on its own and running the handler twice.
    """

    def setUp(self):
        self.user = create_host()
        with muted():
            self.game = create_game_session(self.user, game_name="Round completion")
            self.player = Player.objects.create(game=self.game, name="Tester")
            self.other_player = Player.objects.create(game=self.game, name="Second")

        self.round = GameRound.objects.create(
            game=self.game,
            round_number=1,
            status=GameRound.Status.ACTIVE,
        )

    def _submit_move(self):
        with muted():
            return PlayerMove.objects.create(
                session_round=self.round,
                player=self.player,
                action="car",
                payload={"agents": [{"id": 1, "action": "car"}]},
            )

    def _complete_round(self, **kwargs):
        defaults = {
            "sender": GameSession,
            "game_session": self.game,
            "game_round": self.round,
        }
        defaults.update(kwargs)
        with muted():
            round_completed.send(**defaults)

    def test_completing_a_round_enters_stats_phase(self):
        self._submit_move()

        self._complete_round()

        self.round.refresh_from_db()
        self.assertEqual(
            self.round.between_round_phase,
            GameRound.BetweenRoundPhase.STATS,
            msg="round should be waiting in the stats phase after completing",
        )
        self.assertEqual(self.round.status, GameRound.Status.COMPLETED)

    def test_completing_a_round_records_totals(self):
        self._submit_move()

        self._complete_round()

        self.round.refresh_from_db()
        self.assertGreater(self.round.total_emissions_g, 0.0)
        self.assertGreater(self.round.total_cost_eur, 0.0)

    def test_game_stays_active_when_no_end_condition_is_met(self):
        self._submit_move()

        self._complete_round()

        self.game.refresh_from_db()
        self.assertIsNone(self.game.ended_at)

    def test_resolves_the_round_from_game_id_alone(self):
        """The view-side caller sends only `game_id`; the handler looks the rest up."""
        self._submit_move()

        self._complete_round(
            sender=GameRound,
            game_session=None,
            game_round=None,
            game_id=self.game.game_id,
        )

        self.round.refresh_from_db()
        self.assertEqual(
            self.round.between_round_phase,
            GameRound.BetweenRoundPhase.STATS,
        )


# ---------------------------------------------------------------------------
# Roadmap.md 1.1 — one round-completion path
#
# game.rounds is imported inside the methods below, not at module level. The
# module does not exist yet, and a top-level import would take RoundCompletionTests
# above down with it — that class tests handle_round_completed, which this work
# does not change, and it needs to stay visibly green throughout.
# ---------------------------------------------------------------------------


class RoundFixtureMixin(TempMediaRootMixin):
    """A started game with an active round and two ordinary players.

    is_active is set with .update() rather than save(): GameSession.save() forces
    is_active back to False whenever game_map is None (models.py), and these tests
    are about round bookkeeping, not maps.
    """

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Consolidation")
            self.player = Player.objects.create(game=self.game, name="Erste")
            self.other_player = Player.objects.create(game=self.game, name="Zweite")

        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=True, started_at=timezone.now()
        )
        self.game.refresh_from_db()

        self.round = GameRound.objects.create(
            game=self.game,
            round_number=1,
            status=GameRound.Status.ACTIVE,
        )

    def submit_move(self, player):
        with muted():
            return PlayerMove.objects.create(
                session_round=self.round,
                player=player,
                action="car",
                payload={"agents": [{"id": 1, "action": "car"}]},
            )

    def complete_round_if_ready(self):
        from game.rounds import complete_round_if_ready

        with muted():
            return complete_round_if_ready(self.game.game_id)


@override_settings(**TEST_BACKENDS)
class CompleteRoundIfReadyTests(RoundFixtureMixin, TestCase):
    """The single decision point: is this round over?

    Counting rule, applied on both sides of the comparison: active
    (left_at__isnull=True) and not the host's own row, i.e.
    PlayerQuerySet.playing(). The post_save receiver this replaces counted every
    Player row, so a game anyone had left could never complete.
    """

    def test_returns_false_while_a_player_is_outstanding(self):
        self.submit_move(self.player)

        with patch("game.tasks.run_simulation_task.delay"):
            self.assertFalse(self.complete_round_if_ready())

        self.round.refresh_from_db()
        self.assertEqual(self.round.status, GameRound.Status.ACTIVE)

    def test_returns_true_once_every_active_player_has_moved(self):
        self.submit_move(self.player)
        self.submit_move(self.other_player)

        with patch("game.tasks.run_simulation_task.delay"):
            self.assertTrue(self.complete_round_if_ready())

        self.round.refresh_from_db()
        self.assertEqual(self.round.status, GameRound.Status.COMPLETED)

    def test_a_player_who_left_is_not_waited_for(self):
        with muted():
            self.other_player.left_at = timezone.now()
            self.other_player.save()
        self.submit_move(self.player)

        with patch("game.tasks.run_simulation_task.delay"):
            self.assertTrue(self.complete_round_if_ready())

    def test_the_hosts_own_row_is_not_waited_for(self):
        with muted():
            Player.objects.create(
                game=self.game,
                name="Host",
                user=self.host,
                controlled_by_host=True,
            )
        self.submit_move(self.player)
        self.submit_move(self.other_player)

        with patch("game.tasks.run_simulation_task.delay"):
            self.assertTrue(self.complete_round_if_ready())

    def test_a_seat_played_at_the_host_machine_is_waited_for(self):
        """controlled_by_host no longer means "the host's row" (Roadmap.md 1.6).

        A student playing at the host machine is a player like any other, and
        the round waits for their move too. Only the host's own row, found by
        account, is left out.
        """
        with muted():
            seat = Player.objects.create(
                game=self.game, name="Ohne Handy", controlled_by_host=True
            )
        self.submit_move(self.player)
        self.submit_move(self.other_player)

        with patch("game.tasks.run_simulation_task.delay"):
            self.assertFalse(self.complete_round_if_ready())

        self.submit_move(seat)

        with patch("game.tasks.run_simulation_task.delay"):
            self.assertTrue(self.complete_round_if_ready())

    def test_no_op_when_nobody_has_moved(self):
        with patch("game.tasks.run_simulation_task.delay"):
            self.assertFalse(self.complete_round_if_ready())

    def test_no_op_on_a_round_that_is_not_active(self):
        self.submit_move(self.player)
        self.submit_move(self.other_player)
        GameRound.objects.filter(pk=self.round.pk).update(
            status=GameRound.Status.COMPLETED
        )

        with patch("game.tasks.run_simulation_task.delay"):
            self.assertFalse(self.complete_round_if_ready())

    def test_no_op_on_a_game_that_is_not_running(self):
        self.submit_move(self.player)
        self.submit_move(self.other_player)
        GameSession.objects.filter(pk=self.game.pk).update(is_active=False)

        with patch("game.tasks.run_simulation_task.delay"):
            self.assertFalse(self.complete_round_if_ready())

    def test_unknown_game_is_survivable(self):
        from game.rounds import complete_round_if_ready

        with muted():
            self.assertFalse(complete_round_if_ready("NOPE12"))


@override_settings(**TEST_BACKENDS)
class RoundCompletionDispatchTests(RoundFixtureMixin, TestCase):
    """The claim, and what it hands to Celery."""

    def test_the_round_pk_goes_to_the_task(self):
        self.submit_move(self.player)
        self.submit_move(self.other_player)

        with patch("game.tasks.run_simulation_task.delay") as delay:
            self.complete_round_if_ready()

        delay.assert_called_once_with(self.round.pk)

    def test_only_the_first_caller_claims_the_round(self):
        """Two players submitting at the same instant both reach the check.

        Today nothing prevents a double run except the accidental ordering of the
        two old callers. The atomic status claim is what makes it deterministic.
        """
        self.submit_move(self.player)
        self.submit_move(self.other_player)

        with patch("game.tasks.run_simulation_task.delay") as delay:
            first = self.complete_round_if_ready()
            second = self.complete_round_if_ready()

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(delay.call_count, 1)

    def test_the_simulation_does_not_run_in_the_caller(self):
        """The whole point: the caller dispatches and returns.

        If TrafficSimulator is reachable from complete_round_if_ready the round is
        still being simulated on the Daphne worker that served the last move.
        """
        self.submit_move(self.player)
        self.submit_move(self.other_player)

        with patch("game.tasks.run_simulation_task.delay"):
            with patch("game.simulation.TrafficSimulator") as simulator:
                self.complete_round_if_ready()

        simulator.assert_not_called()


@override_settings(**TEST_BACKENDS)
class PostSaveReceiverGoneTests(RoundFixtureMixin, TestCase):
    """signals.check_round_completion fires too early and counts wrong.

    It runs inside PlayerMoveView.post's atomic block and *before* _store_routes,
    so when it triggers the round, handle_round_completed finds no AgentRoute and
    silently takes the legacy _calculate_hardcoded_stats branch instead of
    simulating. Saving a PlayerMove must no longer decide anything.
    """

    def test_saving_a_move_does_not_complete_the_round(self):
        self.submit_move(self.player)
        self.submit_move(self.other_player)

        self.round.refresh_from_db()
        self.assertEqual(
            self.round.status,
            GameRound.Status.ACTIVE,
            msg="a PlayerMove save must not complete the round on its own",
        )

    def test_the_receiver_is_gone_from_the_module(self):
        import game.signals as signals

        self.assertFalse(
            hasattr(signals, "check_round_completion"),
            msg="the post_save receiver on PlayerMove should be deleted outright",
        )


@override_settings(**TEST_BACKENDS)
class LeavingPlayerCompletesRoundTests(RoundFixtureMixin, TestCase):
    """Somebody leaving can be what completes the round — a real third trigger.

    cleanup_leaving_player keeps its post_delete hook but stops deciding for
    itself: it counted every Player row, and it gated on a round-number
    comparison that is false in exactly the common case.

    The receiver schedules the check with transaction.on_commit, and TestCase
    never commits — without captureOnCommitCallbacks(execute=True) the check
    never runs, and the negative case below would pass for the wrong reason.
    """

    def test_deleting_the_last_outstanding_player_completes_the_round(self):
        self.submit_move(self.player)

        with patch("game.tasks.run_simulation_task.delay") as delay:
            with muted(), self.captureOnCommitCallbacks(execute=True):
                self.other_player.delete()

        self.round.refresh_from_db()
        self.assertEqual(self.round.status, GameRound.Status.COMPLETED)
        delay.assert_called_once_with(self.round.pk)

    def test_deleting_a_player_while_others_are_outstanding_does_nothing(self):
        with muted():
            third = Player.objects.create(game=self.game, name="Dritte")
        self.submit_move(self.player)

        with patch("game.tasks.run_simulation_task.delay") as delay:
            with muted(), self.captureOnCommitCallbacks(execute=True):
                third.delete()

        self.round.refresh_from_db()
        self.assertEqual(self.round.status, GameRound.Status.ACTIVE)
        delay.assert_not_called()


@override_settings(**TEST_BACKENDS)
class PlayerMoveOnCommitTests(RoundFixtureMixin, TestCase):
    """PlayerMoveView must schedule the check on commit, not in a thread.

    The daemon thread got the ordering right by luck — it happened to start after
    the atomic block, so it saw committed routes. on_commit gets it right by
    definition, with no second DB connection and no exceptions vanishing into the
    surrounding `except Exception`.
    """

    def move_url(self, player):
        return f"/api/game/{self.game.game_id}/player/{player.player_id}/move/"

    def authenticate_as(self, player):
        game_name = f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}"
        player_name = f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        self.client.cookies[game_name] = sign_value(
            f"{self.game.game_id}:test-token", settings.COOKIE_GAME_SALT
        )
        # The 1.2 format: the player_id bound to its game inside the signature.
        self.client.cookies[player_name] = sign_value(
            f"{self.game.game_id}:{player.player_id}", settings.COOKIE_PLAYER_SALT
        )

    def post_move(self, player):
        with muted():
            return self.client.post(
                self.move_url(player),
                {"action": "car", "payload": {}},
                content_type="application/json",
            )

    def test_the_view_no_longer_owns_a_completion_check(self):
        from game.views_rest import PlayerMoveView

        self.assertFalse(
            hasattr(PlayerMoveView, "_check_round_completion"),
            msg="_check_round_completion belongs in game/rounds.py now",
        )

    def test_the_view_module_no_longer_imports_threading(self):
        import game.views_rest as views_rest

        self.assertFalse(
            hasattr(views_rest, "threading"),
            msg="the daemon thread is replaced by transaction.on_commit",
        )

    def test_the_last_move_completes_the_round_on_commit(self):
        self.submit_move(self.player)
        self.authenticate_as(self.other_player)

        # muted() wraps the capture, not the other way round: the callbacks run
        # when the capture block exits, and they log the dispatch.
        with patch("game.tasks.run_simulation_task.delay") as delay:
            with muted(), self.captureOnCommitCallbacks(execute=True):
                response = self.post_move(self.other_player)

        self.assertEqual(response.status_code, 200)
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, GameRound.Status.COMPLETED)
        delay.assert_called_once_with(self.round.pk)

    def test_nothing_completes_before_the_transaction_commits(self):
        """Captured but not executed: the round must still be open.

        This is the assertion that the check is genuinely deferred rather than
        called inline.
        """
        self.submit_move(self.player)
        self.authenticate_as(self.other_player)

        with patch("game.tasks.run_simulation_task.delay") as delay:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                self.post_move(self.other_player)

        # The round check, and (since roster-from-db) the roster broadcast.
        self.assertEqual(
            len(callbacks), 2, msg="the move view should register exactly two callbacks"
        )
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, GameRound.Status.ACTIVE)
        delay.assert_not_called()


# ---------------------------------------------------------------------------
# Roadmap.md 1.6 — the pause
#
# game.pause is imported inside the tests: it doesn't exist before the pause
# guide.
# ---------------------------------------------------------------------------


def pause_url(game_id):
    return f"/api/game/{game_id}/pause/"


def resume_url(game_id):
    return f"/api/game/{game_id}/resume/"


class PauseMixin(RoundFixtureMixin):
    def post(self, url):
        with muted(), self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, content_type="application/json")

    def pause(self):
        return self.post(pause_url(self.game.game_id))

    def resume(self):
        return self.post(resume_url(self.game.game_id))

    def paused_at(self):
        self.game.refresh_from_db()
        return self.game.paused_at


@override_settings(**TEST_BACKENDS)
class PauseEndpointTests(PauseMixin, TestCase):
    """POST api/game/<id>/pause/ and .../resume/ — the host's bell."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.host)

    def test_the_host_pauses_a_running_game(self):
        response = self.pause()

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(self.paused_at())
        self.assertEqual(response.json()["paused_at"], self.paused_at().isoformat())

    def test_pausing_is_announced(self):
        listener = GroupListener(self.game.game_id)

        self.pause()

        self.assertEqual(
            listener.data("game.paused"), {"paused_at": self.paused_at().isoformat()}
        )

    def test_pausing_counts_as_activity(self):
        """The idle end reads updated_at, and update() doesn't set it."""
        old = timezone.now() - timezone.timedelta(days=3)
        GameSession.objects.filter(pk=self.game.pk).update(updated_at=old)

        self.pause()

        self.game.refresh_from_db()
        self.assertGreater(self.game.updated_at, old)

    def test_a_paused_game_cannot_be_paused_again(self):
        self.pause()

        response = self.pause()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "paused")

    def test_a_lobby_cannot_be_paused(self):
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=False, started_at=None
        )

        response = self.pause()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "not_running")
        self.assertIsNone(self.paused_at())

    def test_an_ended_game_cannot_be_paused(self):
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=False, ended_at=timezone.now()
        )

        response = self.pause()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "not_running")

    def test_the_host_resumes(self):
        self.pause()
        listener = GroupListener(self.game.game_id)

        response = self.resume()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"paused_at": None})
        self.assertIsNone(self.paused_at())
        self.assertEqual(listener.data("game.resumed"), {})

    def test_a_running_game_cannot_be_resumed(self):
        response = self.resume()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "not_paused")

    def test_a_player_cannot_pause_or_resume(self):
        self.client.logout()
        game_name = f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}"
        player_name = f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        self.client.cookies[game_name] = sign_value(
            f"{self.game.game_id}:test-token", settings.COOKIE_GAME_SALT
        )
        self.client.cookies[player_name] = sign_value(
            f"{self.game.game_id}:{self.player.player_id}", settings.COOKIE_PLAYER_SALT
        )

        self.assertEqual(self.pause().status_code, 403)
        GameSession.objects.filter(pk=self.game.pk).update(paused_at=timezone.now())
        self.assertEqual(self.resume().status_code, 403)
        self.assertIsNotNone(self.paused_at())

    def test_another_host_cannot_pause(self):
        self.client.force_login(create_host(username="other-host"))

        self.assertEqual(self.pause().status_code, 403)
        self.assertIsNone(self.paused_at())

    def test_the_game_view_shows_the_pause(self):
        """GameSessionDetailView is the host's REST snapshot."""
        self.pause()

        with muted():
            payload = self.client.get(f"/api/game/{self.game.game_id}/").json()

        self.assertEqual(parse_datetime(payload["paused_at"]), self.paused_at())

    def test_stopping_a_paused_game_ends_the_pause(self):
        self.pause()

        with muted(), self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f"/api/game/{self.game.game_id}/",
                {"is_active": False},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.ended_at)
        self.assertIsNone(self.game.paused_at)


@override_settings(**TEST_BACKENDS)
class PausedRoundTests(PauseMixin, TestCase):
    """While paused, nobody moves and no round ends. Seats can still change."""

    def move_url(self, player):
        return f"/api/game/{self.game.game_id}/player/{player.player_id}/move/"

    def authenticate_as(self, player):
        self.client.cookies[f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}"] = (
            sign_value(f"{self.game.game_id}:test-token", settings.COOKIE_GAME_SALT)
        )
        self.client.cookies[f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"] = (
            sign_value(
                f"{self.game.game_id}:{player.player_id}", settings.COOKIE_PLAYER_SALT
            )
        )

    def set_paused(self):
        from game.pause import pause_game

        with muted():
            pause_game(self.game.game_id)

    def test_a_move_while_paused_is_refused(self):
        self.set_paused()
        self.authenticate_as(self.player)

        with muted():
            response = self.client.post(
                self.move_url(self.player),
                {"action": "car", "payload": {}},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "paused")
        self.assertFalse(PlayerMove.objects.exists())

    def test_a_paused_round_does_not_complete(self):
        self.submit_move(self.player)
        self.submit_move(self.other_player)
        self.set_paused()

        with patch("game.tasks.run_simulation_task.delay") as delay:
            self.assertFalse(self.complete_round_if_ready())

        delay.assert_not_called()
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, GameRound.Status.ACTIVE)

    def test_a_seat_that_leaves_during_the_pause_completes_the_round_on_resume(self):
        """The leave schedules the check, the pause stops it, resume runs it."""
        self.submit_move(self.player)
        self.set_paused()

        with patch("game.tasks.run_simulation_task.delay") as delay:
            with muted(), self.captureOnCommitCallbacks(execute=True):
                self.other_player.delete()
            delay.assert_not_called()

            self.client.force_login(self.host)
            self.resume()

        delay.assert_called_once_with(self.round.pk)
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, GameRound.Status.COMPLETED)

    def test_a_second_resume_dispatches_nothing(self):
        self.submit_move(self.player)
        self.submit_move(self.other_player)
        self.set_paused()
        self.client.force_login(self.host)

        with patch("game.tasks.run_simulation_task.delay") as delay:
            first = self.resume()
            second = self.resume()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        delay.assert_called_once_with(self.round.pk)

    def test_the_host_can_add_a_seat_while_paused(self):
        self.set_paused()
        self.client.force_login(self.host)

        with muted(), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/game/{self.game.game_id}/player/",
                {"name": "Nachzuegler"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 201)

    def test_the_host_can_remove_a_seat_while_paused(self):
        self.set_paused()
        self.client.force_login(self.host)

        with patch("game.tasks.run_simulation_task.delay"):
            with muted(), self.captureOnCommitCallbacks(execute=True):
                response = self.client.delete(
                    f"/api/game/{self.game.game_id}/player/{self.player.player_id}/"
                )

        self.assertEqual(response.status_code, 204)
        self.player.refresh_from_db()
        self.assertIsNotNone(self.player.left_at)


# ---------------------------------------------------------------------------
# Cost units — see `.claude/plans/to-do/[backend]-cost-units.md`.
#
# AgentSimulationResult.mean_cost_eur is per person; SimulationResult
# .total_cost_eur is the whole cohort. The round table sums the first into the
# player rows and prints the second as "Runde gesamt", so the rows come out
# exactly people_per_agent times too small. CO2 has no such problem: total_co2_g
# is already scaled when it is written.
# ---------------------------------------------------------------------------


class SimulatedRoundMixin(TempMediaRootMixin):
    """A round with a real map and real routes, so the simulation actually runs.

    `_run_simulation` is only reached when AgentRoutes exist
    (`signals.py:301`); without them the handler takes the hardcoded fallback
    and none of this is exercised.
    """

    people_per_agent = 1000

    def setUp(self):
        from maps.models import Edge, GameMap, MapVersion, Node, StreetEdge

        from game.models import AgentRoute, RouteSegment

        self.host = create_host()
        self.game_map = GameMap.objects.create(
            name="Kosten", x_dim=10, y_dim=10, scale=1000.0
        )
        version = MapVersion.objects.create(
            game_map=self.game_map, name="Base", base_version=True
        )
        node_a = Node.objects.create(
            game_map=self.game_map, name="Zuhause", x_position=0, y_position=0
        )
        node_a.map_versions.add(version)
        node_b = Node.objects.create(
            game_map=self.game_map, name="Arbeit", x_position=2, y_position=0
        )
        node_b.map_versions.add(version)
        edge = Edge.objects.create(
            game_map=self.game_map, start_node=node_a, end_node=node_b
        )
        edge.map_versions.add(version)
        street_edge = StreetEdge.objects.create(edge=edge, speed_limit=50, lanes=2)
        street_edge.map_versions.add(version)

        with muted():
            self.game = create_game_session(
                self.host,
                game_name="Kosten",
                game_map=self.game_map,
                people_per_agent=self.people_per_agent,
            )
            self.player = Player.objects.create(game=self.game, name="Anna")
            self.other = Player.objects.create(game=self.game, name="Bruno")

        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=True, started_at=timezone.now(), active_map_version=version
        )
        self.game.refresh_from_db()

        self.round = GameRound.objects.create(
            game=self.game, round_number=1, status=GameRound.Status.ACTIVE
        )

        for player in (self.player, self.other):
            with muted():
                move = PlayerMove.objects.create(
                    session_round=self.round,
                    player=player,
                    action="car",
                    payload={"agents": [{"id": 1, "action": "car"}]},
                )
            route = AgentRoute.objects.create(
                player_move=move,
                agent_id=1,
                transport_mode="car",
                total_distance_m=2000,
                estimated_time_min=3,
            )
            RouteSegment.objects.create(
                agent_route=route, order=1, edge=edge, mode="car"
            )

    def complete_round(self):
        listener = GroupListener(self.game.game_id)
        with muted(), self.captureOnCommitCallbacks(execute=True):
            round_completed.send(
                sender=GameSession, game_session=self.game, game_round=self.round
            )
        return listener


@override_settings(**TEST_BACKENDS)
class CostUnitTests(SimulatedRoundMixin, TestCase):
    """Two numbers meant to be read against each other carry one unit."""

    def test_the_player_rows_add_up_to_the_round_total(self):
        listener = self.complete_round()

        data = listener.data("round.completed")
        rows = sum(stat["cost_eur"] for stat in data["player_stats"])

        self.assertAlmostEqual(rows, data["round_cost_eur"], places=2)

    def test_an_agents_own_line_adds_up_to_its_players_row(self):
        listener = self.complete_round()

        for stat in listener.data("round.completed")["player_stats"]:
            agents = sum(agent["cost_eur"] for agent in stat["agents"])
            self.assertAlmostEqual(agents, stat["cost_eur"], places=2)

    def test_the_co2_column_was_already_consistent(self):
        """The control: CO2 is scaled when it is written, so it always matched.
        If this one ever goes red the scaling moved, not the units."""
        listener = self.complete_round()

        data = listener.data("round.completed")
        rows = sum(stat["emissions_g"] for stat in data["player_stats"])

        self.assertAlmostEqual(rows, data["round_emissions_g"], places=1)

    def test_the_summary_reports_the_cohort_figure(self):
        self.complete_round()
        self.client.force_login(self.host)

        with muted():
            response = self.client.get(f"/api/game/{self.game.game_id}/summary/")

        players = response.json()["players"]
        self.assertTrue(players)
        for player in players:
            self.assertGreater(
                player["total_cost_eur"],
                100.0,
                msg="a 2 km car trip costs about 0,64 € per person and about "
                "640 € for the thousand people the agent stands for; the "
                "summary shows the cohort, like the CO2 beside it",
            )


@override_settings(**TEST_BACKENDS)
class CostUnitWithOnePersonPerAgentTests(SimulatedRoundMixin, TestCase):
    """people_per_agent = 1 makes the scaling a no-op.

    Without this the test above would pass for a version that simply multiplied
    everything by a constant it made up.
    """

    people_per_agent = 1

    def test_rows_and_total_agree_when_there_is_nothing_to_scale(self):
        listener = self.complete_round()

        data = listener.data("round.completed")
        rows = sum(stat["cost_eur"] for stat in data["player_stats"])

        self.assertAlmostEqual(rows, data["round_cost_eur"], places=2)
