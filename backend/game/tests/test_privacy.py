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
from unittest.mock import patch

from django.contrib.auth import get_user_model
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
    GroupListener,
    TempMediaRootMixin,
    create_form_data,
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


# ---------------------------------------------------------------------------
# Roadmap.md 1.6 — idle games end by themselves
#
# A paused game can wait for a class that never comes back, and a lobby nobody
# starts waits forever. Both kept their names indefinitely. Each game now ends
# after its own idle_end_days, and the normal anonymisation takes it from
# there. game.idle is imported inside the tests; it doesn't exist before the
# pause guide.
# ---------------------------------------------------------------------------


def days_ago(days):
    return timezone.now() - timezone.timedelta(days=days)


class IdleGameMixin(TempMediaRootMixin):
    """A lobby with one player, everything in it dated `idle_days` back."""

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Vergessen")
            self.player = Player.objects.create(game=self.game, name="Mia")

    def age(self, game, days):
        GameSession.objects.filter(pk=game.pk).update(updated_at=days_ago(days))
        Player.objects.filter(game=game).update(joined_at=days_ago(days))
        game.refresh_from_db()

    def due(self):
        from game.idle import games_due_for_idle_end

        return games_due_for_idle_end()


@override_settings(**TEST_BACKENDS)
class IdleEndTests(IdleGameMixin, TestCase):
    def test_a_lobby_idle_past_its_limit_is_due(self):
        self.age(self.game, 31)

        self.assertIn(self.game, self.due())

    def test_a_lobby_inside_its_limit_is_not(self):
        self.age(self.game, 29)

        self.assertNotIn(self.game, self.due())

    def test_each_game_has_its_own_limit(self):
        with muted():
            short = create_game_session(self.host, game_name="Kurz", idle_end_days=1)
        self.age(self.game, 2)
        self.age(short, 2)

        due = self.due()

        self.assertIn(short, due)
        self.assertNotIn(self.game, due)

    def test_a_recent_move_keeps_a_game_alive(self):
        game_round = GameRound.objects.create(
            game=self.game, round_number=1, status=GameRound.Status.ACTIVE
        )
        with muted():
            move = PlayerMove.objects.create(
                session_round=game_round, player=self.player, action="car"
            )
        self.age(self.game, 40)
        GameRound.objects.filter(pk=game_round.pk).update(updated_at=days_ago(40))
        PlayerMove.objects.filter(pk=move.pk).update(moved_at=days_ago(2))

        self.assertNotIn(self.game, self.due())

    def test_a_recent_round_keeps_a_game_alive(self):
        game_round = GameRound.objects.create(
            game=self.game, round_number=1, status=GameRound.Status.COMPLETED
        )
        self.age(self.game, 40)
        GameRound.objects.filter(pk=game_round.pk).update(updated_at=days_ago(2))

        self.assertNotIn(self.game, self.due())

    def test_a_recent_join_keeps_a_lobby_alive(self):
        self.age(self.game, 40)
        with muted():
            Player.objects.create(game=self.game, name="Neu")

        self.assertNotIn(self.game, self.due())

    def test_a_paused_game_ends_too(self):
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=True, started_at=days_ago(40), paused_at=days_ago(40)
        )
        self.age(self.game, 40)

        self.assertIn(self.game, self.due())

    def test_an_ended_game_is_never_due(self):
        GameSession.objects.filter(pk=self.game.pk).update(ended_at=days_ago(40))
        self.age(self.game, 40)

        self.assertNotIn(self.game, self.due())

    def test_ending_an_idle_game_ends_it_like_the_stop_button(self):
        from game.idle import end_idle_game

        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=True, started_at=days_ago(40), paused_at=days_ago(40)
        )
        self.game.refresh_from_db()
        listener = GroupListener(self.game.game_id)

        with muted(), self.captureOnCommitCallbacks(execute=True):
            end_idle_game(self.game)

        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.ended_at)
        self.assertFalse(self.game.is_active)
        self.assertIsNone(self.game.paused_at)
        self.assertIn("game.ended", listener.names())


