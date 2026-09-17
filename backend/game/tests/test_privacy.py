"""Anonymisation at game end. Roadmap.md 1.3.

A new topic file. Anonymisation is not a model invariant (test_models) and it does
not happen during a round (test_rounds) — it is a lifecycle rule of its own.

The rule, decided 2026-08-13: at game end `Player.name` becomes "Spieler N" and
the QR image is dropped. **Everything else stays.** Moves, routes and results keep
their foreign keys and stay linkable, because the research data is the point and
deleting the game would take it with it. Most of what is asserted below is
therefore about what must *survive*.
"""

import os
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from game.models import (
    AgentRoute,
    GameRound,
    GameSession,
    Player,
    PlayerMove,
)

from ._helpers import (
    TEST_BACKENDS,
    TempMediaRootMixin,
    create_game_session,
    create_host,
    muted,
)


class PlayedGameMixin(TempMediaRootMixin):
    """A finished game with two players who each moved and routed once."""

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Beendet")
            self.first = Player.objects.create(game=self.game, name="Mia")
            self.second = Player.objects.create(game=self.game, name="Jan")

            self.round = GameRound.objects.create(
                game=self.game,
                round_number=1,
                status=GameRound.Status.COMPLETED,
            )
            for player in (self.first, self.second):
                move = PlayerMove.objects.create(
                    session_round=self.round,
                    player=player,
                    action="route_submission",
                    payload={},
                )
                AgentRoute.objects.create(
                    player_move=move,
                    agent_id=1,
                    transport_mode="car",
                    total_distance_m=1200.0,
                    estimated_time_min=15.0,
                )

    def end_the_game(self, hours_ago=0):
        ended = timezone.now() - timezone.timedelta(hours=hours_ago)
        GameSession.objects.filter(pk=self.game.pk).update(
            ended_at=ended, is_active=False
        )
        self.game.refresh_from_db()


@override_settings(**TEST_BACKENDS)
class AnonymiseGameTests(PlayedGameMixin, TestCase):
    """What anonymise_game strips, and — mostly — what it must not touch."""

    def anonymise(self):
        from game.anon import anonymise_game

        with muted():
            return anonymise_game(self.game)

    def test_names_become_spieler_n_in_join_order(self):
        self.end_the_game()

        self.anonymise()

        names = list(
            Player.objects.filter(game=self.game)
            .order_by("joined_at", "pk")
            .values_list("name", flat=True)
        )
        self.assertEqual(names, ["Spieler 1", "Spieler 2"])

    def test_the_original_names_are_gone(self):
        self.end_the_game()

        self.anonymise()

        remaining = set(
            Player.objects.filter(game=self.game).values_list("name", flat=True)
        )
        self.assertNotIn("Mia", remaining)
        self.assertNotIn("Jan", remaining)

    def test_moves_routes_and_links_all_survive(self):
        """The whole reason this is anonymisation and not deletion."""
        self.end_the_game()
        move_count = PlayerMove.objects.filter(session_round=self.round).count()
        route_count = AgentRoute.objects.count()

        self.anonymise()

        self.assertEqual(
            PlayerMove.objects.filter(session_round=self.round).count(), move_count
        )
        self.assertEqual(AgentRoute.objects.count(), route_count)
        self.assertTrue(
            PlayerMove.objects.filter(player=self.first).exists(),
            msg="moves must stay attributable to their (now anonymous) player",
        )

    def test_the_qr_image_is_dropped(self):
        self.end_the_game()
        qr_path = self.game.game_qr_code.path
        self.assertTrue(os.path.exists(qr_path))

        self.anonymise()

        self.game.refresh_from_db()
        self.assertFalse(os.path.exists(qr_path))
        self.assertFalse(self.game.game_qr_code)

    def test_anonymised_at_is_stamped(self):
        self.end_the_game()

        self.anonymise()

        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.anonymised_at)

    def test_running_it_twice_changes_nothing(self):
        self.end_the_game()

        self.anonymise()
        first_pass = list(
            Player.objects.filter(game=self.game)
            .order_by("pk")
            .values_list("name", flat=True)
        )
        self.anonymise()
        second_pass = list(
            Player.objects.filter(game=self.game)
            .order_by("pk")
            .values_list("name", flat=True)
        )

        self.assertEqual(first_pass, second_pass)

    def test_it_returns_the_number_renamed(self):
        self.end_the_game()

        self.assertEqual(self.anonymise(), 2)
        self.assertEqual(self.anonymise(), 0)

    def test_other_games_are_untouched(self):
        self.end_the_game()
        with muted():
            other = create_game_session(self.host, game_name="Laeuft noch")
            bystander = Player.objects.create(game=other, name="Unbeteiligt")

        self.anonymise()

        bystander.refresh_from_db()
        self.assertEqual(bystander.name, "Unbeteiligt")


