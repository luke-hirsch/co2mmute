from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from co2mmute.utils import sign_value
from game.models import GameRound, GameSession, Player, PlayerMove
from game.signals import round_completed

from ._helpers import (
    TEST_BACKENDS,
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
    (left_at__isnull=True) and not host-controlled. The post_save receiver this
    replaces counted every Player row, so a game anyone had left could never
    complete.
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

    def test_a_host_controlled_row_is_not_waited_for(self):
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
        # Pre-1.2 format: the bare player_id. 1.2 binds it to the game.
        self.client.cookies[player_name] = sign_value(
            player.player_id, settings.COOKIE_PLAYER_SALT
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

        self.assertEqual(
            len(callbacks), 1, msg="the move view should register exactly one callback"
        )
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, GameRound.Status.ACTIVE)
        delay.assert_not_called()