@override_settings(**TEST_BACKENDS)
class IdleEndTaskTests(IdleGameMixin, TestCase):
    def run_task(self):
        from game.tasks import end_idle_games

        with muted(), self.captureOnCommitCallbacks(execute=True):
            return end_idle_games()

    def test_the_task_ends_exactly_the_due_games(self):
        with muted():
            fresh = create_game_session(self.host, game_name="Frisch")
        self.age(self.game, 31)

        self.assertEqual(self.run_task(), 1)

        self.game.refresh_from_db()
        fresh.refresh_from_db()
        self.assertIsNotNone(self.game.ended_at)
        self.assertIsNone(fresh.ended_at)

    @override_settings(ANONYMISE_GRACE_HOURS=0)
    def test_an_idle_game_is_then_anonymised_as_usual(self):
        from game.tasks import anonymise_finished_games

        self.age(self.game, 31)
        self.run_task()
        GameSession.objects.filter(pk=self.game.pk).update(ended_at=days_ago(1))

        with muted():
            anonymise_finished_games()

        self.player.refresh_from_db()
        self.assertEqual(self.player.name, "Spieler 1")

    def test_one_bad_game_does_not_stop_the_sweep(self):
        from game import idle

        with muted():
            other = create_game_session(self.host, game_name="Zweites")
        self.age(self.game, 31)
        self.age(other, 31)

        real_end = idle.end_idle_game
        calls = {"n": 0}

        def flaky(game):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return real_end(game)

        with patch("game.idle.end_idle_game", side_effect=flaky):
            ended = self.run_task()

        self.assertEqual(calls["n"], 2)
        self.assertEqual(ended, 1)


@override_settings(**TEST_BACKENDS)
class IdleEndCommandTests(IdleGameMixin, TestCase):
    """stdout goes to a StringIO, as in ManagementCommandTests."""

    def test_dry_run_changes_nothing(self):
        self.age(self.game, 31)

        with muted():
            call_command("end_idle_games", "--dry-run", stdout=StringIO())

        self.game.refresh_from_db()
        self.assertIsNone(self.game.ended_at)

    def test_it_ends_the_due_games(self):
        self.age(self.game, 31)

        with muted(), self.captureOnCommitCallbacks(execute=True):
            call_command("end_idle_games", stdout=StringIO())

        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.ended_at)


@override_settings(**TEST_BACKENDS)
class IdleEndSettingTests(TempMediaRootMixin, TestCase):
    """idle_end_days: per game, set by the host in the create form."""

    def setUp(self):
        self.host = create_host()
        self.client.force_login(self.host)

    def create(self, **overrides):
        with muted():
            return self.client.post("/game/create/", create_form_data(**overrides))

    def test_a_game_without_a_choice_gets_30_days(self):
        """Also what the migration gives every existing game."""
        with muted():
            game = create_game_session(self.host)

        self.assertEqual(game.idle_end_days, 30)

    def test_the_create_form_offers_30_days(self):
        from game.forms import GameSessionCreateForm

        form = GameSessionCreateForm()

        self.assertIn("idle_end_days", form.fields)
        self.assertEqual(form.fields["idle_end_days"].initial, 30)

    def test_the_host_sets_it_when_creating_a_game(self):
        response = self.create(game_name="Kurz", idle_end_days=7)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(GameSession.objects.get(game_name="Kurz").idle_end_days, 7)

    def test_zero_days_is_refused(self):
        response = self.create(game_name="Null", idle_end_days=0)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(GameSession.objects.filter(game_name="Null").exists())

    def test_more_than_a_year_is_refused(self):
        response = self.create(game_name="Ewig", idle_end_days=366)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(GameSession.objects.filter(game_name="Ewig").exists())

    def test_the_beat_schedule_ends_idle_games_daily(self):
        """On a crontab: beat keeps no state across rebuilds, so an interval
        would restart with every deploy."""
        from celery.schedules import crontab
        from django.conf import settings as django_settings

        entries = [
            entry
            for entry in django_settings.CELERY_BEAT_SCHEDULE.values()
            if entry["task"] == "game.tasks.end_idle_games"
        ]
        self.assertEqual(len(entries), 1)
        self.assertIsInstance(entries[0]["schedule"], crontab)


