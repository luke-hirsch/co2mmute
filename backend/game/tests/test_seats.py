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

from co2mmute.utils import unsign_value
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


# ─────────────────────────────────────────────────────────────────────────────
# Roadmap.md 1.7: a seat moves to another device
#
# game.seats' new names are imported inside the tests: they don't exist before
# the seat-handover guide.
# ─────────────────────────────────────────────────────────────────────────────

CODE_PATTERN = r"^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$"


def code_url(game_id, player_id):
    return f"/api/game/{game_id}/player/{player_id}/code/"


def takeover_url(game_id, player_id):
    return f"/api/game/{game_id}/player/{player_id}/takeover/"


def seat_code_url(code):
    return f"/api/game/seat/{code}/"


class HandoverMixin(SeatsMixin):
    """A running game with an open round. Cem plays at the host machine."""

    def setUp(self):
        super().setUp()
        with muted():
            self.cem = Player.objects.create(
                game=self.game, name="Cem", controlled_by_host=True
            )
        self.start()
        self.round = self.open_round()

    def issue(self, player):
        """A code for the seat, straight from game.seats."""
        from game.seats import issue_code

        return issue_code(player)

    def request_code(self, player):
        with muted():
            return self.client.post(code_url(self.game.game_id, player.player_id))

    def take_over(self, player):
        with muted(), self.captureOnCommitCallbacks(execute=True):
            return self.client.post(takeover_url(self.game.game_id, player.player_id))

    def peek(self, code):
        with muted():
            return self.client.get(seat_code_url(code))

    def redeem(self, code):
        with muted(), self.captureOnCommitCallbacks(execute=True):
            return self.client.post(seat_code_url(code))

    def fresh_client(self):
        """Another browser: no session, no cookies."""
        self.client = self.client_class()

    def post_move(self, player_id):
        with muted(), self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                f"/api/game/{self.game.game_id}/player/{player_id}/move/",
                {"action": "car", "payload": {}},
                content_type="application/json",
            )

    def seat_listener(self, player):
        from game import roster

        return GroupListener(group=roster.player_group(player.pk))

    def revocations(self, listener):
        return [
            message["reason"]
            for message in listener.messages()
            if message.get("type") == "player_revoked"
        ]


@override_settings(**TEST_BACKENDS)
class IssueCodeTests(HandoverMixin, TestCase):
    """POST /api/game/<game_id>/player/<player_id>/code/."""

    def test_a_player_gets_a_code_for_their_own_seat(self):
        self.as_player(self.anna)

        response = self.request_code(self.anna)

        self.assertEqual(response.status_code, 201)
        self.assertRegex(response.json()["code"], CODE_PATTERN)
        self.assertEqual(response.json()["expires_in"], 300)

    def test_the_host_gets_a_code_for_a_seat_at_the_host_machine(self):
        self.as_host()

        response = self.request_code(self.cem)

        self.assertEqual(response.status_code, 201)

    def test_the_host_gets_no_code_for_a_students_seat(self):
        """Take it over first. A student's seat is the student's."""
        self.as_host()

        self.assertEqual(self.request_code(self.anna).status_code, 403)

    def test_a_player_gets_no_code_for_another_seat(self):
        self.as_player(self.anna)

        self.assertEqual(self.request_code(self.ben).status_code, 403)
        self.assertEqual(self.request_code(self.cem).status_code, 403)

    def test_there_is_no_code_for_the_host_row(self):
        self.as_host()
        log_in_as_player(self.client, self.game.game_id, self.host_row.player_id)

        response = self.request_code(self.host_row)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "host")

    def test_there_is_no_code_in_an_ended_game(self):
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=False, ended_at=timezone.now()
        )
        self.as_player(self.anna)

        response = self.request_code(self.anna)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "ended")

    def test_a_new_code_kills_the_old_one(self):
        self.as_player(self.anna)
        old = self.request_code(self.anna).json()["code"]

        new = self.request_code(self.anna).json()["code"]

        self.assertEqual(self.peek(old).status_code, 404)
        self.assertEqual(self.peek(new).status_code, 200)

    def test_a_code_can_be_made_during_the_pause(self):
        GameSession.objects.filter(pk=self.game.pk).update(paused_at=timezone.now())
        self.as_host()

        self.assertEqual(self.request_code(self.cem).status_code, 201)


