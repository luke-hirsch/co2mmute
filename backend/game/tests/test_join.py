"""The pre-join surface: session lookup, joining, lobby state.

A new topic file. The convention is that a feature's tests go in the topic file
that owns the code, and nothing owned this one — until Roadmap.md 1.4 there was
no way to ask "does this game exist and can I join it?" without already holding a
cookie.

URLs are written out literally rather than reversed. These paths are the contract
the SPA hardcodes, so a rename should fail here rather than be papered over by
reverse().
"""

from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from co2mmute.utils import sign_value, unsign_value
from game.cache import invalidate_game_session
from game.models import GameSession, Player

from ._helpers import (
    TEST_BACKENDS,
    TempMediaRootMixin,
    create_game_map,
    create_game_session,
    create_host,
    english_in,
    muted,
    post_create,
    visible_text,
)


def lookup_url(game_id):
    return f"/api/game/lookup/{game_id}/"


def join_url(game_id):
    return f"/api/game/join/{game_id}/"


def lobby_url(game_id):
    return f"/api/game/{game_id}/lobby/"


create_url = "/api/game/"


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

    def test_the_bare_api_path_resolves_to_the_create_view(self):
        """`POST api/game/` is the one path with no segment after the prefix.

        Nothing can swallow it — `<str:game_id>/` needs a segment — but it is
        pinned with the rest because this file's whole point is that a route in
        the wrong place here answers plausibly instead of 404ing.
        """
        match = resolve(create_url)
        self.assertEqual(
            match.func.view_class.__name__, "GameSessionListCreateView"
        )

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

    def test_the_seat_code_resolves_to_its_view(self):
        """Roadmap.md 1.7. Two segments: undeclared, `seat/<code>/` lands in
        GetYourOwnGame as game "seat", player <code>."""
        match = resolve("/api/game/seat/K7P2QX/")

        self.assertEqual(match.func.view_class.__name__, "SeatCodeView")
        self.assertEqual(match.kwargs["code"], "K7P2QX")

    def test_the_seat_actions_resolve_to_their_views(self):
        code = resolve("/api/game/ABC123/player/P-01/code/")
        takeover = resolve("/api/game/ABC123/player/P-01/takeover/")

        self.assertEqual(code.func.view_class.__name__, "SeatCodeIssueView")
        self.assertEqual(takeover.func.view_class.__name__, "SeatTakeoverView")
        self.assertEqual(takeover.kwargs["player_id"], "P-01")

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
class OneJoinFunnelTests(TempMediaRootMixin, TestCase):
    """There is one way into a game: `/app/join/<ID>`. S22.

    There used to be two. Django's `/join/<id>/` asked for the id and the
    password, then `game/<id>/player/create/` for the name, with
    `request.session["joined_game_ids"]` carrying the permission between them;
    the SPA's `JoinForm` asks the lookup first and takes name and password in
    one `POST api/game/join/<id>/`. The QR code and the landing page pointed at
    the Django one, which had drifted: it never checked `max_players`, it took
    no lock, its `messages.error` calls went to pages that did not render them,
    and it logged the player's name.

    The SPA won because it is the one with the seat rule under a lock. The
    Django pages are **deleted, not redirected** — Lukas, 2026-09-30: no running
    game is worth keeping a door for, so an old QR image answers 404.
    """

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Ein Eingang")

    def test_the_django_join_is_gone(self):
        from django.urls import Resolver404

        for path in (
            "/join/",
            f"/join/{self.game.game_id}/",
            f"/game/{self.game.game_id}/player/create/",
            f"/game/{self.game.game_id}/player/P-01/update/",
        ):
            with self.subTest(path):
                with self.assertRaises(Resolver404):
                    resolve(path)
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_nothing_of_it_is_left_importable(self):
        """`game/forms.py` held the two join forms and nothing else, so the
        module itself is gone."""
        from importlib.util import find_spec

        import game.views as views

        for name in ("JoinSessionView", "PlayerCreateView", "PlayerUpdateView"):
            with self.subTest(name):
                self.assertFalse(hasattr(views, name))
        self.assertIsNone(find_spec("game.forms"))

    def test_its_templates_are_gone(self):
        from django.template import TemplateDoesNotExist
        from django.template.loader import get_template

        for name in ("game/join_session.html", "game/create_player.html", "game/update_player.html"):
            with self.subTest(name):
                with self.assertRaises(TemplateDoesNotExist):
                    get_template(name)

    def test_the_qr_code_points_into_the_spa(self):
        self.assertEqual(
            self.game.join_url, f"{settings.BASE_URL}/app/join/{self.game.game_id}"
        )

    def test_the_qr_image_carries_that_address(self):
        """What the phone camera reads, not just the property beside it."""
        from unittest import mock

        import qrcode

        with mock.patch.object(qrcode.QRCode, "add_data", autospec=True) as add_data:
            self.game.generate_qr_code()

        add_data.assert_called_once()
        self.assertEqual(add_data.call_args.args[1], self.game.join_url)

    def test_the_landing_page_sends_its_id_into_the_spa(self):
        html = self.client.get("/").content.decode()

        self.assertIn('action="/app/join"', html)
        self.assertNotRegex(html, r"(?<!/app)/join/", "a link into the deleted Django join")


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


# ---------------------------------------------------------------------------
# The funnel is German (2.6)
#
# The detector itself moved to `_helpers.py` in S17: it had been sitting in
# this file covering two pages while `/map/upload/` was English, and the maps
# tests could not reach it from here.
# ---------------------------------------------------------------------------