@override_settings(**TEST_BACKENDS)
class AccountAnonymisationTests(TempMediaRootMixin, TestCase):
    """DSGVO erasure for the host account. Decided 2026-09-24.

    The host is the only real auth.User this project has, and
    GameSession.game_host is on_delete=CASCADE — so deleting that row would
    take every game the host ever ran, and the thesis data with it. The answer
    is the one already given for players: the name goes, the rows stay.

    Running games end, because a host who deletes their account mid-lesson is
    not coming back to press stop.
    """

    def setUp(self):
        self.host = create_host(
            username="werblinski",
            email="sebastian@example.com",
            first_name="Sebastian",
            last_name="Werblinski",
        )
        with muted():
            self.running = create_game_session(self.host, game_name="Laufend")
            GameSession.objects.filter(pk=self.running.pk).update(
                is_active=True, started_at=timezone.now()
            )
            self.running.refresh_from_db()
            self.host_row = Player.objects.create(
                game=self.running,
                user=self.host,
                name="Sebastian Werblinski (Host)",
            )
            self.student = Player.objects.create(game=self.running, name="Mia")

    def anonymise(self):
        from game.anon import anonymise_account

        with muted():
            return anonymise_account(self.host)

    # --- the row survives, because CASCADE would take the games -------------

    def test_the_account_row_survives(self):
        self.anonymise()

        self.assertTrue(
            get_user_model().objects.filter(pk=self.host.pk).exists(),
            "deleting the row cascades onto every game this host ever ran",
        )

    def test_the_games_survive(self):
        self.anonymise()

        self.running.refresh_from_db()
        self.assertEqual(self.running.game_host_id, self.host.pk)

    def test_the_moves_and_players_survive(self):
        self.anonymise()

        self.assertTrue(Player.objects.filter(pk=self.student.pk).exists())

    # --- what is actually stripped -----------------------------------------

    def test_the_username_is_gone(self):
        self.anonymise()

        self.host.refresh_from_db()
        self.assertNotIn("werblinski", self.host.username.lower())

    def test_the_username_names_the_row_and_stays_unique(self):
        self.anonymise()

        self.host.refresh_from_db()
        self.assertEqual(self.host.username, f"geloescht-{self.host.pk}")

    def test_the_personal_fields_are_emptied(self):
        self.anonymise()

        self.host.refresh_from_db()
        self.assertEqual(self.host.first_name, "")
        self.assertEqual(self.host.last_name, "")
        self.assertEqual(self.host.email, "")

    def test_the_account_can_no_longer_be_used(self):
        self.anonymise()

        self.host.refresh_from_db()
        self.assertFalse(self.host.is_active)
        self.assertFalse(self.host.has_usable_password())

    # --- the host's own Player rows ----------------------------------------

    def test_the_host_row_loses_the_real_name(self):
        """GameSessionCreateView writes "<full name> (Host)" into the row."""
        self.anonymise()

        self.host_row.refresh_from_db()
        self.assertEqual(self.host_row.name, "Host")

    def test_the_host_row_is_still_found_by_account(self):
        """The trap: clearing Player.user would make host_rows() miss it, and
        the later game anonymisation would number the host as a Spieler."""
        self.anonymise()

        host_rows = Player.objects.filter(game=self.running).host_rows()
        self.assertEqual(list(host_rows), [self.host_row])

    def test_the_students_are_not_renamed_yet(self):
        """Player anonymisation stays with the grace-period beat job."""
        self.anonymise()

        self.student.refresh_from_db()
        self.assertEqual(self.student.name, "Mia")

    # --- the running games --------------------------------------------------

    def test_a_running_game_is_ended(self):
        self.anonymise()

        self.running.refresh_from_db()
        self.assertIsNotNone(self.running.ended_at)
        self.assertFalse(self.running.is_active)

    def test_the_ending_is_recorded_as_the_host(self):
        self.anonymise()

        self.running.refresh_from_db()
        self.assertEqual(self.running.end_reason, GameSession.EndReason.HOST)

    def test_a_paused_game_is_ended_too(self):
        GameSession.objects.filter(pk=self.running.pk).update(
            paused_at=timezone.now()
        )

        self.anonymise()

        self.running.refresh_from_db()
        self.assertIsNotNone(self.running.ended_at)
        self.assertIsNone(self.running.paused_at)

    def test_an_already_ended_game_keeps_its_own_reason(self):
        ended_at = timezone.now() - timezone.timedelta(days=2)
        with muted():
            old = create_game_session(self.host, game_name="Fertig")
        GameSession.objects.filter(pk=old.pk).update(
            ended_at=ended_at,
            is_active=False,
            end_reason=GameSession.EndReason.MAX_ROUNDS,
        )

        self.anonymise()

        old.refresh_from_db()
        self.assertEqual(old.end_reason, GameSession.EndReason.MAX_ROUNDS)
        self.assertEqual(old.ended_at, ended_at)

    def test_somebody_elses_game_keeps_running(self):
        other_host = create_host(username="kollegin")
        with muted():
            theirs = create_game_session(other_host, game_name="Fremd")
            GameSession.objects.filter(pk=theirs.pk).update(is_active=True)

        self.anonymise()

        theirs.refresh_from_db()
        self.assertIsNone(theirs.ended_at)
        self.assertTrue(theirs.is_active)

    def test_the_players_are_told_the_game_ended(self):
        listener = GroupListener(self.running.game_id)

        self.anonymise()

        self.assertIn("game.ended", listener.names())

    # --- shape --------------------------------------------------------------

    def test_it_returns_the_number_of_games_ended(self):
        self.assertEqual(self.anonymise(), 1)

    def test_running_it_twice_changes_nothing(self):
        self.anonymise()
        self.host.refresh_from_db()
        username_after_one = self.host.username

        self.assertEqual(self.anonymise(), 0)

        self.host.refresh_from_db()
        self.assertEqual(self.host.username, username_after_one)
