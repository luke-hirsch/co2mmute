"""Seats: adding, removing, and (1.7) handing them over. game/seats.py.

A new topic file for a new module. Roadmap.md 1.6: the host adds seats that are
played at the host machine, in the lobby and while the game runs, and removes
seats. After the start a removed seat keeps its row (left_at), because its moves
are research data.

Everything goes through the REST endpoints the SPA will call, so the
permissions are part of what is tested. The routes themselves are pinned in
test_join.UrlRoutingTests.
"""

from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from game.models import GameRound, GameSession, Player, PlayerMove

from ._helpers import (
    TEST_BACKENDS,
    GroupListener,
    TempMediaRootMixin,
    create_game_session,
    create_host,
    log_in_as_player,
    muted,
)


def seats_url(game_id):
    return f"/api/game/{game_id}/player/"


def seat_url(game_id, player_id):
    return f"/api/game/{game_id}/player/{player_id}/"


def entry(players, player):
    return next((p for p in players if p["player_id"] == player.player_id), None)


class SeatsMixin(TempMediaRootMixin):
    """A lobby: the host's own row (as GameSessionCreateView makes it after
    1.6, not host-controlled), Anna and Ben."""

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Plaetze")
            self.host_row = Player.objects.create(
                game=self.game, name="Host", user=self.host
            )
            self.anna = Player.objects.create(game=self.game, name="Anna")
            self.ben = Player.objects.create(game=self.game, name="Ben")

    def start(self):
        """is_active goes in with update(): save() resets it without a map."""
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=True, started_at=timezone.now()
        )
        self.game.refresh_from_db()

    def open_round(self):
        return GameRound.objects.create(
            game=self.game, round_number=1, status=GameRound.Status.ACTIVE
        )

    def move(self, game_round, player):
        with muted():
            return PlayerMove.objects.create(
                session_round=game_round, player=player, action="car"
            )

    def as_host(self):
        self.client.force_login(self.host)

    def as_player(self, player):
        log_in_as_player(self.client, self.game.game_id, player.player_id)

    def add(self, name="Ohne Handy", game=None):
        game = game or self.game
        with muted(), self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                seats_url(game.game_id), {"name": name}, content_type="application/json"
            )

    def remove(self, player):
        with muted(), self.captureOnCommitCallbacks(execute=True):
            return self.client.delete(seat_url(self.game.game_id, player.player_id))


