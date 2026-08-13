from django.test import TestCase, override_settings

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