@override_settings(**TEST_BACKENDS)
class HostRowAnonymisationTests(TempMediaRootMixin, TestCase):
    """The host's own Player row, and players who play at the host machine.

    GameSessionCreateView names the host row after the account —
    "Erika Muster (Host)". That full name has to go as well. The row is not a
    student, though, so it becomes "Host" and takes no "Spieler N" number.

    Roadmap.md 1.6 lets the host add players who play on the host machine
    (controlled_by_host=True, no account). Those are students and are numbered
    like everyone else, which is why the rule keys on the host account.
    """

    def setUp(self):
        self.host = create_host(first_name="Erika", last_name="Muster")
        with muted():
            self.game = create_game_session(self.host, game_name="Mit Host")
            self.host_row = Player.objects.create(
                game=self.game,
                user=self.host,
                name="Erika Muster (Host)",
                controlled_by_host=True,
            )
            self.player = Player.objects.create(game=self.game, name="Mia")
            self.at_the_host_machine = Player.objects.create(
                game=self.game, name="Ohne Handy", controlled_by_host=True
            )
        GameSession.objects.filter(pk=self.game.pk).update(
            ended_at=timezone.now(), is_active=False
        )
        self.game.refresh_from_db()

    def anonymise(self):
        from game.anon import anonymise_game

        with muted():
            return anonymise_game(self.game)

    def test_the_host_row_becomes_host(self):
        self.anonymise()

        self.host_row.refresh_from_db()
        self.assertEqual(self.host_row.name, "Host")

    def test_the_host_row_takes_no_number(self):
        self.anonymise()

        self.player.refresh_from_db()
        self.assertEqual(self.player.name, "Spieler 1")

    def test_a_host_controlled_player_is_numbered_like_everyone_else(self):
        self.anonymise()

        self.at_the_host_machine.refresh_from_db()
        self.assertEqual(self.at_the_host_machine.name, "Spieler 2")

    def test_the_host_row_counts_as_renamed_once(self):
        self.assertEqual(self.anonymise(), 3)
        self.assertEqual(self.anonymise(), 0)


@override_settings(**TEST_BACKENDS)
class RemovedSeatAnonymisationTests(PlayedGameMixin, TestCase):
    """A seat removed after the start keeps its row (Roadmap.md 1.6), and with
    it the name. At game end it is renamed like every other row."""

    def test_a_seat_removed_after_the_start_is_anonymised_too(self):
        from game.anon import anonymise_game

        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=True, started_at=timezone.now()
        )
        self.client.force_login(self.host)
        with muted(), self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(
                f"/api/game/{self.game.game_id}/player/{self.second.player_id}/"
            )
        self.assertEqual(response.status_code, 204)
        self.end_the_game()

        with muted():
            anonymise_game(self.game)

        self.second.refresh_from_db()
        self.assertIsNotNone(self.second.left_at)
        self.assertEqual(self.second.name, "Spieler 2")
        self.assertTrue(PlayerMove.objects.filter(player=self.second).exists())