@override_settings(**TEST_BACKENDS)
class AddSeatTests(SeatsMixin, TestCase):
    """POST /api/game/<game_id>/player/ — the host adds a seat. It was a 405."""

    def test_the_host_adds_a_seat_in_the_lobby(self):
        self.as_host()

        response = self.add("Ohne Handy")

        self.assertEqual(response.status_code, 201)
        seat = Player.objects.get(
            game=self.game, player_id=response.json()["player_id"]
        )
        self.assertEqual(seat.name, "Ohne Handy")
        self.assertTrue(seat.controlled_by_host)
        self.assertTrue(seat.player_id.startswith("P-"))
        self.assertIn("agent_assignments", response.json())

    def test_the_host_adds_a_seat_while_the_game_runs(self):
        self.start()
        self.as_host()

        response = self.add()

        self.assertEqual(response.status_code, 201)

    def test_the_new_seat_is_a_player_not_the_host(self):
        self.as_host()

        player_id = self.add().json()["player_id"]

        playing = Player.objects.filter(game=self.game).playing()
        self.assertTrue(playing.filter(player_id=player_id).exists())
        self.assertFalse(
            Player.objects.filter(game=self.game)
            .host_rows()
            .filter(player_id=player_id)
            .exists()
        )

    def test_the_host_keeps_their_own_cookies(self):
        """The host acts for the seat through the session (IsPlayerInGame's
        host branch). A player cookie for the seat would replace the host's."""
        self.as_host()

        response = self.add()

        self.assertNotIn(
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}", response.cookies
        )

    def test_a_player_cannot_add_a_seat(self):
        self.as_player(self.anna)

        response = self.add()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Player.objects.filter(game=self.game).count(), 3)

    def test_nobody_without_a_login_can_add_a_seat(self):
        """A guard, green from the start."""
        response = self.add()

        self.assertEqual(response.status_code, 403)

    def test_another_games_host_cannot_add_a_seat(self):
        other_host = create_host(username="other-host")
        self.client.force_login(other_host)

        response = self.add()

        self.assertEqual(response.status_code, 403)

    def test_no_seat_after_the_game_ended(self):
        GameSession.objects.filter(pk=self.game.pk).update(
            ended_at=timezone.now(), is_active=False
        )
        self.as_host()

        response = self.add()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "ended")

    def test_no_seat_beyond_max_players(self):
        """Anna and Ben are two seats. The host row is not one."""
        GameSession.objects.filter(pk=self.game.pk).update(max_players=3)
        self.as_host()

        first = self.add("Dritte")
        second = self.add("Vierte")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["reason"], "full")

    def test_a_seat_at_the_host_machine_counts_against_max_players(self):
        """A student joining after the host filled the game is refused."""
        GameSession.objects.filter(pk=self.game.pk).update(max_players=3)
        self.as_host()
        self.add("Dritte")
        self.client.logout()

        with muted():
            response = self.client.post(
                f"/api/game/join/{self.game.game_id}/",
                {"name": "Zu spaet"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "full")

    def test_a_blank_name_is_refused(self):
        self.as_host()

        response = self.add("   ")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Player.objects.filter(game=self.game).count(), 3)

    def test_the_new_seat_is_announced(self):
        listener = GroupListener(self.game.game_id)
        self.as_host()

        player_id = self.add().json()["player_id"]

        joined = listener.data("player.joined")
        self.assertEqual(joined["player_id"], player_id)
        self.assertTrue(joined["controlled_by_host"])
        last_roster = listener.rosters()[-1]
        self.assertIn(player_id, [p["player_id"] for p in last_roster])

    def test_a_seat_added_during_a_round_is_waited_for(self):
        """The host plays it from the round it joins in."""
        from game.rounds import complete_round_if_ready

        self.start()
        game_round = self.open_round()
        self.move(game_round, self.anna)
        self.move(game_round, self.ben)
        self.as_host()
        self.add()

        with patch("game.tasks.run_simulation_task.delay") as delay, muted():
            self.assertFalse(complete_round_if_ready(self.game.game_id))
        delay.assert_not_called()