class GermanFunnelTests(TempMediaRootMixin, TestCase):
    """What the funnel around a game says, and what the create endpoint refuses
    with, is German.

    It started as the three Django pages in front of the SPA — `/join/`,
    `player/create/` and `/share/` — which made the join flow the one place a
    class met English. S13 and S22 deleted all three; the join screens are the
    SPA's now and `frontend/tests/design/german.test.ts` reads them. What is
    left here is what still comes off the server. The detector is the
    frontend's idea ported over: assert on the rendered text, because a label
    built in `Meta.labels` is invisible to a grep of the template.

    Nothing in here asserts an exact sentence. The test is "this page is not
    English", never "this page says what the guide said" — the wording stays
    free to improve, and only a string nobody translated goes red.
    """

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host, game_name="Testspiel")
        invalidate_game_session(self.game.game_id)

    def test_the_create_endpoint_refuses_in_german(self):
        """The create screen renders what comes back, so these are copy.

        They used to be English and it did not show: the form had its own
        German wording and this serializer only ever answered the lobby's
        PATCH, whose errors no screen displayed. S13 made them the sentence a
        host reads.
        """
        self.client.force_login(self.host)

        with muted():
            response = post_create(
                self.client,
                game_name="Zu klein",
                max_players=0,
                agent_per_player=0,
                max_rounds=0,
                max_CO2_level=0,
                people_per_agent=0,
            )

        self.assertEqual(response.status_code, 400)
        errors = response.json()
        self.assertTrue(errors)
        offenders = {
            field: messages
            for field, messages in errors.items()
            if english_in(" ".join(str(m) for m in messages))
        }
        self.assertEqual(offenders, {})

    def test_every_number_is_refused_in_german_at_both_ends(self):
        """The zeros above are `validate()`'s own German. What is past a
        column's range — `idle_end_days` stops at 365 on the model, the small
        integers at 32 767 — and what is not a number at all were refused by
        Django's and DRF's defaults, in English, and went straight onto the
        form. S21 found it by typing 99 999 into "Ende nach Tagen ohne Spiel".
        """
        self.client.force_login(self.host)
        numbers = (
            "max_players",
            "agent_per_player",
            "max_rounds",
            "max_CO2_level",
            "people_per_agent",
            "idle_end_days",
        )

        offenders = {}
        for field in numbers:
            for value in (10**12, "viele"):
                with muted():
                    response = post_create(self.client, **{field: value})
                self.assertEqual(response.status_code, 400, (field, value))
                messages = " ".join(response.json().get(field, []))
                self.assertTrue(messages, (field, value, response.json()))
                if english_in(messages):
                    offenders[(field, value)] = messages

        self.assertEqual(offenders, {})

    def test_a_missing_map_is_refused_in_german(self):
        self.client.force_login(self.host)

        with muted():
            response = post_create(self.client, game_map=None)

        self.assertEqual(response.status_code, 400)
        messages = response.json()["game_map"]
        self.assertEqual(english_in(" ".join(str(m) for m in messages)), [])

    def test_the_share_page_is_german(self):
        self.client.force_login(self.host)

        response = self.client.get(f"/game/{self.game.game_id}/share/")

        text = visible_text(response.content.decode())
        self.assertEqual(english_in(text), [], f"English on /share/: {text[:400]}")

    def test_the_profile_page_has_no_english_heading(self):
        self.client.force_login(self.host)

        response = self.client.get("/accounts/profile/")

        text = visible_text(response.content.decode())
        self.assertEqual(english_in(text), [], f"English on /accounts/profile/: {text[:400]}")