@override_settings(**TEST_BACKENDS)
class GamesDueTests(PlayedGameMixin, TestCase):
    """The grace period exists so the post-game summary still reads properly
    while the class is standing in front of it."""

    def due(self, grace_hours=24):
        from game.anon import games_due_for_anonymisation

        return list(games_due_for_anonymisation(grace_hours))

    def test_a_game_still_inside_the_grace_period_is_not_due(self):
        self.end_the_game(hours_ago=1)
        self.assertNotIn(self.game, self.due())

    def test_a_game_past_the_grace_period_is_due(self):
        self.end_the_game(hours_ago=48)
        self.assertIn(self.game, self.due())

    def test_a_running_game_is_never_due(self):
        self.assertNotIn(self.game, self.due())

    def test_an_already_anonymised_game_is_not_due_again(self):
        self.end_the_game(hours_ago=48)
        GameSession.objects.filter(pk=self.game.pk).update(anonymised_at=timezone.now())

        self.assertNotIn(self.game, self.due())


@override_settings(**TEST_BACKENDS)
class AnonymiseTaskTests(PlayedGameMixin, TestCase):
    """The beat task. Hangs off 1.1 — the beat container is commented out until then."""

    @override_settings(ANONYMISE_GRACE_HOURS=24)
    def test_the_task_picks_up_exactly_the_due_games(self):
        from game.tasks import anonymise_finished_games

        self.end_the_game(hours_ago=48)

        with muted():
            renamed = anonymise_finished_games()

        self.assertEqual(renamed, 2)
        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.anonymised_at)

    @override_settings(ANONYMISE_GRACE_HOURS=24)
    def test_the_task_leaves_games_inside_the_grace_period_alone(self):
        from game.tasks import anonymise_finished_games

        self.end_the_game(hours_ago=1)

        with muted():
            self.assertEqual(anonymise_finished_games(), 0)

        self.first.refresh_from_db()
        self.assertEqual(self.first.name, "Mia")

    @override_settings(ANONYMISE_GRACE_HOURS=0)
    def test_one_bad_game_does_not_stop_the_sweep(self):
        from unittest.mock import patch

        from game.tasks import anonymise_finished_games

        self.end_the_game(hours_ago=1)
        with muted():
            other = create_game_session(self.host, game_name="Zweites")
            Player.objects.create(game=other, name="Noch wer")
        GameSession.objects.filter(pk=other.pk).update(
            ended_at=timezone.now() - timezone.timedelta(hours=1), is_active=False
        )

        real_anonymise = __import__(
            "game.anon", fromlist=["anonymise_game"]
        ).anonymise_game
        calls = {"n": 0}

        def flaky(game):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return real_anonymise(game)

        with patch("game.anon.anonymise_game", side_effect=flaky), muted():
            anonymise_finished_games()

        self.assertEqual(
            calls["n"], 2, msg="the sweep must continue past a failing game"
        )


@override_settings(**TEST_BACKENDS)
class QrFileDeletionTests(TempMediaRootMixin, TestCase):
    """Deleting a GameSession must take its PNG with it.

    This is the assertion behind the long-standing failure in
    test_models.test_delete_game_removes_record_and_qr_code: Django deletes the
    row, not the file it points at.
    """

    def test_deleting_a_game_removes_the_qr_file(self):
        host = create_host()
        with muted():
            game = create_game_session(host, game_name="Zum loeschen")
        qr_path = game.game_qr_code.path
        self.assertTrue(os.path.exists(qr_path))

        with muted():
            game.delete()

        self.assertFalse(
            os.path.exists(qr_path),
            msg="the QR image should not outlive the game it belongs to",
        )

    def test_deleting_a_game_without_a_qr_file_is_survivable(self):
        host = create_host()
        with muted():
            game = create_game_session(host, game_name="Ohne QR")
            game.game_qr_code.delete(save=True)
            game.delete()


