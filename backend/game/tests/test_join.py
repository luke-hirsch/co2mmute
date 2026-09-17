"""The pre-join surface: session lookup, joining, lobby state.

A new topic file. The convention is that a feature's tests go in the topic file
that owns the code, and nothing owned this one — until Roadmap.md 1.4 there was
no way to ask "does this game exist and can I join it?" without already holding a
cookie.

URLs are written out literally rather than reversed. These paths are the contract
the SPA hardcodes, so a rename should fail here rather than be papered over by
reverse().
"""

from django.conf import settings
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from co2mmute.utils import sign_value
from game.cache import invalidate_game_session
from game.models import GameSession, Player

from ._helpers import (
    TEST_BACKENDS,
    TempMediaRootMixin,
    create_game_session,
    create_host,
    muted,
)


def lookup_url(game_id):
    return f"/api/game/lookup/{game_id}/"


def join_url(game_id):
    return f"/api/game/join/{game_id}/"


def lobby_url(game_id):
    return f"/api/game/{game_id}/lobby/"


class GameCookieMixin:
    """Mint the game-access cookie the way co2mmute.utils.set_game_access_cookie does."""

    def give_game_access(self, game_id):
        name = f"{settings.COOKIE_GAME_PREFIX}{game_id}"
        self.client.cookies[name] = sign_value(
            f"{game_id}:test-token", settings.COOKIE_GAME_SALT
        )