@override_settings(**TEST_BACKENDS)
class PeekCodeTests(HandoverMixin, TestCase):
    """GET /api/game/seat/<code>/ — "Du übernimmst Cem?" before anything happens."""

    def test_it_names_the_game_and_the_seat_without_any_cookie(self):
        code = self.issue(self.cem)

        response = self.peek(code)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "game_id": self.game.game_id,
                "game_name": "Plaetze",
                "player_name": "Cem",
            },
        )

    def test_looking_does_not_use_the_code_up(self):
        code = self.issue(self.cem)

        self.peek(code)
        self.peek(code)

        self.assertEqual(self.redeem(code).status_code, 200)

    def test_lower_case_is_fine(self):
        code = self.issue(self.cem)

        self.assertEqual(self.peek(code.lower()).status_code, 200)

    def test_an_unknown_code_is_a_404(self):
        self.assertEqual(self.peek("ZZZZZZ").status_code, 404)

    def test_a_code_runs_out(self):
        with patch("game.seats.CODE_TTL", 0):
            code = self.issue(self.cem)

        self.assertEqual(self.peek(code).status_code, 404)

    def test_the_code_of_a_seat_that_left_is_dead(self):
        code = self.issue(self.cem)
        Player.objects.filter(pk=self.cem.pk).update(left_at=timezone.now())

        self.assertEqual(self.peek(code).status_code, 404)

    def test_the_code_of_an_ended_game_is_refused(self):
        code = self.issue(self.cem)
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=False, ended_at=timezone.now()
        )

        response = self.peek(code)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "ended")


