"""Between-round phases: stats → discussion → voting → stalemate → next round.

Roadmap.md 1.1, last bullet: the consumers.py split, part 1. game/phases.py owns
the rules and is plain sync code, so nothing here needs a socket. That is the
point of the split. test_socket.py checks that the consumer really hands over.

game.phases and StatsAck are imported inside the tests rather than at module
level. Neither exists before the guide is typed, and a top-level import would
turn this file into one import error instead of a list of red tests.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from game.models import GameRound, GameSession, MapVersionVote, Player, PlayerMove
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

Phase = GameRound.BetweenRoundPhase


def phases():
    from game import phases as module

    return module


def stats_acks():
    from game.models import StatsAck

    return StatsAck.objects


class BetweenRoundsMixin(TempMediaRootMixin):
    """A running game whose round 1 is over and waits in a between-round phase.

    Two players, plus the host's own row the way GameSessionCreateView makes it.
    The host row is never waited for; every test here would hang on it if it
    were.

    is_active goes in with .update(): GameSession.save() resets it whenever
    game_map is None.
    """

    phase = Phase.STATS

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Zwischen den Runden")
            self.host_row = Player.objects.create(
                game=self.game, name="Host", user=self.host, controlled_by_host=True
            )
            self.anna = Player.objects.create(game=self.game, name="Anna")
            self.ben = Player.objects.create(game=self.game, name="Ben")

        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=True, started_at=timezone.now()
        )
        self.game.refresh_from_db()

        self.round = GameRound.objects.create(
            game=self.game,
            round_number=1,
            status=GameRound.Status.COMPLETED,
            total_emissions_g=1234.5,
            between_round_phase=self.phase,
        )

    def add_ballot(self, options=2):
        """A map whose active version has `options` versions to vote on.

        Set after the players exist, so set_up_player has no map to assign
        home nodes from.
        """
        game_map = GameMap.objects.create(name="Testkarte")
        base = MapVersion.objects.create(
            game_map=game_map, name="Basis", base_version=True
        )
        versions = [
            MapVersion.objects.create(
                game_map=game_map, name=f"Option {n}", source_version=base
            )
            for n in range(1, options + 1)
        ]
        base.compatible_versions.add(*versions)
        GameSession.objects.filter(pk=self.game.pk).update(
            game_map=game_map, map_updates=True, active_map_version=base
        )
        self.game.refresh_from_db()
        return base, versions

    def set_round(self, **fields):
        GameRound.objects.filter(pk=self.round.pk).update(**fields)
        self.round.refresh_from_db()

    def ack(self, player):
        with muted():
            return phases().ack_stats(self.game.game_id, player.player_id)

    def vote(self, player, version):
        with muted():
            return phases().submit_vote(
                self.game.game_id,
                player.player_id,
                version.pk if version else None,
            )

    def answer(self, player, want_revote):
        with muted():
            return phases().submit_stalemate_vote(
                self.game.game_id, player.player_id, want_revote
            )

    def phase_now(self):
        self.round.refresh_from_db()
        return self.round.between_round_phase

    def round_count(self):
        return GameRound.objects.filter(game=self.game).count()


@override_settings(**TEST_BACKENDS)
class StatsAckTests(BetweenRoundsMixin, TestCase):
    """The stats phase ends once every playing seat has acked.

    Acks used to sit in a Redis set keyed by player_id, with a one-hour TTL:
    gone after a long break, and a player with a new id (1.7) would count twice.
    They are rows now, keyed by the Player row.
    """

    def test_an_ack_is_stored_once_per_player(self):
        self.assertTrue(self.ack(self.anna))
        self.ack(self.anna)

        self.assertEqual(
            stats_acks().filter(game_round=self.round, player=self.anna).count(), 1
        )

    def test_the_phase_waits_for_every_playing_seat(self):
        self.ack(self.anna)

        self.assertEqual(self.phase_now(), Phase.STATS)
        self.assertEqual(self.round_count(), 1)

    def test_the_last_ack_starts_the_next_round_when_there_is_no_ballot(self):
        listener = GroupListener(self.game.game_id)

        self.ack(self.anna)
        self.ack(self.ben)

        self.assertEqual(self.phase_now(), Phase.NONE)
        new_round = GameRound.objects.get(game=self.game, round_number=2)
        self.assertEqual(new_round.status, GameRound.Status.ACTIVE)
        self.assertIsNotNone(new_round.started_at)

        self.assertEqual(listener.names(), ["stats.all_acked", "round.started"])
        self.assertEqual(listener.data("stats.all_acked"), {"next_phase": "next_round"})
        self.assertEqual(
            listener.data("round.started"),
            {
                "round_number": 2,
                "max_rounds": 10,
                "total_game_emissions_g": 1234.5,
                "max_co2_level_g": 10_000_000,
            },
        )

    def test_the_last_ack_opens_the_discussion_when_there_is_a_ballot(self):
        _, versions = self.add_ballot()
        listener = GroupListener(self.game.game_id)

        self.ack(self.anna)
        self.ack(self.ben)

        self.assertEqual(self.phase_now(), Phase.DISCUSSION)
        self.assertEqual(self.round_count(), 1)
        self.assertEqual(listener.names(), ["stats.all_acked"])
        data = listener.data("stats.all_acked")
        self.assertEqual(data["next_phase"], "discussion")
        self.assertCountEqual(
            [option["id"] for option in data["map_versions"]],
            [version.pk for version in versions],
        )

    def test_the_host_row_cannot_ack(self):
        self.assertFalse(self.ack(self.host_row))

        self.assertFalse(stats_acks().filter(player=self.host_row).exists())

    def test_a_player_who_left_is_not_waited_for(self):
        Player.objects.filter(pk=self.ben.pk).update(left_at=timezone.now())

        self.ack(self.anna)

        self.assertEqual(self.round_count(), 2)

    def test_a_player_who_left_cannot_ack(self):
        Player.objects.filter(pk=self.ben.pk).update(left_at=timezone.now())

        self.assertFalse(self.ack(self.ben))

    def test_an_ack_outside_the_stats_phase_is_refused(self):
        self.set_round(between_round_phase=Phase.DISCUSSION)

        self.assertFalse(self.ack(self.anna))
        self.assertFalse(stats_acks().exists())

    def test_an_ack_survives_a_new_player_id(self):
        """1.7 gives a player a new player_id. The ack belongs to the row."""
        self.ack(self.anna)
        Player.objects.filter(pk=self.anna.pk).update(player_id="P-NEU1")

        self.ack(self.ben)

        self.assertEqual(self.round_count(), 2)

    def test_the_phase_ends_once_however_often_it_is_checked(self):
        self.ack(self.anna)
        self.ack(self.ben)

        self.assertFalse(self.ack(self.ben), msg="the stats phase is over")
        with muted():
            phases().recheck(self.game.game_id)

        self.assertEqual(self.round_count(), 2)

    def test_two_sockets_finishing_together_start_one_round(self):
        """Both callers read the phase as STATS before either one writes.

        Only the claim on between_round_phase stops the second one. Without it,
        this game gets a round 3.
        """
        stats_acks().create(game_round=self.round, player=self.anna)
        stats_acks().create(game_round=self.round, player=self.ben)

        with muted():
            game, stale_round = phases()._load(self.game.game_id)
            phases()._advance_from_stats(game, stale_round)
            phases()._advance_from_stats(game, stale_round)

        self.assertEqual(self.round_count(), 2)


@override_settings(**TEST_BACKENDS)
class VotingTests(BetweenRoundsMixin, TestCase):
    """Discussion → voting → a result (or a stalemate)."""

    phase = Phase.DISCUSSION

    def setUp(self):
        super().setUp()
        self.base, (self.option_1, self.option_2) = self.add_ballot()

    def open_vote(self):
        with muted():
            return phases().open_vote(self.game.game_id)

    def test_the_host_opens_the_vote_from_the_discussion(self):
        listener = GroupListener(self.game.game_id)

        self.assertTrue(self.open_vote())

        self.assertEqual(self.phase_now(), Phase.VOTING)
        self.assertEqual(listener.names(), ["vote.opened"])
        self.assertCountEqual(
            [option["id"] for option in listener.data("vote.opened")["versions"]],
            [self.option_1.pk, self.option_2.pk],
        )

    def test_the_vote_cannot_be_opened_from_another_phase(self):
        """It used to open from any phase, the stats phase included."""
        self.set_round(between_round_phase=Phase.STATS)

        self.assertFalse(self.open_vote())
        self.assertEqual(self.phase_now(), Phase.STATS)

    def test_a_vote_before_the_vote_opens_is_refused(self):
        self.assertFalse(self.vote(self.anna, self.option_1))

        self.assertFalse(MapVersionVote.objects.exists())

    def test_a_player_votes_once(self):
        self.open_vote()

        self.assertTrue(self.vote(self.anna, self.option_1))
        self.assertFalse(self.vote(self.anna, self.option_2))
        self.assertEqual(
            MapVersionVote.objects.get(player=self.anna).map_version, self.option_1
        )

    def test_leave_as_is_is_a_vote(self):
        self.open_vote()

        self.assertTrue(self.vote(self.anna, None))

    def test_a_version_that_is_not_on_the_ballot_is_refused(self):
        """Any MapVersion pk used to be accepted, from any map."""
        stranger = MapVersion.objects.create(
            game_map=self.base.game_map, name="Nicht zur Wahl"
        )
        self.open_vote()

        self.assertFalse(self.vote(self.anna, stranger))
        self.assertFalse(MapVersionVote.objects.exists())

    def test_the_host_row_cannot_vote(self):
        self.open_vote()

        self.assertFalse(self.vote(self.host_row, self.option_1))

    def test_progress_counts_playing_seats_only(self):
        self.open_vote()
        listener = GroupListener(self.game.game_id)

        self.vote(self.anna, self.option_1)

        self.assertEqual(
            listener.data("vote.recorded"),
            {"player_id": self.anna.player_id, "votes_cast": 1, "votes_needed": 2},
        )

    def test_a_clear_winner_changes_the_map_and_starts_the_next_round(self):
        self.open_vote()
        listener = GroupListener(self.game.game_id)

        self.vote(self.anna, self.option_1)
        self.vote(self.ben, self.option_1)

        self.game.refresh_from_db()
        self.assertEqual(self.game.active_map_version, self.option_1)
        self.assertEqual(self.phase_now(), Phase.NONE)
        self.assertEqual(self.round_count(), 2)

        self.assertEqual(
            listener.names(),
            ["vote.recorded", "vote.recorded", "vote.result", "round.started"],
        )
        result = listener.data("vote.result")
        self.assertFalse(result["stalemate"])
        self.assertEqual(result["winning_version_id"], self.option_1.pk)
        self.assertEqual(result["winning_version_name"], "Option 1")
        self.assertEqual(
            result["vote_counts"],
            [{"version_id": self.option_1.pk, "version_name": "Option 1", "count": 2}],
        )

    def test_leave_as_is_winning_keeps_the_map(self):
        self.open_vote()

        self.vote(self.anna, None)
        self.vote(self.ben, None)

        self.game.refresh_from_db()
        self.assertEqual(self.game.active_map_version, self.base)
        self.assertEqual(self.round_count(), 2)

    def test_a_tie_asks_whether_to_vote_again(self):
        self.open_vote()
        listener = GroupListener(self.game.game_id)

        self.vote(self.anna, self.option_1)
        self.vote(self.ben, None)

        self.assertEqual(self.phase_now(), Phase.STALEMATE)
        self.assertEqual(self.round.stalemate_count, 1)
        self.assertEqual(self.round_count(), 1)
        self.assertEqual(listener.names()[-1], "vote.stalemate")
        stalemate = listener.data("vote.stalemate")
        self.assertEqual(stalemate["stalemate_count"], 1)
        self.assertCountEqual(
            stalemate["vote_counts"],
            [
                {
                    "version_id": self.option_1.pk,
                    "version_name": "Option 1",
                    "count": 1,
                },
                {"version_id": None, "version_name": "Leave as it is", "count": 1},
            ],
        )

    def test_a_second_tie_leaves_the_map_as_it_is(self):
        self.set_round(stalemate_count=1)
        self.open_vote()

        self.vote(self.anna, self.option_1)
        self.vote(self.ben, self.option_2)

        self.game.refresh_from_db()
        self.assertEqual(self.game.active_map_version, self.base)
        self.assertEqual(self.phase_now(), Phase.NONE)
        self.assertEqual(self.round.stalemate_count, 2)
        self.assertEqual(self.round_count(), 2)

    def test_a_vote_from_a_player_who_left_does_not_count(self):
        """Both sides of the comparison use the same seats. Counting Ben's vote
        while not waiting for him would turn this into a tie."""
        self.open_vote()
        self.vote(self.ben, self.option_2)
        Player.objects.filter(pk=self.ben.pk).update(left_at=timezone.now())

        self.vote(self.anna, self.option_1)

        self.game.refresh_from_db()
        self.assertEqual(self.game.active_map_version, self.option_1)


@override_settings(**TEST_BACKENDS)
class StalemateTests(BetweenRoundsMixin, TestCase):
    """After the first tie: vote again, or leave the map as it is."""

    phase = Phase.STALEMATE

    def setUp(self):
        super().setUp()
        self.base, (self.option_1, self.option_2, _) = self.add_ballot(options=3)
        # The tied vote that got us here, on a ballot of two out of three.
        self.set_round(
            stalemate_count=1,
            vote_option_ids=[self.option_1.pk, self.option_2.pk],
        )
        MapVersionVote.objects.create(
            game_round=self.round, player=self.anna, map_version=self.option_1
        )
        MapVersionVote.objects.create(
            game_round=self.round, player=self.ben, map_version=None
        )

    def force_leave(self):
        with muted():
            return phases().force_leave_as_is(self.game.game_id)

    def test_a_player_answers_once(self):
        self.assertTrue(self.answer(self.anna, True))
        self.assertFalse(self.answer(self.anna, False))

    def test_an_answer_outside_the_stalemate_is_refused(self):
        self.set_round(between_round_phase=Phase.VOTING)

        self.assertFalse(self.answer(self.anna, True))

    def test_progress_counts_playing_seats_only(self):
        listener = GroupListener(self.game.game_id)

        self.answer(self.anna, True)

        self.assertEqual(listener.data("stalemate.progress"), {"cast": 1, "needed": 2})

    def test_a_majority_for_voting_again_reopens_the_same_ballot(self):
        listener = GroupListener(self.game.game_id)

        self.answer(self.anna, True)
        self.answer(self.ben, True)

        self.assertEqual(self.phase_now(), Phase.VOTING)
        self.assertFalse(MapVersionVote.objects.filter(game_round=self.round).exists())
        self.assertEqual(self.round_count(), 1)
        self.assertEqual(
            listener.names(),
            ["stalemate.progress", "stalemate.progress", "vote.opened"],
        )
        self.assertCountEqual(
            [option["id"] for option in listener.data("vote.opened")["versions"]],
            [self.option_1.pk, self.option_2.pk],
        )

    def test_no_majority_leaves_the_map_as_it_is(self):
        """A split answer counts as "leave it", as before."""
        listener = GroupListener(self.game.game_id)

        self.answer(self.anna, True)
        self.answer(self.ben, False)

        self.assertEqual(self.phase_now(), Phase.NONE)
        self.assertEqual(self.round_count(), 2)
        self.game.refresh_from_db()
        self.assertEqual(self.game.active_map_version, self.base)

        self.assertEqual(listener.names()[-2:], ["vote.result", "round.started"])
        result = listener.data("vote.result")
        self.assertTrue(result["forced"])
        self.assertIsNone(result["winning_version_id"])

    def test_the_host_can_cut_it_short(self):
        self.assertTrue(self.force_leave())

        self.assertEqual(self.phase_now(), Phase.NONE)
        self.assertEqual(self.round_count(), 2)

    def test_the_host_cannot_force_a_result_outside_the_stalemate(self):
        """It used to start a new round from any phase, in the middle of a vote too."""
        self.set_round(between_round_phase=Phase.VOTING)

        self.assertFalse(self.force_leave())

        self.assertEqual(self.phase_now(), Phase.VOTING)
        self.assertEqual(self.round_count(), 1)


@override_settings(**TEST_BACKENDS)
class BallotTests(BetweenRoundsMixin, TestCase):
    """At most two map versions per vote, drawn once per round and stored on it.

    The draw used to live in a two-hour cache key that the consumer deleted at
    the next round. A long break or a Redis restart between round.completed and
    the vote drew different options than the players had seen.
    """

    def setUp(self):
        super().setUp()
        self.base, self.versions = self.add_ballot(options=3)

    def ballot_ids(self):
        with muted():
            return [option["id"] for option in phases().vote_options(self.round)]

    def test_at_most_two_options(self):
        self.assertEqual(len(self.ballot_ids()), 2)

    def test_the_draw_is_stored_on_the_round(self):
        ids = self.ballot_ids()

        self.round.refresh_from_db()
        self.assertCountEqual(self.round.vote_option_ids, ids)

    def test_the_draw_survives_a_cache_flush(self):
        """The second pick is what a fresh draw would give. It must never be used."""
        v1, v2, v3 = self.versions
        with patch("random.sample", side_effect=[[v1.pk, v2.pk], [v2.pk, v3.pk]]):
            first = self.ballot_ids()
            cache.clear()
            second = self.ballot_ids()

        self.assertCountEqual(first, [v1.pk, v2.pk])
        self.assertEqual(second, first)

    def test_an_option_says_what_it_changes(self):
        option = phases().vote_options(self.round)[0]

        self.assertEqual(
            set(option), {"id", "name", "poll_text", "is_rollback", "change_img_url"}
        )
        self.assertFalse(option["is_rollback"])

    def test_no_ballot_without_map_updates(self):
        GameSession.objects.filter(pk=self.game.pk).update(map_updates=False)
        self.game.refresh_from_db()

        self.assertEqual(self.ballot_ids(), [])

    def test_round_completed_announces_the_stored_ballot(self):
        """handle_round_completed runs in the Celery worker. It must show the
        players exactly the options they will later vote on."""
        next_round = GameRound.objects.create(
            game=self.game, round_number=2, status=GameRound.Status.ACTIVE
        )
        with muted():
            PlayerMove.objects.create(
                session_round=next_round,
                player=self.anna,
                action="car",
                payload={"agents": [{"id": 1, "action": "car"}]},
            )
        listener = GroupListener(self.game.game_id)

        with muted():
            round_completed.send(
                sender=GameRound, game_session=self.game, game_round=next_round
            )

        next_round.refresh_from_db()
        announced = [
            option["id"] for option in listener.data("round.completed")["map_versions"]
        ]
        self.assertEqual(len(announced), 2)
        self.assertCountEqual(announced, next_round.vote_option_ids)


@override_settings(**TEST_BACKENDS)
class LeavingFinishesAPhaseTests(BetweenRoundsMixin, TestCase):
    """Someone leaving can be what finishes a phase.

    The check used to hang off the socket's disconnect, which is the wrong
    event: a locked phone disconnects without leaving, and a player the host
    removes may never disconnect at all. The post_delete receiver on Player
    schedules it now, next to the round-completion check.

    It runs on commit. Without captureOnCommitCallbacks(execute=True) it never
    runs inside a TestCase, and the negative case would pass for nothing.
    """

    def leave(self, player):
        with muted(), self.captureOnCommitCallbacks(execute=True):
            player.delete()

    def test_leaving_can_finish_the_stats_phase(self):
        self.ack(self.anna)

        self.leave(self.ben)

        self.assertEqual(self.round_count(), 2)

    def test_leaving_can_finish_the_vote(self):
        _, (option_1, option_2) = self.add_ballot()
        self.set_round(
            between_round_phase=Phase.VOTING,
            vote_option_ids=[option_1.pk, option_2.pk],
        )
        self.vote(self.anna, option_1)

        self.leave(self.ben)

        self.game.refresh_from_db()
        self.assertEqual(self.game.active_map_version, option_1)
        self.assertEqual(self.round_count(), 2)

    def test_leaving_can_finish_the_stalemate(self):
        _, (option_1, option_2) = self.add_ballot()
        self.set_round(
            between_round_phase=Phase.STALEMATE,
            stalemate_count=1,
            vote_option_ids=[option_1.pk, option_2.pk],
        )
        self.answer(self.anna, True)

        self.leave(self.ben)

        self.assertEqual(self.phase_now(), Phase.VOTING)

    def test_leaving_while_others_are_outstanding_changes_nothing(self):
        with muted():
            cem = Player.objects.create(game=self.game, name="Cem")
        self.ack(self.anna)

        self.leave(cem)

        self.assertEqual(self.phase_now(), Phase.STATS)
        self.assertEqual(self.round_count(), 1)

    def test_a_recheck_for_an_unknown_game_is_survivable(self):
        with muted():
            phases().recheck("NOPE12")


@override_settings(**TEST_BACKENDS)
class HostSeatsBetweenRoundsTests(BetweenRoundsMixin, TestCase):
    """The host acks and votes for the seats played at the host machine.
    Roadmap.md 1.6.

    A host socket speaks for several seats. Acks cover all of them at once
    (they share one screen); votes name the seat. Only seats played at the
    host machine: a student's seat is the student's.
    """

    def setUp(self):
        super().setUp()
        with muted():
            self.cem = Player.objects.create(
                game=self.game, name="Cem", controlled_by_host=True
            )
            self.dana = Player.objects.create(
                game=self.game, name="Dana", controlled_by_host=True
            )

    def ack_for_host_seats(self):
        with muted():
            return phases().ack_host_seats(self.game.game_id)

    def vote_by_host(self, player, version):
        with muted():
            return phases().submit_vote(
                self.game.game_id,
                player.player_id,
                version.pk if version else None,
                by_host=True,
            )

    def answer_by_host(self, player, want_revote):
        with muted():
            return phases().submit_stalemate_vote(
                self.game.game_id, player.player_id, want_revote, by_host=True
            )

    def open_voting(self):
        _, (option_1, option_2) = self.add_ballot()
        self.set_round(
            between_round_phase=Phase.VOTING,
            vote_option_ids=[option_1.pk, option_2.pk],
        )
        return option_1, option_2

    def test_the_host_acks_for_every_seat_at_the_host_machine(self):
        self.assertTrue(self.ack_for_host_seats())

        acked = set(
            stats_acks().filter(game_round=self.round).values_list("player", flat=True)
        )
        self.assertEqual(acked, {self.cem.pk, self.dana.pk})

    def test_the_host_ack_can_be_the_last_one(self):
        self.ack(self.anna)
        self.ack(self.ben)

        self.ack_for_host_seats()

        self.assertEqual(self.round_count(), 2)

    def test_the_host_ack_is_refused_outside_the_stats_phase(self):
        self.set_round(between_round_phase=Phase.DISCUSSION)

        self.assertFalse(self.ack_for_host_seats())
        self.assertFalse(stats_acks().exists())

    def test_the_host_ack_is_refused_without_seats_at_the_host_machine(self):
        Player.objects.filter(pk__in=[self.cem.pk, self.dana.pk]).update(
            left_at=timezone.now()
        )

        self.assertFalse(self.ack_for_host_seats())

    def test_the_seats_still_count_one_by_one(self):
        """Cem and Dana are two seats, not one host."""
        self.ack(self.anna)
        self.ack_for_host_seats()

        self.assertEqual(self.phase_now(), Phase.STATS)

    def test_the_host_votes_for_a_seat_at_the_host_machine(self):
        option_1, _ = self.open_voting()

        self.assertTrue(self.vote_by_host(self.cem, option_1))

        self.assertEqual(
            MapVersionVote.objects.get(
                game_round=self.round, player=self.cem
            ).map_version,
            option_1,
        )

    def test_the_host_may_not_vote_for_a_student(self):
        option_1, _ = self.open_voting()

        self.assertFalse(self.vote_by_host(self.anna, option_1))
        self.assertFalse(MapVersionVote.objects.filter(player=self.anna).exists())

    def test_the_host_may_not_vote_as_the_host_row(self):
        option_1, _ = self.open_voting()

        self.assertFalse(self.vote_by_host(self.host_row, option_1))

    def test_each_seat_votes_once(self):
        option_1, option_2 = self.open_voting()
        self.vote_by_host(self.cem, option_1)

        self.assertFalse(self.vote_by_host(self.cem, option_2))
        self.assertTrue(self.vote_by_host(self.dana, option_2))

    def test_host_votes_can_decide_the_round(self):
        option_1, _ = self.open_voting()
        self.vote(self.anna, option_1)
        self.vote(self.ben, None)
        self.vote_by_host(self.cem, option_1)

        self.vote_by_host(self.dana, option_1)

        self.game.refresh_from_db()
        self.assertEqual(self.game.active_map_version, option_1)
        self.assertEqual(self.round_count(), 2)

    def test_the_host_answers_a_stalemate_for_a_seat(self):
        option_1, option_2 = self.open_voting()
        self.set_round(between_round_phase=Phase.STALEMATE, stalemate_count=1)

        self.assertTrue(self.answer_by_host(self.cem, True))
        self.assertFalse(self.answer_by_host(self.anna, True))