@override_settings(**TEST_BACKENDS)
class SessionLookupTests(TempMediaRootMixin, TestCase):
    """GET /api/game/lookup/<game_id>/ — answerable without any cookie."""

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Lookup")

    def test_unknown_game_returns_404(self):
        with muted():
            response = self.client.get(lookup_url("NOPE12"))
        self.assertEqual(response.status_code, 404)

    def test_lookup_needs_no_cookie(self):
        response = self.client.get(lookup_url(self.game.game_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["game_id"], self.game.game_id)

    def test_lookup_reports_a_password_without_leaking_it(self):
        with muted():
            self.game.game_password = "geheim"
            self.game.save()

        payload = self.client.get(lookup_url(self.game.game_id)).json()

        self.assertTrue(payload["requires_password"])
        self.assertNotIn("game_password", payload)
        self.assertNotIn("geheim", str(payload))

    def test_open_lobby_reports_no_password(self):
        payload = self.client.get(lookup_url(self.game.game_id)).json()
        self.assertFalse(payload["requires_password"])

    def test_lookup_leaks_neither_host_nor_player_names(self):
        with muted():
            Player.objects.create(game=self.game, name="Mia")

        payload = self.client.get(lookup_url(self.game.game_id)).json()

        self.assertNotIn("Mia", str(payload))
        self.assertNotIn(self.host.username, str(payload))

    def test_started_game_is_not_joinable(self):
        with muted():
            self.game.started_at = timezone.now()
            self.game.is_active = True
            self.game.save()

        payload = self.client.get(lookup_url(self.game.game_id)).json()

        self.assertFalse(payload["joinable"])
        self.assertEqual(payload["reason"], "started")

    def test_ended_game_is_not_joinable(self):
        with muted():
            self.game.ended_at = timezone.now()
            self.game.save()

        payload = self.client.get(lookup_url(self.game.game_id)).json()

        self.assertFalse(payload["joinable"])
        self.assertEqual(payload["reason"], "ended")

    def test_full_game_is_not_joinable(self):
        with muted():
            game = create_game_session(self.host, game_name="Full", max_players=1)
            Player.objects.create(game=game, name="Erste")

        payload = self.client.get(lookup_url(game.game_id)).json()

        self.assertFalse(payload["joinable"])
        self.assertEqual(payload["reason"], "full")
        self.assertEqual(payload["player_count"], 1)
        self.assertEqual(payload["max_players"], 1)

    def test_the_hosts_own_row_does_not_take_a_seat(self):
        """GameSessionCreateView makes a Player row for the host.

        It is not a participant and must not count against max_players. It is
        recognised by its account, not by controlled_by_host.
        """
        with muted():
            game = create_game_session(self.host, game_name="Host row", max_players=1)
            Player.objects.create(
                game=game, name="Host", user=self.host, controlled_by_host=True
            )

        payload = self.client.get(lookup_url(game.game_id)).json()

        self.assertEqual(payload["player_count"], 0)
        self.assertTrue(payload["joinable"])

    def test_a_seat_played_at_the_host_machine_takes_a_place(self):
        """A student at the host machine (Roadmap.md 1.6) is a player and
        counts against max_players like everyone else."""
        with muted():
            game = create_game_session(self.host, game_name="Am Host", max_players=1)
            Player.objects.create(game=game, name="Ohne Handy", controlled_by_host=True)

        payload = self.client.get(lookup_url(game.game_id)).json()

        self.assertEqual(payload["player_count"], 1)
        self.assertEqual(payload["reason"], "full")


@override_settings(**TEST_BACKENDS)
class JoinSessionApiTests(TempMediaRootMixin, TestCase):
    """POST /api/game/join/<game_id>/ — one call replaces two form views."""

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Join")

    def post_join(self, game_id, **body):
        with muted():
            return self.client.post(
                join_url(game_id), body, content_type="application/json"
            )

    def test_join_creates_the_player_and_returns_201(self):
        response = self.post_join(self.game.game_id, name="Testspieler")

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["name"], "Testspieler")
        self.assertTrue(payload["player_id"])
        self.assertTrue(
            Player.objects.filter(
                game=self.game, player_id=payload["player_id"]
            ).exists()
        )

    def test_join_sets_both_signed_cookies(self):
        response = self.post_join(self.game.game_id, name="Testspieler")
        player_id = response.json()["player_id"]

        game_cookie = response.cookies.get(
            f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}"
        )
        player_cookie = response.cookies.get(
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        )

        self.assertIsNotNone(game_cookie, msg="join must set the game-access cookie")
        self.assertIsNotNone(player_cookie, msg="join must set the player cookie")

        game_value = signing.TimestampSigner(salt=settings.COOKIE_GAME_SALT).unsign(
            game_cookie.value
        )
        self.assertTrue(game_value.startswith(f"{self.game.game_id}:"))

        player_value = signing.TimestampSigner(salt=settings.COOKIE_PLAYER_SALT).unsign(
            player_cookie.value
        )
        # 1.2 binds the player cookie to its game; until then it is the bare id.
        self.assertIn(player_id, player_value)

    def test_join_rejects_a_wrong_password(self):
        with muted():
            self.game.game_password = "geheim"
            self.game.save()

        response = self.post_join(self.game.game_id, name="Mia", password="falsch")

        self.assertEqual(response.status_code, 403)
        # The message matters: without the endpoint this path 403s anyway, from
        # HasGameAccess on the view the URL currently falls through to. Asserting
        # the endpoint's own wording is what keeps this test honest.
        self.assertEqual(response.json()["detail"], "Incorrect password.")
        self.assertFalse(Player.objects.filter(game=self.game).exists())

    def test_join_rejects_a_missing_password_when_one_is_set(self):
        with muted():
            self.game.game_password = "geheim"
            self.game.save()

        response = self.post_join(self.game.game_id, name="Mia")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Incorrect password.")

    def test_join_accepts_the_right_password(self):
        with muted():
            self.game.game_password = "geheim"
            self.game.save()

        response = self.post_join(self.game.game_id, name="Mia", password="geheim")

        self.assertEqual(response.status_code, 201)

    def test_join_rejects_a_blank_name(self):
        response = self.post_join(self.game.game_id, name="   ")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Player.objects.filter(game=self.game).exists())

    def test_join_rejects_a_missing_name(self):
        response = self.post_join(self.game.game_id)
        self.assertEqual(response.status_code, 400)

    def test_join_after_the_game_started_returns_409(self):
        with muted():
            self.game.started_at = timezone.now()
            self.game.is_active = True
            self.game.save()

        response = self.post_join(self.game.game_id, name="Zuspaet")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "started")

    def test_join_after_the_game_ended_returns_409(self):
        with muted():
            self.game.ended_at = timezone.now()
            self.game.save()

        response = self.post_join(self.game.game_id, name="Zuspaet")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "ended")

    def test_join_when_full_returns_409(self):
        """max_players is enforced nowhere today — a lobby takes unlimited players."""
        with muted():
            game = create_game_session(self.host, game_name="Full", max_players=1)
            Player.objects.create(game=game, name="Erste")

        response = self.post_join(game.game_id, name="Zweite")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "full")
        self.assertEqual(Player.objects.filter(game=game).count(), 1)

    def test_a_player_who_left_frees_their_seat(self):
        with muted():
            game = create_game_session(self.host, game_name="Freed", max_players=1)
            gone = Player.objects.create(game=game, name="Weg")
            gone.left_at = timezone.now()
            gone.save()

        response = self.post_join(game.game_id, name="Neue")

        self.assertEqual(response.status_code, 201)

    def test_join_unknown_game_returns_404(self):
        response = self.post_join("NOPE12", name="Mia")
        self.assertEqual(response.status_code, 404)

    def test_agent_assignments_come_back_in_the_response(self):
        """The post_save receiver assigns nodes when the game has a map.

        With no map there is nothing to assign, so the key is present and null —
        the SPA branches on it either way.
        """
        response = self.post_join(self.game.game_id, name="Mia")

        self.assertIn("agent_assignments", response.json())