class MapWithNothingToVoteOnTests(GameCookieMixin, TempMediaRootMixin, TestCase):
    """A map with one version removes the vote, and nothing says so.

    `_advance_from_stats` is "discussion if there is a ballot, else the next
    round", and `vote_options()` offers the versions `compatible_versions`
    reaches from the active one. On a single-version map there are none — so
    the class goes stats → next round and never sees a discussion or a ballot,
    which is the mechanic the whole game is built around. The shipped map has
    one version, so nobody has ever seen it in a real game.

    The chain itself is fine; it was verified end to end through tie and
    stalemate on a seeded copy. What is missing is a warning at the two places
    a host can still do something about it: the map select, and the lobby.
    """

    def setUp(self):
        from maps.models import GameMap, MapVersion

        self.host = create_host()
        self.flat_map = GameMap.objects.create(
            name="Eine Fassung", x_dim=100, y_dim=100, scale=100.0
        )
        self.flat_base = MapVersion.objects.create(
            game_map=self.flat_map, name="Base", base_version=True
        )
        self.rich_map = GameMap.objects.create(
            name="Mit Varianten", x_dim=100, y_dim=100, scale=100.0
        )
        self.rich_base = MapVersion.objects.create(
            game_map=self.rich_map, name="Base", base_version=True
        )
        self.rich_change = MapVersion.objects.create(
            game_map=self.rich_map, name="Busspur Hauptstraße"
        )
        self.rich_base.compatible_versions.add(self.rich_change)

    def _lobby(self, game_map, map_updates=True, **overrides):
        # map_updates is passed explicitly in every case: the MODEL default is
        # False while the create form's initial is True, so a game made any
        # other way than through /game/create/ has no vote at all whatever its
        # map offers. That trap has its own test below.
        with muted():
            game = create_game_session(
                self.host,
                game_name="Abstimmung",
                game_map=game_map,
                map_updates=map_updates,
                **overrides,
            )
        self.give_game_access(game.game_id)
        return self.client.get(lobby_url(game.game_id)).json()

    def test_the_lobby_names_the_map(self):
        """Finding 13: the host lobby never said which map the game runs on —
        which matters now that the map decides whether there is a vote."""
        payload = self._lobby(self.rich_map)

        self.assertEqual(payload["map_name"], "Mit Varianten")

    def test_the_lobby_says_a_one_version_map_has_no_ballot(self):
        payload = self._lobby(self.flat_map)

        self.assertIs(payload["map_changes_available"], False)

    def test_the_lobby_says_a_versioned_map_has_one(self):
        payload = self._lobby(self.rich_map)

        self.assertIs(payload["map_changes_available"], True)

    def test_a_game_with_map_updates_switched_off_has_no_ballot_either(self):
        """Same outcome, different cause, and the host set this one themselves."""
        payload = self._lobby(self.rich_map, map_updates=False)

        self.assertIs(payload["map_changes_available"], False)

    def test_the_model_default_leaves_the_vote_switched_off(self):
        """Not the form's default — the model's. A game created through the
        REST API without naming `map_updates` never reaches a ballot, whatever
        its map offers."""
        with muted():
            game = create_game_session(
                self.host, game_name="Standard", game_map=self.rich_map
            )
        self.give_game_access(game.game_id)

        payload = self.client.get(lobby_url(game.game_id)).json()

        self.assertIs(payload["map_changes_available"], False)

    def test_a_game_without_a_map_has_no_ballot_and_no_name(self):
        payload = self._lobby(None)

        self.assertIsNone(payload["map_name"])
        self.assertIs(payload["map_changes_available"], False)

    def test_the_map_is_read_before_the_game_starts(self):
        """`active_map_version` is only set when the game starts, so the lobby
        has to fall back to the base version — otherwise the warning would
        only appear once it is too late to change the map."""
        payload = self._lobby(self.rich_map)

        self.assertIsNone(
            GameSession.objects.get(game_id=payload["game_id"]).active_map_version
        )
        self.assertIs(payload["map_changes_available"], True)

    def test_the_map_list_marks_a_map_with_nothing_to_vote_on(self):
        """What the Django form put in the option label, the API now states.

        `MapChoiceField` appended "— keine Kartenänderungen" to the label; the
        React select reads this boolean and says the same thing. A flag beats a
        decorated label: the screen can put the sentence where it belongs
        instead of inside the option text.
        """
        self.client.force_login(self.host)

        response = self.client.get("/api/maps/")

        self.assertEqual(response.status_code, 200)
        by_id = {row["id"]: row for row in response.json()}
        self.assertIs(by_id[self.flat_map.pk]["offers_map_changes"], False)

    def test_the_map_list_leaves_a_versioned_map_alone(self):
        self.client.force_login(self.host)

        response = self.client.get("/api/maps/")

        self.assertEqual(response.status_code, 200)
        by_id = {row["id"]: row for row in response.json()}
        self.assertIs(by_id[self.rich_map.pk]["offers_map_changes"], True)