@override_settings(**TEST_BACKENDS)
class ManagementCommandTests(PlayedGameMixin, TestCase):
    """Backfill and a by-hand escape hatch.

    Beat only ever catches games that end from now on, and whoever inherits this
    needs a way to answer "please remove that name" without a shell.

    stdout goes to a StringIO: verbosity=0 does not silence self.stdout.write,
    and the run has to stay a wall of dots.
    """

    def test_dry_run_changes_nothing(self):
        self.end_the_game(hours_ago=48)

        with muted():
            call_command("anonymise_games", "--dry-run", verbosity=0, stdout=StringIO())

        self.first.refresh_from_db()
        self.assertEqual(self.first.name, "Mia")

    @override_settings(ANONYMISE_GRACE_HOURS=24)
    def test_the_default_run_respects_the_grace_period(self):
        self.end_the_game(hours_ago=1)

        with muted():
            call_command("anonymise_games", verbosity=0, stdout=StringIO())

        self.first.refresh_from_db()
        self.assertEqual(self.first.name, "Mia")

    @override_settings(ANONYMISE_GRACE_HOURS=24)
    def test_all_ignores_the_grace_period(self):
        self.end_the_game(hours_ago=1)

        with muted():
            call_command("anonymise_games", "--all", verbosity=0, stdout=StringIO())

        self.first.refresh_from_db()
        self.assertEqual(self.first.name, "Spieler 1")

    def test_a_running_game_is_never_touched_even_with_all(self):
        with muted():
            call_command("anonymise_games", "--all", verbosity=0, stdout=StringIO())

        self.first.refresh_from_db()
        self.assertEqual(self.first.name, "Mia")


class ExpiredSessionTests(TestCase):
    """Django never deletes expired django_session rows by itself — the DB
    backend needs clearsessions, and nothing ran it. Before 1.2 every join wrote
    the player id into the session, and for a logged-in user that row links the
    account to the player."""

    def test_the_task_deletes_expired_sessions_only(self):
        from django.contrib.sessions.models import Session

        from game.tasks import clear_expired_sessions

        now = timezone.now()
        Session.objects.create(
            session_key="expired".ljust(32, "0"),
            session_data="",
            expire_date=now - timezone.timedelta(days=1),
        )
        Session.objects.create(
            session_key="current".ljust(32, "0"),
            session_data="",
            expire_date=now + timezone.timedelta(days=1),
        )

        clear_expired_sessions()

        self.assertEqual(
            list(Session.objects.values_list("session_key", flat=True)),
            ["current".ljust(32, "0")],
        )


class RetentionSettingsTests(TestCase):
    def test_the_grace_period_is_configurable(self):
        from django.conf import settings as django_settings

        self.assertTrue(hasattr(django_settings, "ANONYMISE_GRACE_HOURS"))
        self.assertGreaterEqual(django_settings.ANONYMISE_GRACE_HOURS, 0)

    def test_the_beat_schedule_carries_the_anonymisation_job(self):
        from django.conf import settings as django_settings

        schedule = getattr(django_settings, "CELERY_BEAT_SCHEDULE", {})
        tasks = {entry["task"] for entry in schedule.values()}
        self.assertIn("game.tasks.anonymise_finished_games", tasks)

    def test_the_beat_schedule_clears_expired_sessions(self):
        from django.conf import settings as django_settings

        schedule = getattr(django_settings, "CELERY_BEAT_SCHEDULE", {})
        tasks = {entry["task"] for entry in schedule.values()}
        self.assertIn("game.tasks.clear_expired_sessions", tasks)

    def test_cleanup_old_simulations_stays_unscheduled(self):
        """It deletes EdgeTrafficSnapshot rows — research data. Anonymising
        rather than deleting is the whole point; do not sweep it away."""
        from django.conf import settings as django_settings

        schedule = getattr(django_settings, "CELERY_BEAT_SCHEDULE", {})
        tasks = {entry["task"] for entry in schedule.values()}
        self.assertNotIn("game.tasks.cleanup_old_simulations", tasks)