@override_settings(**TEST_BACKENDS)
class LobbyStateTests(GameCookieMixin, TempMediaRootMixin, TestCase):
    """GET /api/game/<game_id>/lobby/ — everything the lobby screen renders."""

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Lobby")
            self.player = Player.objects.create(game=self.game, name="Mia")

    def test_lobby_requires_the_game_cookie(self):
        with muted():
            response = self.client.get(lobby_url(self.game.game_id))
        self.assertEqual(response.status_code, 403)

    def test_lobby_returns_the_roster_and_the_settings(self):
        self.give_game_access(self.game.game_id)

        payload = self.client.get(lobby_url(self.game.game_id)).json()

        self.assertEqual(payload["game_name"], "Lobby")
        self.assertEqual(payload["max_players"], self.game.max_players)
        self.assertEqual(payload["agent_per_player"], self.game.agent_per_player)
        self.assertEqual(payload["max_rounds"], self.game.max_rounds)
        self.assertEqual(payload["max_co2_level_kg"], self.game.max_CO2_level)
        self.assertEqual([p["name"] for p in payload["players"]], ["Mia"])

    def test_lobby_omits_players_who_left(self):
        with muted():
            self.player.left_at = timezone.now()
            self.player.save()
        self.give_game_access(self.game.game_id)

        payload = self.client.get(lobby_url(self.game.game_id)).json()

        self.assertEqual(payload["players"], [])

    def test_lobby_reports_the_lifecycle_flags(self):
        self.give_game_access(self.game.game_id)

        payload = self.client.get(lobby_url(self.game.game_id)).json()

        self.assertFalse(payload["is_active"])
        self.assertIsNone(payload["started_at"])
        self.assertIsNone(payload["ended_at"])
        self.assertTrue(payload["joinable"])

    def test_lobby_reports_the_pause(self):
        """Roadmap.md 1.6: the lobby payload is the REST snapshot the SPA
        seeds its state from."""
        self.give_game_access(self.game.game_id)
        before = self.client.get(lobby_url(self.game.game_id)).json()
        paused_at = timezone.now()
        GameSession.objects.filter(pk=self.game.pk).update(paused_at=paused_at)
        invalidate_game_session(self.game.game_id)

        after = self.client.get(lobby_url(self.game.game_id)).json()

        self.assertIsNone(before["paused_at"])
        self.assertEqual(after["paused_at"], paused_at.isoformat())

    def test_lobby_of_an_unknown_game_is_not_reachable(self):
        self.give_game_access("NOPE12")
        with muted():
            response = self.client.get(lobby_url("NOPE12"))
        self.assertEqual(response.status_code, 404)


class UrlRoutingTests(TestCase):
    """Pin each new path to its view.

    Worth its own class because the failure it guards against is silent: both
    `<str:game_id>/` and `<str:game_id>/<str:player_id>/` are entirely dynamic, so
    an unrouted path does not 404 — it lands in GetYourOwnGame and comes back as
    a plausible-looking 403. Status codes alone cannot tell the two apart.
    """

    def test_lookup_resolves_to_the_lookup_view(self):
        match = resolve(lookup_url("ABC123"))
        self.assertEqual(match.func.view_class.__name__, "SessionLookupView")
        self.assertEqual(match.kwargs["game_id"], "ABC123")

    def test_join_resolves_to_the_join_view(self):
        match = resolve(join_url("ABC123"))
        self.assertEqual(match.func.view_class.__name__, "JoinSessionAPIView")
        self.assertEqual(match.kwargs["game_id"], "ABC123")

    def test_lobby_resolves_to_the_lobby_view(self):
        """Must be declared above `<game_id>/<player_id>/` or `lobby` reads as a player id."""
        match = resolve(lobby_url("ABC123"))
        self.assertEqual(match.func.view_class.__name__, "LobbyStateView")
        self.assertEqual(match.kwargs["game_id"], "ABC123")

    def test_pause_and_resume_resolve_to_their_views(self):
        """Roadmap.md 1.6. Two segments each: undeclared, they land in
        GetYourOwnGame with player_id="pause"."""
        pause = resolve("/api/game/ABC123/pause/")
        resume = resolve("/api/game/ABC123/resume/")

        self.assertEqual(pause.func.view_class.__name__, "GamePauseView")
        self.assertEqual(resume.func.view_class.__name__, "GameResumeView")
        self.assertEqual(pause.kwargs["game_id"], "ABC123")

    def test_the_existing_player_routes_still_resolve(self):
        self.assertEqual(
            resolve("/api/game/ABC123/player/").func.view_class.__name__,
            "PlayerListView",
        )
        self.assertEqual(
            resolve("/api/game/ABC123/P-01/").func.view_class.__name__,
            "GetYourOwnGame",
        )