@override_settings(**TEST_BACKENDS)
class CreateGameEndpointTests(TempMediaRootMixin, TestCase):
    """`POST api/game/` — what the Django `CreateView` used to do. S13.

    The screen moved to React because the two calibrated numbers have to follow
    the class size as the host types it, and a server-rendered form derives
    them once per GET. What moved with it is everything the old `form_valid`
    did besides saving the row: the host's own `Player`, both signed cookies,
    and the cache entry the permissions and the consumers read.

    The cookies matter more than they look. The host is a Django user with a
    session *and* a player in their own game, and `IsPlayerInGame` /
    `HasGameAccess` ask for the cookies, not the session — so a create that
    forgets them leaves the host holding a game they cannot act in.
    """

    def setUp(self):
        self.host = create_host(first_name="Sebastian", last_name="Werblinski")
        self.game_map = create_game_map()

    def _create(self, **overrides):
        overrides.setdefault("game_map", self.game_map.pk)
        with muted():
            return post_create(self.client, **overrides)

    def test_an_anonymous_visitor_is_refused(self):
        response = self._create()

        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(GameSession.objects.exists())

    def test_the_host_creates_a_game(self):
        self.client.force_login(self.host)

        response = self._create(game_name="Klasse 8b")

        self.assertEqual(response.status_code, 201, msg=response.content)
        game = GameSession.objects.get(game_name="Klasse 8b")
        self.assertEqual(game.game_host, self.host)
        self.assertEqual(response.json()["game_id"], game.game_id)

    def test_the_body_cannot_name_a_different_host(self):
        """`game_host` is read-only, so a POST cannot hand somebody else a game."""
        other = create_host(username="fremd")
        self.client.force_login(self.host)

        response = self._create(game_name="Nicht deins", game_host=other.pk)

        self.assertEqual(response.status_code, 201, msg=response.content)
        self.assertEqual(
            GameSession.objects.get(game_name="Nicht deins").game_host, self.host
        )

    def test_it_seats_the_host(self):
        """Found by account, never by `controlled_by_host` — that flag means
        "played at the host machine", which this row is not."""
        self.client.force_login(self.host)

        self._create(game_name="Mit Host")

        game = GameSession.objects.get(game_name="Mit Host")
        host_row = Player.objects.filter(game=game).host_rows().get()  # type: ignore
        self.assertEqual(host_row.user, self.host)
        self.assertFalse(host_row.controlled_by_host)
        self.assertEqual(host_row.name, "Sebastian Werblinski (Host)")

    def test_a_nameless_account_is_just_Host(self):
        nameless = create_host(username="ohne")
        self.client.force_login(nameless)

        self._create(game_name="Ohne Namen")

        game = GameSession.objects.get(game_name="Ohne Namen")
        self.assertEqual(
            Player.objects.filter(game=game).host_rows().get().name,  # type: ignore
            "Host",
        )

    def test_it_hands_back_both_cookies(self):
        self.client.force_login(self.host)

        response = self._create(game_name="Mit Keksen")

        game_id = response.json()["game_id"]
        self.assertIn(f"{settings.COOKIE_GAME_PREFIX}{game_id}", response.cookies)
        self.assertIn(f"{settings.COOKIE_PLAYER_PREFIX}{game_id}", response.cookies)

    def test_the_player_cookie_names_the_host_row(self):
        """Both cookie values are "<game_id>:<x>"; the player one carries the
        `player_id`, and `ws_auth` refuses one whose game id does not match."""
        self.client.force_login(self.host)

        response = self._create(game_name="Kekse pruefen")

        game_id = response.json()["game_id"]
        raw = response.cookies[f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"].value
        value = unsign_value(raw, settings.COOKIE_PLAYER_SALT)
        game = GameSession.objects.get(game_id=game_id)
        host_row = Player.objects.filter(game=game).host_rows().get()  # type: ignore
        self.assertEqual(value, f"{game_id}:{host_row.player_id}")

    def test_the_new_game_is_cached(self):
        """`get_cached_game_session` is what the permissions and both consumers
        read, so a create that skips it makes the first request a miss."""
        from game.cache import get_cached_game_session

        self.client.force_login(self.host)

        response = self._create(game_name="Im Cache")

        game_id = response.json()["game_id"]
        self.assertIsNotNone(get_cached_game_session(game_id))

    def test_it_refuses_more_agents_than_seats(self):
        self.client.force_login(self.host)

        response = self._create(
            game_name="Zu viele", max_players=2, agent_per_player=3
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("agent_per_player", response.json())
        self.assertFalse(GameSession.objects.filter(game_name="Zu viele").exists())

    def test_a_refused_body_seats_nobody(self):
        """The row, the seat and the cookies are one step or none."""
        self.client.force_login(self.host)

        self._create(game_name="Kaputt", max_rounds=0)

        self.assertFalse(GameSession.objects.filter(game_name="Kaputt").exists())
        self.assertFalse(Player.objects.exists())


@override_settings(**TEST_BACKENDS)
class HostGameListTests(TempMediaRootMixin, TestCase):
    """`GET api/game/` — the host's own games, for `/app/host`. S13.

    It replaces the `game_sessions` context the profile template got. Two
    things it adds and the template did not have: the counts the delete dialog
    needs, and a scope that is asserted rather than assumed.
    """

    def setUp(self):
        self.host = create_host()
        self.other = create_host(username="kollegin")
        with muted():
            self.mine = create_game_session(self.host, game_name="Meins")
            self.theirs = create_game_session(self.other, game_name="Deins")
        self.client.force_login(self.host)

    def test_an_anonymous_visitor_is_refused(self):
        self.client.logout()

        response = self.client.get("/api/game/")

        self.assertIn(response.status_code, (401, 403))

    def test_it_lists_only_your_own_games(self):
        response = self.client.get("/api/game/")

        self.assertEqual(response.status_code, 200)
        names = [row["game_name"] for row in response.json()]
        self.assertEqual(names, ["Meins"])

    def test_it_says_nothing_about_the_password(self):
        """This is a list on a page, not the row a game screen plays from."""
        response = self.client.get("/api/game/")

        self.assertNotIn("game_password", response.json()[0])

    def test_newest_first(self):
        with muted():
            create_game_session(self.host, game_name="Frisch")

        response = self.client.get("/api/game/")

        self.assertEqual(
            [row["game_name"] for row in response.json()], ["Frisch", "Meins"]
        )

    def test_it_counts_the_rounds(self):
        from game.models import GameRound

        with muted():
            GameRound.objects.create(game=self.mine, round_number=1)
            GameRound.objects.create(game=self.mine, round_number=2)

        response = self.client.get("/api/game/")

        self.assertEqual(response.json()[0]["round_count"], 2)

    def test_it_counts_the_seats_without_the_host_row(self):
        """`user` is NULL for every student, so a plain `!=` against the host
        counts nobody at all. That is the bug this test exists for."""
        Player.objects.create(game=self.mine, user=self.host, name="Host")
        Player.objects.create(game=self.mine, name="Mia")
        Player.objects.create(game=self.mine, name="Jonas")

        response = self.client.get("/api/game/")

        self.assertEqual(response.json()[0]["player_count"], 2)

    def test_a_game_with_nothing_on_it_counts_zero(self):
        response = self.client.get("/api/game/")

        row = response.json()[0]
        self.assertEqual(row["round_count"], 0)
        self.assertEqual(row["player_count"], 0)

    def test_it_says_whether_a_game_is_running(self):
        """The delete dialog has to refuse one, and the list has to say why."""
        from django.utils import timezone

        GameSession.objects.filter(pk=self.mine.pk).update(
            is_active=True, started_at=timezone.now()
        )

        row = self.client.get("/api/game/").json()[0]

        self.assertIs(row["is_active"], True)
        self.assertIsNotNone(row["started_at"])
        self.assertIsNone(row["ended_at"])


class CreateFormRedirectTests(TempMediaRootMixin, TestCase):
    """`/game/create/` is a doorway now, and it has to stay one.

    Everything points at it: the landing page twice, the footer, the profile
    page, the end-of-game screen and six e2e specs. The redirect is what keeps
    all of them working while there is only one create screen.
    """

    def setUp(self):
        self.host = create_host()

    def test_the_old_url_sends_a_host_into_the_spa(self):
        self.client.force_login(self.host)

        response = self.client.get("/game/create/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/app/game/create")

    def test_an_anonymous_visitor_goes_to_the_login_first(self):
        """Not into the SPA, which would only bounce them back a tick later."""
        response = self.client.get("/game/create/")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/accounts/login/"))

    def test_the_form_is_gone(self):
        """A second create form is the two-sources-of-truth bug this project
        keeps having. The Django one is deleted, not left beside the React one.

        Since S22 the module that held it is gone too — its last two forms were
        the Django join's."""
        from importlib.util import find_spec

        self.assertIsNone(find_spec("game.forms"))


class CalibratedCreateFormTests(TempMediaRootMixin, TestCase):
    """S2: the two numbers a game is played against follow the class size.

    The scale is not a taste. Measured on Berlin_Mitte-West, a round is the
    same round for a full class and for a half-empty one only if the district's
    commuter population is held constant while the seats vary: at 6 400
    commuters, 16 / 8 / 4 / 2 seats give a mean car delay of 11.3 / 11.0 / 11.4
    / 11.5 min and car CO2 within 3 %. Hold `people_per_agent` at a number
    instead and a half-full class sees 0.4 min of delay against 11.3, which is
    a different game depending on who turned up.

    The budget is kg per person per round since F8 step 2b, the same on every
    map: the people on the map times the kg times the rounds.
    """

    def setUp(self):
        self.host = create_host()

    def test_the_shipped_defaults_are_the_calibrated_pair(self):
        """The class size the create screen opens on, and what it derives.

        These were assertions about a Django form's `initial` until S13. The
        screen is React now and `frontend/tests/lib/create-game.test.ts` pins
        what it offers; what stays here is the arithmetic underneath, which is
        the half that has to agree with the simulation.
        """
        from game.calibration import (
            CO2_KG_PER_PERSON_NORMAL,
            DEFAULT_AGENT_PER_PLAYER,
            DEFAULT_MAX_PLAYERS,
            DEFAULT_MAX_ROUNDS,
            co2_budget_kg,
            people_per_agent,
        )

        self.assertEqual(DEFAULT_MAX_PLAYERS, 16)
        self.assertEqual(DEFAULT_AGENT_PER_PLAYER, 4)
        self.assertEqual(DEFAULT_MAX_ROUNDS, 6)
        self.assertEqual(CO2_KG_PER_PERSON_NORMAL, Decimal("2.4"))
        per_gruppe = people_per_agent(
            max_players=DEFAULT_MAX_PLAYERS,
            agent_per_player=DEFAULT_AGENT_PER_PLAYER,
        )
        self.assertEqual(per_gruppe, 106)
        # 2.4 kg × 6 800 commuters × 6 rounds.
        self.assertEqual(co2_budget_kg(max_rounds=DEFAULT_MAX_ROUNDS), 97_920)

    def test_people_per_agent_follows_the_class_size(self):
        """Half the seats, twice the people behind each Gruppe."""
        from game.calibration import people_per_agent

        # 6 800 / 32 is 212.5, and Python's round() goes to even.
        for seats, expected in ((16, 106), (8, 212), (4, 425), (2, 850)):
            with self.subTest(seats=seats):
                self.assertEqual(
                    people_per_agent(max_players=seats, agent_per_player=4),
                    expected,
                )

    def test_people_per_agent_follows_the_agents_per_player_too(self):
        """It is agents that carry people, not players."""
        from game.calibration import people_per_agent

        self.assertEqual(
            people_per_agent(max_players=16, agent_per_player=2), 212
        )

    def test_the_budget_is_kilograms_times_commuters_times_rounds(self):
        """Per person and per round, so the pressure is spread over the whole
        game and a map with more commuters gets a bigger budget for them.

        It carries no Gruppe term on purpose: the district's population is
        constant, so a round costs what it costs however many students play —
        and the timetable runs whether anybody rides, so a host who types over
        the scale must not shrink the budget under it.
        """
        from game.calibration import co2_budget_kg

        cases = (
            (dict(max_rounds=6), 97_920),
            (dict(max_rounds=3), 48_960),
            (dict(max_rounds=10), 163_200),
            (dict(max_rounds=6, kg_per_person=Decimal("1.0")), 40_800),
            (dict(max_rounds=6, kg_per_person=Decimal("6.0")), 244_800),
        )
        for arguments, expected in cases:
            with self.subTest(**arguments):
                self.assertEqual(co2_budget_kg(**arguments), expected)

    def test_an_empty_field_counts_as_one_round(self):
        """The fields are strings while they are being retyped."""
        from game.calibration import co2_budget_kg

        self.assertEqual(co2_budget_kg(max_rounds=0), 16_320)

    def test_the_host_keeps_whatever_they_send(self):
        """Derived is an offer, not a rule. The host stays in charge.

        The screen derives the pair and writes it into the two fields; if the
        host types over them, the endpoint takes what it is given — there is no
        server-side recomputation that would quietly overrule them.
        """
        self.client.force_login(self.host)

        with muted():
            response = post_create(
                self.client,
                game_name="Eigene Zahlen",
                people_per_agent=1000,
                max_CO2_level=500,
            )

        self.assertEqual(response.status_code, 201, msg=response.content)
        game = GameSession.objects.get(game_name="Eigene Zahlen")
        self.assertEqual(game.people_per_agent, 1000)
        self.assertEqual(game.max_CO2_level, 500)

    def test_the_budget_is_beatable_and_losable(self):
        """What the normal kg is FOR, in one assertion.

        Measured on the shipped map at 6 800 commuters, there and back
        (`calibrate_map`, six seeds, Postgres): a round where everybody drives
        is 4.17 kg a head, a round nobody drives 1.53 kg, the timetables' own
        floor. Normal has to sit between them or it is not a budget. A class
        that goes 100/75/50/50/25/25 % spends 16.09 kg a head over six rounds
        against 14.4 — over, as it has been since every line runs until
        everybody is home (docs/kalibrierung.md §11, §13).
        """
        from game.calibration import CO2_KG_PER_PERSON_NORMAL

        self.assertLess(CO2_KG_PER_PERSON_NORMAL, Decimal("4.17"))
        self.assertGreater(CO2_KG_PER_PERSON_NORMAL, Decimal("1.53"))

    def test_the_game_records_the_kg_it_was_played_at(self):
        """The dial is what the host chose; `max_CO2_level` is what follows
        from it. A game's research data has to say which was chosen."""
        self.client.force_login(self.host)

        with muted():
            response = post_create(
                self.client, game_name="Normal", co2_kg_per_person="2.4"
            )

        self.assertEqual(response.status_code, 201, msg=response.content)
        game = GameSession.objects.get(game_name="Normal")
        self.assertEqual(game.co2_kg_per_person, Decimal("2.4"))

    def test_a_game_made_without_the_dial_says_so(self):
        """Every game before the dial, and one made over the API without it,
        was played against a total nobody stated per head."""
        self.client.force_login(self.host)

        with muted():
            response = post_create(self.client, game_name="Ohne Regler")

        self.assertEqual(response.status_code, 201, msg=response.content)
        self.assertIsNone(
            GameSession.objects.get(game_name="Ohne Regler").co2_kg_per_person
        )

    def test_the_dial_takes_only_its_own_steps(self):
        """Refused in German, beside the field: the screen renders it."""
        self.client.force_login(self.host)

        for value in ("2.5", "0.8", "6.2", "2.45", "zwei", "-2.4"):
            with self.subTest(value=value):
                with muted():
                    response = post_create(
                        self.client, game_name="Falsch", co2_kg_per_person=value
                    )
                self.assertEqual(response.status_code, 400)
                message = " ".join(response.json()["co2_kg_per_person"])
                self.assertNotRegex(message, r"[Ee]nsure|valid|digits|number")
                self.assertTrue(message)
        self.assertFalse(GameSession.objects.filter(game_name="Falsch").exists())

    def test_the_map_the_screen_derives_from_carries_the_pair(self):
        """What the host sees is derived in the browser, from these two fields.

        The derivation moved to `frontend/src/lib/calibration.ts` with S13 —
        it has to follow the class size as the host types, which a
        server-rendered form could never do. Its inputs still come from here,
        over `GET api/maps/`, so this is the half the backend still owns: the
        two numbers reach the client at all.
        """
        from maps.models import GameMap

        game_map = GameMap.objects.create(name="Vorschlagskarte")
        self.client.force_login(self.host)

        response = self.client.get("/api/maps/")

        self.assertEqual(response.status_code, 200)
        row = {r["id"]: r for r in response.json()}[game_map.pk]
        self.assertEqual(row["district_commuters"], 6_800)
        self.assertNotIn("co2_budget_kg_per_round", row)


class MapCarriedCalibrationTests(TempMediaRootMixin, TestCase):
    """The commuter count belongs to the map, not to a constant.

    It is a property of the graph: the car demand its corridors carry at the
    real city's rush hour. Another city is another count. The budget used to
    be one too, until F8 step 2b: it is kg per person now, the same on every
    map, so a map with long commutes or a thin timetable is harder by itself.
    """

    def setUp(self):
        self.host = create_host()

    def _map(self, **overrides):
        from maps.models import GameMap

        fields = {
            "name": "Testkarte",
            "x_dim": 13,
            "y_dim": 10,
            "scale": 1000.0,
        }
        fields.update(overrides)
        return GameMap.objects.create(**fields)

    def test_a_map_carries_its_own_count(self):
        from maps.models import GameMap

        game_map = self._map()

        self.assertEqual(
            game_map.district_commuters,
            GameMap._meta.get_field("district_commuters").default,
        )

    def test_the_shipped_default_is_the_measured_berlin_figure(self):
        """6 800: an all-car morning on Berlin Mitte-West at TomTom's 19 km/h."""
        from maps.models import GameMap

        self.assertEqual(
            GameMap._meta.get_field("district_commuters").default, 6_800
        )

    def test_no_map_carries_a_budget(self):
        """A number that is the same on every map is not a map's."""
        from django.core.exceptions import FieldDoesNotExist
        from maps.models import GameMap

        with self.assertRaises(FieldDoesNotExist):
            GameMap._meta.get_field("co2_budget_kg_per_round")

    def test_the_scale_comes_off_the_map_that_was_chosen(self):
        """A quieter map means fewer people behind each Gruppe."""
        from game.calibration import people_per_agent

        quiet = self._map(name="Kleinstadt", district_commuters=1_600)

        self.assertEqual(
            people_per_agent(max_players=16, agent_per_player=4, game_map=quiet),
            25,
        )

    def test_a_quieter_map_gets_a_smaller_budget_for_the_same_kg(self):
        """Through its commuters, and only through them: the kg is the same
        on every map."""
        from game.calibration import co2_budget_kg

        quiet = self._map(name="Kleinstadt", district_commuters=1_600)

        self.assertEqual(co2_budget_kg(max_rounds=6, game_map=quiet), 23_040)

    def test_without_a_map_the_field_default_stands_in(self):
        """The create form renders before a map is chosen, and must offer
        something coherent rather than nothing."""
        from game.calibration import co2_budget_kg, people_per_agent

        self.assertEqual(
            people_per_agent(max_players=16, agent_per_player=4), 106
        )
        self.assertEqual(co2_budget_kg(max_rounds=6), 97_920)

    def test_a_tie_rounds_down(self):
        """800 over 64 Gruppen is 12.5, and Python's round() goes to even.

        Pinned rather than rounded up on purpose: under the corridors' capacity
        is the safe side of a tie. `frontend/src/lib/calibration.ts` mirrors
        this rule, because the offer is now computed in the browser — its own
        test uses these same numbers.
        """
        from game.calibration import people_per_agent

        quiet = self._map(name="Kleinstadt", district_commuters=800)

        self.assertEqual(
            people_per_agent(max_players=16, agent_per_player=4, game_map=quiet),
            12,
        )

    def test_the_count_travels_to_the_client_per_map(self):
        """The screen derives from whichever map is selected, so the count
        has to be on every row of the list, not only on the default."""
        self.client.force_login(self.host)
        quiet = self._map(name="Kleinstadt", district_commuters=1_600)

        response = self.client.get("/api/maps/")

        self.assertEqual(response.status_code, 200)
        row = {r["id"]: r for r in response.json()}[quiet.pk]
        self.assertEqual(row["district_commuters"], 1_600)


class MapCalibrationRoundTripTests(TempMediaRootMixin, TestCase):
    """The count has to survive an export and a re-import.

    The JSON export is the only way a map moves between boxes, so a field the
    export drops is a field that does not exist off this machine. Every file
    written before F8 step 2b also carries `co2_budget_kg_per_round`; it
    still imports, and the budget is left behind.
    """

    def setUp(self):
        self.host = create_host()
        self.host.is_staff = True
        self.host.save(update_fields=["is_staff"])

    def test_the_export_carries_the_count(self):
        from maps.models import GameMap, MapVersion

        game_map = GameMap.objects.create(
            name="Exportkarte",
            x_dim=13,
            y_dim=10,
            scale=1000.0,
            district_commuters=3_200,
        )
        MapVersion.objects.create(
            game_map=game_map, name="Base", base_version=True
        )
        self.client.force_login(self.host)

        response = self.client.get(f"/api/maps/{game_map.pk}/export/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["map"]["district_commuters"], 3_200)
        self.assertNotIn("co2_budget_kg_per_round", payload["map"])

    def test_an_import_reads_the_count_back_and_leaves_an_old_budget(self):
        import json

        from django.core.files.uploadedfile import SimpleUploadedFile
        from maps.models import GameMap

        graph = {
            "scale": 1000.0,
            "map": {
                "name": "Reimport",
                "x_dim": 13,
                "y_dim": 10,
                "district_commuters": 3_200,
                "co2_budget_kg_per_round": 5_000,
            },
            "nodes": [
                {"id": "a", "name": "A", "x": 0, "y": 0, "types": []},
                {"id": "b", "name": "B", "x": 1, "y": 0, "types": []},
            ],
            "edges": [
                {"start_node": "a", "end_node": "b", "type": "street"},
            ],
            "bus_lines": [],
            "train_lines": [],
        }
        upload = SimpleUploadedFile(
            "reimport.json",
            json.dumps(graph).encode(),
            content_type="application/json",
        )
        self.client.force_login(self.host)

        response = self.client.post(
            "/api/maps/import/",
            {
                "map_name": "Reimport",
                "description": "",
                "max_players": 16,
                "json_file": upload,
            },
        )

        # 201 with the new map, 400 with what the file got wrong.
        self.assertEqual(response.status_code, 201)
        game_map = GameMap.objects.get(name="Reimport")
        self.assertEqual(game_map.district_commuters, 3_200)
        self.assertFalse(hasattr(game_map, "co2_budget_kg_per_round"))

    def test_an_old_export_without_the_count_still_imports(self):
        """Every map exported before today has no such keys."""
        import json

        from django.core.files.uploadedfile import SimpleUploadedFile
        from maps.models import GameMap

        graph = {
            "scale": 1000.0,
            "map": {"name": "Alt", "x_dim": 13, "y_dim": 10},
            "nodes": [
                {"id": "a", "name": "A", "x": 0, "y": 0, "types": []},
                {"id": "b", "name": "B", "x": 1, "y": 0, "types": []},
            ],
            "edges": [
                {"start_node": "a", "end_node": "b", "type": "street"},
            ],
            "bus_lines": [],
            "train_lines": [],
        }
        upload = SimpleUploadedFile(
            "alt.json", json.dumps(graph).encode(), content_type="application/json"
        )
        self.client.force_login(self.host)

        response = self.client.post(
            "/api/maps/import/",
            {
                "map_name": "Alt",
                "description": "",
                "max_players": 16,
                "json_file": upload,
            },
        )

        self.assertEqual(response.status_code, 201)
        game_map = GameMap.objects.get(name="Alt")
        self.assertEqual(game_map.district_commuters, 6_800)


class MapSaysWhetherItsCountWasMeasuredTests(TempMediaRootMixin, TestCase):
    """S21: a map says whether its commuter count was measured on it.

    Every map starts at Berlin Mitte-West's 6 800 commuters, because that is
    the field default. On a smaller map it is too high, and the create form
    used to offer it without a word. Comparing a map's count against the
    default cannot tell the two cases apart — the one map where 6 800 *is*
    measured carries exactly that — so the map says it: `calibrated`, false
    until somebody who measured it says otherwise. (It named a pair until F8
    step 2b took the budget off the map.)

    It travels in the file, because the file is how a map moves between boxes.
    The export has written the count on every map since S2, measured or not,
    so a file stating it is not a file stating it was measured; only the flag
    is.
    """

    def setUp(self):
        self.host = create_host()
        self.host.is_staff = True
        self.host.save(update_fields=["is_staff"])

    def _import(self, map_block):
        import json

        from django.core.files.uploadedfile import SimpleUploadedFile
        from maps.models import GameMap

        graph = {
            "scale": 1000.0,
            "map": {"name": "Kiez", "x_dim": 13, "y_dim": 10, **map_block},
            "nodes": [
                {"id": "a", "name": "A", "x": 0, "y": 0, "types": []},
                {"id": "b", "name": "B", "x": 1, "y": 0, "types": []},
            ],
            "edges": [
                {"start_node": "a", "end_node": "b", "type": "street"},
            ],
            "bus_lines": [],
            "train_lines": [],
        }
        upload = SimpleUploadedFile(
            "kiez.json", json.dumps(graph).encode(), content_type="application/json"
        )
        self.client.force_login(self.host)
        with muted():
            response = self.client.post(
                "/api/maps/import/",
                {
                    "map_name": "Kiez",
                    "description": "",
                    "max_players": 16,
                    "json_file": upload,
                },
            )
        self.assertEqual(response.status_code, 201, response.content)
        return GameMap.objects.get(pk=response.json()["id"])

    def test_a_new_map_is_not_measured(self):
        from maps.models import GameMap

        game_map = GameMap.objects.create(name="Kiez")

        self.assertFalse(game_map.calibrated)

    def test_the_flag_reaches_the_create_screen(self):
        """The warning is drawn in the browser, from the map list."""
        from maps.models import GameMap

        measured = GameMap.objects.create(name="Gemessen", calibrated=True)
        guessed = GameMap.objects.create(name="Geschätzt")
        self.client.force_login(self.host)

        response = self.client.get("/api/maps/")

        self.assertEqual(response.status_code, 200)
        rows = {r["id"]: r for r in response.json()}
        self.assertIs(rows[measured.pk]["calibrated"], True)
        self.assertIs(rows[guessed.pk]["calibrated"], False)

    def test_the_export_carries_the_flag(self):
        from maps.models import GameMap, MapVersion

        game_map = GameMap.objects.create(name="Gemessen", calibrated=True)
        MapVersion.objects.create(game_map=game_map, name="Base", base_version=True)
        self.client.force_login(self.host)

        response = self.client.get(f"/api/maps/{game_map.pk}/export/")

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["map"]["calibrated"], True)

    def test_an_import_reads_the_flag_back(self):
        game_map = self._import({"district_commuters": 1_600, "calibrated": True})

        self.assertTrue(game_map.calibrated)
        self.assertEqual(game_map.district_commuters, 1_600)

    def test_a_file_from_before_the_dial_is_still_measured(self):
        """Its budget is left behind; the count it measured is still its own."""
        game_map = self._import(
            {
                "district_commuters": 6_400,
                "co2_budget_kg_per_round": 16_000,
                "calibrated": True,
            }
        )

        self.assertTrue(game_map.calibrated)
        self.assertEqual(game_map.district_commuters, 6_400)

    def test_a_file_stating_the_count_without_the_flag_is_not_measured(self):
        """The case the flag exists for: a map exported after S2 carries
        Berlin's default as plainly as Berlin itself does."""
        game_map = self._import({"district_commuters": 6_800})

        self.assertFalse(game_map.calibrated)

    def test_the_flag_without_the_count_is_not_honoured(self):
        """"Measured" names a number. A file that says so and gives none would
        mark the field default as this map's measurement — a budget beside it
        is no count."""
        with muted():
            game_map = self._import(
                {"calibrated": True, "co2_budget_kg_per_round": 2_000}
            )

        self.assertFalse(game_map.calibrated)
        self.assertEqual(game_map.district_commuters, 6_800)

    def test_only_true_is_true(self):
        """A hand-edited file saying "ja" or 1 is not a statement anybody
        should be held to."""
        game_map = self._import({"district_commuters": 1_600, "calibrated": "ja"})

        self.assertFalse(game_map.calibrated)