@override_settings(**TEST_BACKENDS)
class RemoveSeatTests(SeatsMixin, TestCase):
    """DELETE /api/game/<game_id>/player/<player_id>/.

    Before the start the row goes, as it always did. After the start it stays
    with left_at, so its moves and votes stay research data.
    """

    def revocations(self, listener):
        return [
            message["reason"]
            for message in listener.messages()
            if message.get("type") == "player_revoked"
        ]

    def seat_listener(self, player):
        from game import roster

        return GroupListener(group=roster.player_group(player.pk))

    def test_before_the_start_the_row_is_deleted(self):
        """A guard, green from the start."""
        self.as_host()

        response = self.remove(self.anna)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Player.objects.filter(pk=self.anna.pk).exists())

    def test_after_the_start_the_host_removal_keeps_the_row(self):
        self.start()
        self.as_host()

        response = self.remove(self.anna)

        self.assertEqual(response.status_code, 204)
        self.anna.refresh_from_db()
        self.assertIsNotNone(self.anna.left_at)
        self.assertFalse(
            Player.objects.filter(game=self.game)
            .playing()
            .filter(pk=self.anna.pk)
            .exists()
        )

    def test_after_the_start_a_player_who_leaves_keeps_the_row(self):
        self.start()
        self.as_player(self.anna)

        response = self.remove(self.anna)

        self.assertEqual(response.status_code, 204)
        self.anna.refresh_from_db()
        self.assertIsNotNone(self.anna.left_at)

    def test_the_moves_of_a_removed_seat_stay(self):
        self.start()
        game_round = self.open_round()
        self.move(game_round, self.anna)
        self.as_host()

        self.remove(self.anna)

        self.assertTrue(PlayerMove.objects.filter(player_id=self.anna.pk).exists())

    def test_the_host_removing_a_seat_revokes_it_as_removed(self):
        """kicked used to come from ?kicked=true. It follows from who asks now:
        anyone but the seat's own player removes it."""
        self.start()
        listener = self.seat_listener(self.anna)
        self.as_host()

        self.remove(self.anna)

        self.assertEqual(self.revocations(listener), ["removed"])
        self.assertTrue(Player.objects.filter(pk=self.anna.pk).exists())

    def test_a_player_who_leaves_is_revoked_as_left(self):
        self.start()
        listener = self.seat_listener(self.anna)
        self.as_player(self.anna)

        self.remove(self.anna)

        self.assertEqual(self.revocations(listener), ["left"])
        self.assertTrue(Player.objects.filter(pk=self.anna.pk).exists())

    def test_a_removal_after_the_start_is_announced(self):
        self.start()
        listener = GroupListener(self.game.game_id)
        self.as_host()

        self.remove(self.anna)

        left = listener.data("player.left")
        self.assertEqual(left["player_id"], self.anna.player_id)
        self.assertTrue(left["was_kicked"])
        self.assertIsNone(entry(listener.rosters()[-1], self.anna))
        self.assertTrue(Player.objects.filter(pk=self.anna.pk).exists())

    def test_removing_a_seat_twice_is_a_404(self):
        self.start()
        self.as_host()
        self.remove(self.anna)

        response = self.remove(self.anna)

        self.assertEqual(response.status_code, 404)

    def test_the_host_keeps_their_cookies(self):
        """destroy() used to delete the requester's cookies, whoever it was."""
        self.as_host()
        log_in_as_player(self.client, self.game.game_id, self.host_row.player_id)

        response = self.remove(self.anna)

        self.assertEqual(response.status_code, 204)
        self.assertNotIn(
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}", response.cookies
        )
        self.assertNotIn(
            f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}", response.cookies
        )

    def test_a_player_who_leaves_loses_their_cookies(self):
        """A guard, green from the start."""
        self.as_player(self.anna)

        response = self.remove(self.anna)

        for prefix in (settings.COOKIE_PLAYER_PREFIX, settings.COOKIE_GAME_PREFIX):
            cookie = response.cookies[f"{prefix}{self.game.game_id}"]
            self.assertEqual(cookie.value, "")
            self.assertEqual(cookie["max-age"], 0)

    def test_the_last_outstanding_seat_leaving_completes_the_round(self):
        self.start()
        game_round = self.open_round()
        self.move(game_round, self.anna)
        self.as_host()

        with patch("game.tasks.run_simulation_task.delay") as delay:
            self.remove(self.ben)

        game_round.refresh_from_db()
        self.assertEqual(game_round.status, GameRound.Status.COMPLETED)
        delay.assert_called_once_with(game_round.pk)
        self.assertTrue(Player.objects.filter(pk=self.ben.pk).exists())

    def test_the_last_outstanding_seat_leaving_finishes_the_stats_phase(self):
        from game.models import StatsAck

        self.start()
        game_round = GameRound.objects.create(
            game=self.game,
            round_number=1,
            status=GameRound.Status.COMPLETED,
            between_round_phase=GameRound.BetweenRoundPhase.STATS,
        )
        StatsAck.objects.create(game_round=game_round, player=self.anna)
        self.as_host()

        self.remove(self.ben)

        self.assertTrue(
            GameRound.objects.filter(game=self.game, round_number=2).exists()
        )
        self.assertTrue(Player.objects.filter(pk=self.ben.pk).exists())