@override_settings(**TEST_BACKENDS)
class RedeemCodeTests(HandoverMixin, TestCase):
    """POST /api/game/seat/<code>/ — the phone takes the seat."""

    def test_the_new_device_gets_the_seat_under_a_new_id(self):
        code = self.issue(self.cem)
        old_id = self.cem.player_id

        response = self.redeem(code)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.cem.refresh_from_db()
        self.assertNotEqual(self.cem.player_id, old_id)
        self.assertEqual(payload["player_id"], self.cem.player_id)
        self.assertEqual(payload["name"], "Cem")
        self.assertEqual(payload["game_id"], self.game.game_id)
        self.assertIn("agent_assignments", payload)

    def test_the_seat_is_no_longer_played_at_the_host_machine(self):
        self.redeem(self.issue(self.cem))

        self.cem.refresh_from_db()
        self.assertFalse(self.cem.controlled_by_host)

    def test_the_new_device_gets_both_cookies_for_the_new_id(self):
        response = self.redeem(self.issue(self.cem))

        self.cem.refresh_from_db()
        player_cookie = response.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ]
        self.assertIn(
            f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}", response.cookies
        )
        self.assertEqual(
            unsign_value(player_cookie.value, settings.COOKIE_PLAYER_SALT),
            f"{self.game.game_id}:{self.cem.player_id}",
        )

    def test_the_new_device_can_play(self):
        self.redeem(self.issue(self.cem))
        self.cem.refresh_from_db()

        response = self.post_move(self.cem.player_id)

        self.assertEqual(response.status_code, 200)

    def test_a_code_works_once(self):
        code = self.issue(self.cem)
        self.redeem(code)
        self.fresh_client()

        self.assertEqual(self.redeem(code).status_code, 404)

    def test_the_old_device_is_out(self):
        """A student's own code ("auf anderes Gerät"): the first phone's
        cookie names an id that no longer exists."""
        self.as_player(self.anna)
        code = self.request_code(self.anna).json()["code"]
        old_id = self.anna.player_id
        old_browser = self.client
        self.fresh_client()

        self.redeem(code)

        self.client = old_browser
        self.assertEqual(self.post_move(old_id).status_code, 403)

    def test_the_old_device_is_revoked(self):
        listener = self.seat_listener(self.anna)
        code = self.issue(self.anna)

        self.redeem(code)

        self.assertEqual(self.revocations(listener), ["handed_over"])

    def test_the_game_hears_about_the_new_id(self):
        old_id = self.cem.player_id
        listener = GroupListener(self.game.game_id)

        self.redeem(self.issue(self.cem))

        self.cem.refresh_from_db()
        self.assertEqual(
            listener.data("player.handed_over"),
            {"old_player_id": old_id, "new_player_id": self.cem.player_id},
        )
        self.assertIsNotNone(entry(listener.rosters()[-1], self.cem))

    def test_moves_votes_and_acks_stay_with_the_seat(self):
        from game.models import StatsAck

        move = self.move(self.round, self.cem)
        StatsAck.objects.create(game_round=self.round, player=self.cem)

        self.redeem(self.issue(self.cem))

        move.refresh_from_db()
        self.assertEqual(move.player_id, self.cem.pk)
        self.assertTrue(StatsAck.objects.filter(player=self.cem).exists())

    def test_the_host_cannot_redeem_in_their_own_game(self):
        """The host is the session. A seat cookie in the host's browser would
        be a seat without a device."""
        code = self.issue(self.cem)
        self.as_host()

        response = self.redeem(code)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "host")
        self.fresh_client()
        self.assertEqual(self.redeem(code).status_code, 200, msg="code still live")

    def test_someone_elses_host_account_can_redeem(self):
        """A researcher logged into their own host account, joining this game
        as a player (CLAUDE.md, "players are minors")."""
        self.client.force_login(create_host(username="forscherin"))

        self.assertEqual(self.redeem(self.issue(self.cem)).status_code, 200)

    def test_a_browser_with_another_seat_here_is_refused(self):
        code = self.issue(self.cem)
        self.as_player(self.anna)

        response = self.redeem(code)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "seated")
        self.fresh_client()
        self.assertEqual(self.redeem(code).status_code, 200, msg="code still live")

    def test_a_browser_whose_seat_left_may_take_another(self):
        code = self.issue(self.cem)
        self.as_player(self.anna)
        Player.objects.filter(pk=self.anna.pk).update(left_at=timezone.now())

        self.assertEqual(self.redeem(code).status_code, 200)

    def test_the_seats_own_browser_may_redeem_its_code(self):
        self.as_player(self.anna)
        code = self.request_code(self.anna).json()["code"]

        self.assertEqual(self.redeem(code).status_code, 200)

    def test_an_ended_game_refuses(self):
        code = self.issue(self.cem)
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=False, ended_at=timezone.now()
        )

        response = self.redeem(code)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "ended")

    def test_a_seat_changes_hands_during_the_pause(self):
        GameSession.objects.filter(pk=self.game.pk).update(paused_at=timezone.now())

        self.assertEqual(self.redeem(self.issue(self.cem)).status_code, 200)

    def test_redeem_code_is_single_use_at_the_source(self):
        """cache.delete() says True to one caller only."""
        from game.seats import SeatRefused, redeem_code

        code = self.issue(self.cem)
        with muted(), self.captureOnCommitCallbacks(execute=True):
            redeem_code(code)

        with self.assertRaises(SeatRefused):
            redeem_code(code)