@override_settings(**TEST_BACKENDS)
class SessionsRouteRemovedTests(TempMediaRootMixin, TestCase):
    """GameSessionListView is unreachable and 403s; the guide deletes it.

    `api/game/sessions/` never reached it anyway — `<str:game_id>/` is declared
    first and swallows any single-segment path, so the request lands in
    GameSessionDetailView with game_id="sessions".
    """

    def test_the_sessions_route_no_longer_lists_anything(self):
        with muted():
            response = self.client.get("/api/game/sessions/")
        self.assertNotEqual(
            response.status_code,
            200,
            msg="api/game/sessions/ must not serve a session list",
        )

    def test_the_list_view_is_gone_from_the_module(self):
        import game.views_rest as views_rest

        self.assertFalse(
            hasattr(views_rest, "GameSessionListView"),
            msg="GameSessionListView should be deleted, not left importable",
        )


@override_settings(**TEST_BACKENDS)
class JoinSessionFormPasswordTests(TempMediaRootMixin, TestCase):
    """The template join view checks the password only for *started* games.

    game/views.py:148-159 nests the whole password block inside
    `if game_session.started_at:` — so every game anyone actually joins skips it.
    Lobby passwords currently do nothing.
    """

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Form join")
            self.game.game_password = "geheim"
            self.game.save()

    def post_join_form(self, password):
        with muted():
            return self.client.post(
                reverse("session-join"),
                {"game_id": self.game.game_id, "game_password": password},
            )

    def test_a_wrong_password_does_not_get_you_in(self):
        response = self.post_join_form("falsch")

        self.assertEqual(
            response.status_code,
            200,
            msg="a wrong password must re-render the form, not redirect onwards",
        )
        self.assertNotIn(
            "joined_game_ids",
            self.client.session.keys(),
            msg="a wrong password must not mark the session as joined",
        )

    def test_the_right_password_still_gets_you_in(self):
        response = self.post_join_form("geheim")

        self.assertEqual(response.status_code, 302)
        self.assertIn(self.game.game_id, self.client.session["joined_game_ids"])


@override_settings(**TEST_BACKENDS)
class LobbyHostRowTests(GameCookieMixin, TempMediaRootMixin, TestCase):
    """The lobby tells the host's own row apart. Roadmap.md 1.6.

    controlled_by_host used to mark it. From 1.6 on that flag means "played
    at the host machine", and the host row is found by its account.
    """

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Lobby")
            self.host_row = Player.objects.create(
                game=self.game, name="Host", user=self.host
            )
            self.seat = Player.objects.create(
                game=self.game, name="Ohne Handy", controlled_by_host=True
            )
            self.player = Player.objects.create(game=self.game, name="Mia")
        self.give_game_access(self.game.game_id)

    def players(self):
        payload = self.client.get(lobby_url(self.game.game_id)).json()
        return {p["name"]: p for p in payload["players"]}

    def test_the_host_row_is_flagged(self):
        players = self.players()

        self.assertTrue(players["Host"]["is_host"])
        self.assertFalse(players["Ohne Handy"]["is_host"])
        self.assertFalse(players["Mia"]["is_host"])

    def test_a_seat_at_the_host_machine_says_so(self):
        players = self.players()

        self.assertTrue(players["Ohne Handy"]["controlled_by_host"])
        self.assertFalse(players["Host"]["controlled_by_host"])