@override_settings(**TEST_BACKENDS)
class TakeoverTests(HandoverMixin, TestCase):
    """POST /api/game/<game_id>/player/<player_id>/takeover/ — the host plays
    a student's seat from now on."""

    def test_the_host_takes_a_seat_over(self):
        old_id = self.anna.player_id
        self.as_host()

        response = self.take_over(self.anna)

        self.assertEqual(response.status_code, 200)
        self.anna.refresh_from_db()
        self.assertTrue(self.anna.controlled_by_host)
        self.assertNotEqual(self.anna.player_id, old_id)
        self.assertEqual(response.json()["player_id"], self.anna.player_id)

    def test_the_host_plays_the_seat_afterwards(self):
        self.as_host()
        self.take_over(self.anna)
        self.anna.refresh_from_db()

        self.assertEqual(self.post_move(self.anna.player_id).status_code, 200)

    def test_the_students_device_is_out(self):
        old_id = self.anna.player_id
        self.as_host()
        self.take_over(self.anna)
        self.fresh_client()
        log_in_as_player(self.client, self.game.game_id, old_id)

        self.assertEqual(self.post_move(old_id).status_code, 403)

    def test_the_students_sockets_are_revoked(self):
        listener = self.seat_listener(self.anna)
        self.as_host()

        self.take_over(self.anna)

        self.assertEqual(self.revocations(listener), ["taken_over"])

    def test_the_game_hears_about_it(self):
        old_id = self.anna.player_id
        listener = GroupListener(self.game.game_id)
        self.as_host()

        self.take_over(self.anna)

        self.anna.refresh_from_db()
        self.assertEqual(
            listener.data("player.taken_over"),
            {"old_player_id": old_id, "new_player_id": self.anna.player_id},
        )
        anna = entry(listener.rosters()[-1], self.anna)
        self.assertTrue(anna["controlled_by_host"])

    def test_a_live_code_for_the_seat_dies(self):
        """Misuse is repaired by taking over, then a new code."""
        code = self.issue(self.anna)
        self.as_host()

        self.take_over(self.anna)

        self.assertEqual(self.peek(code).status_code, 404)

    def test_the_moves_stay(self):
        move = self.move(self.round, self.anna)
        self.as_host()

        self.assertEqual(self.take_over(self.anna).status_code, 200)

        move.refresh_from_db()
        self.assertEqual(move.player_id, self.anna.pk)

    def test_a_seat_at_the_host_machine_is_refused(self):
        self.as_host()

        response = self.take_over(self.cem)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "controlled")

    def test_the_host_row_is_refused(self):
        self.as_host()

        response = self.take_over(self.host_row)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "host")

    def test_an_ended_game_refuses(self):
        GameSession.objects.filter(pk=self.game.pk).update(
            is_active=False, ended_at=timezone.now()
        )
        self.as_host()

        response = self.take_over(self.anna)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "ended")

    def test_a_removed_seat_is_a_404(self):
        """Passes before the guide too, because the route is missing then;
        test_join pins the route."""
        Player.objects.filter(pk=self.anna.pk).update(left_at=timezone.now())
        self.as_host()

        self.assertEqual(self.take_over(self.anna).status_code, 404)

    def test_a_player_cannot_take_over(self):
        self.as_player(self.ben)

        self.assertEqual(self.take_over(self.anna).status_code, 403)
        self.anna.refresh_from_db()
        self.assertFalse(self.anna.controlled_by_host)

    def test_the_host_takes_over_during_the_pause(self):
        GameSession.objects.filter(pk=self.game.pk).update(paused_at=timezone.now())
        self.as_host()

        self.assertEqual(self.take_over(self.anna).status_code, 200)


@override_settings(**TEST_BACKENDS)
class ClassroomScenarioTests(HandoverMixin, TestCase):
    """The whole 1.6 + 1.7 story, as the plan tells it.

    The bell pauses the game. Next lesson Anna is missing, and the host takes
    her seat over. She comes back, the host shows a code, her phone takes the
    seat back, and the game goes on.
    """

    def test_a_seat_goes_to_the_host_and_back(self):
        from game.pause import pause_game, resume_game

        annas_phone = self.client
        self.as_player(self.anna)
        self.assertEqual(self.post_move(self.anna.player_id).status_code, 200)

        host_screen = self.client_class()
        host_screen.force_login(self.host)
        self.client = host_screen
        with muted(), self.captureOnCommitCallbacks(execute=True):
            pause_game(self.game.game_id)
        self.take_over(self.anna)
        self.anna.refresh_from_db()
        code = self.request_code(self.anna).json()["code"]

        self.client = annas_phone
        self.assertEqual(self.peek(code).json()["player_name"], "Anna")
        self.assertEqual(self.redeem(code).status_code, 200)
        with muted(), self.captureOnCommitCallbacks(execute=True):
            resume_game(self.game.game_id)

        self.anna.refresh_from_db()
        self.assertFalse(self.anna.controlled_by_host)
        self.assertEqual(self.post_move(self.anna.player_id).status_code, 200)
        self.assertEqual(
            PlayerMove.objects.filter(
                player=self.anna, session_round=self.round
            ).count(),
            1,
        )
