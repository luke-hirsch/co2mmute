"""Player identity: the two signed cookies, and the one resolver behind them.

Players have no account and never will (Roadmap.md, "grundsatz spielerdaten"). All
the identity there is lives in `game_access_<game_id>` and `player_<game_id>`, so
this file is where the hardening in Roadmap.md 1.2 is pinned down.
"""

import time
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import signing
from django.http import HttpResponse
from django.test import (
    RequestFactory,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.utils import timezone

from co2mmute.utils import set_game_access_cookie, set_player_cookie, sign_value
from game.models import GameSession, Player
from game.ws_auth import resolve_player

from ._helpers import TEST_BACKENDS, TempMediaRootMixin, muted


def signed_game_cookie(game_id, token="test-token"):
    return sign_value(f"{game_id}:{token}", settings.COOKIE_GAME_SALT)


def signed_player_cookie(game_id, player_id):
    """The post-1.2 format: the player id bound to its game inside the signature.

    Before 1.2 this signs the bare player_id, so only the cookie *name* carries
    the game — rename it in the browser and the signature still verifies.
    """
    return sign_value(f"{game_id}:{player_id}", settings.COOKIE_PLAYER_SALT)


def scope_with_cookies(**cookies):
    header = "; ".join(f"{name}={value}" for name, value in cookies.items())
    return {"headers": [(b"cookie", header.encode())]}


def request_with_session():
    """A request with a real session, like the join views have.

    Before 1.2 both cookie helpers stashed a value in request.session, so a bare
    RequestFactory request was not enough. After 1.2 they must not touch it —
    the session is still attached so a test can prove that.
    """
    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: HttpResponse())(request)
    request.session.save()
    return request


@override_settings(**TEST_BACKENDS)
class WsAuthTests(TempMediaRootMixin, TransactionTestCase):
    """The two cases that have been failing since before phase 0.

    resolve_player calls channels.auth.get_user unconditionally, and get_user
    needs scope["session"], which a hand-built scope does not have:
    `ValueError: Cannot find session in scope`. 1.2 guards the call.

    TransactionTestCase, not TestCase — for every class here that awaits
    resolve_player. channels' database_sync_to_async runs
    close_old_connections() first, and inside TestCase's wrapping transaction
    that really closes the connection: the next test's setUp then dies with
    `the connection is closed`.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="host", password="pass")

        with muted():
            self.game = GameSession.objects.create(
                game_host=self.user,
                game_name="Test",
                max_players=4,
                max_rounds=4,
                max_CO2_level=100,
                agent_per_player=1,
            )
            self.player = Player.objects.create(game=self.game, name="Tester")

    def _make_scope_with_cookies(self, game_id, player_id):
        return scope_with_cookies(
            **{
                f"{settings.COOKIE_PLAYER_PREFIX}{game_id}": signed_player_cookie(
                    game_id, player_id
                ),
                f"{settings.COOKIE_GAME_PREFIX}{game_id}": signed_game_cookie(game_id),
            }
        )

    def test_resolve_player_success(self):
        scope = self._make_scope_with_cookies(self.game.game_id, self.player.player_id)
        player, close_code, reason, is_host = async_to_sync(resolve_player)(
            scope, self.game.game_id
        )
        self.assertIsNone(close_code)
        self.assertIsNone(reason)
        self.assertIsNotNone(player)
        self.assertFalse(is_host)  # Regular player, not host
        if player:
            self.assertEqual(player.player_id, self.player.player_id)

    def test_resolve_player_missing_cookie(self):
        scope = {"headers": []}
        player, close_code, reason, is_host = async_to_sync(resolve_player)(
            scope, self.game.game_id
        )
        self.assertIsNone(player)
        self.assertEqual(close_code, 4401)


@override_settings(**TEST_BACKENDS)
class SignedCookieTests(TempMediaRootMixin, TestCase):
    """What actually goes inside the two cookies, and for how long."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="host", password="pass")
        with muted():
            self.game = GameSession.objects.create(
                game_host=self.user,
                game_name="Cookies",
                max_players=4,
                max_rounds=4,
                max_CO2_level=100,
                agent_per_player=1,
            )
            self.player = Player.objects.create(game=self.game, name="Mia")

    def test_the_player_cookie_carries_its_game_id(self):
        request = request_with_session()
        response = set_player_cookie(
            request, HttpResponse(), self.game.game_id, self.player.player_id
        )

        raw = response.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ].value
        payload = signing.TimestampSigner(salt=settings.COOKIE_PLAYER_SALT).unsign(raw)

        self.assertEqual(payload, f"{self.game.game_id}:{self.player.player_id}")

    def test_the_game_cookie_still_carries_its_game_id(self):
        request = request_with_session()
        response = set_game_access_cookie(request, HttpResponse(), self.game.game_id)

        raw = response.cookies[
            f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}"
        ].value
        payload = signing.TimestampSigner(salt=settings.COOKIE_GAME_SALT).unsign(raw)

        self.assertTrue(payload.startswith(f"{self.game.game_id}:"))

    def test_the_cookie_helpers_leave_the_session_alone(self):
        """Both helpers used to write into django_session (player_by_game,
        game_access_tokens) and nothing ever read it back. For a logged-in user
        that row linked the account to the player. A join must write nothing
        server-side beyond the Player row."""
        request = request_with_session()

        set_game_access_cookie(request, HttpResponse(), self.game.game_id)
        set_player_cookie(
            request, HttpResponse(), self.game.game_id, self.player.player_id
        )

        self.assertEqual(dict(request.session.items()), {})

    @override_settings(COOKIE_AGE=0)
    def test_unsign_value_honours_the_cookie_age(self):
        """max_age used to be None, so the TimestampSigner wrote a timestamp
        nobody read and a copied cookie stayed valid forever."""
        from co2mmute.utils import unsign_value

        signed = sign_value("anything", settings.COOKIE_PLAYER_SALT)

        with self.assertRaises(signing.SignatureExpired):
            unsign_value(signed, settings.COOKIE_PLAYER_SALT)

    def test_unsign_value_still_accepts_a_fresh_cookie(self):
        from co2mmute.utils import unsign_value

        signed = sign_value("anything", settings.COOKIE_PLAYER_SALT)

        self.assertEqual(unsign_value(signed, settings.COOKIE_PLAYER_SALT), "anything")

    def test_an_expired_cookie_reads_as_no_access(self):
        from game.auth import has_game_access

        with override_settings(COOKIE_AGE=0), muted():
            cookies = {
                f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}": signed_game_cookie(
                    self.game.game_id
                )
            }
            self.assertFalse(has_game_access(cookies, self.game.game_id))


@override_settings(**TEST_BACKENDS)
class GameBindingTests(TempMediaRootMixin, TransactionTestCase):
    """A cookie minted for one game must be worthless in another.

    player_id is four hex characters and unique *per game*
    (Player.generate_unique_player_id), so a cookie that only signs the bare id
    is one collision away from letting someone act in a game they never joined.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="host", password="pass")
        with muted():
            self.game_a = GameSession.objects.create(
                game_host=self.user,
                game_name="A",
                max_players=4,
                max_rounds=4,
                max_CO2_level=100,
                agent_per_player=1,
            )
            self.game_b = GameSession.objects.create(
                game_host=self.user,
                game_name="B",
                max_players=4,
                max_rounds=4,
                max_CO2_level=100,
                agent_per_player=1,
            )
            self.player_a = Player.objects.create(game=self.game_a, name="Mia")
            # Same player_id in game B — legal, ids are only unique per game.
            self.player_b = Player.objects.create(game=self.game_b, name="Jan")
            Player.objects.filter(pk=self.player_b.pk).update(
                player_id=self.player_a.player_id
            )
            self.player_b.refresh_from_db()

    def test_the_resolver_rejects_a_cookie_from_another_game(self):
        from game.auth import resolve_player_id

        cookies = {
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game_b.game_id}": signed_player_cookie(
                self.game_a.game_id, self.player_a.player_id
            )
        }

        with muted():
            self.assertIsNone(resolve_player_id(cookies, self.game_b.game_id))

    def test_the_resolver_accepts_a_cookie_from_its_own_game(self):
        from game.auth import resolve_player_id

        cookies = {
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game_a.game_id}": signed_player_cookie(
                self.game_a.game_id, self.player_a.player_id
            )
        }

        self.assertEqual(
            resolve_player_id(cookies, self.game_a.game_id), self.player_a.player_id
        )

    def test_the_websocket_rejects_a_cookie_from_another_game(self):
        scope = scope_with_cookies(
            **{
                f"{settings.COOKIE_PLAYER_PREFIX}{self.game_b.game_id}": signed_player_cookie(
                    self.game_a.game_id, self.player_a.player_id
                ),
                f"{settings.COOKIE_GAME_PREFIX}{self.game_b.game_id}": signed_game_cookie(
                    self.game_b.game_id
                ),
            }
        )

        with muted():
            player, close_code, _, _ = async_to_sync(resolve_player)(
                scope, self.game_b.game_id
            )

        self.assertIsNone(player)
        self.assertEqual(close_code, 4401)

    def test_rest_rejects_a_cookie_from_another_game(self):
        self.client.cookies[
            f"{settings.COOKIE_GAME_PREFIX}{self.game_b.game_id}"
        ] = signed_game_cookie(self.game_b.game_id)
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game_b.game_id}"
        ] = signed_player_cookie(self.game_a.game_id, self.player_a.player_id)

        with muted():
            response = self.client.get(
                f"/api/game/{self.game_b.game_id}/{self.player_b.player_id}/"
            )

        self.assertEqual(response.status_code, 403)

    def test_your_own_game_view_is_scoped_to_its_game(self):
        """GetYourOwnGame looked the player up by player_id alone. Both games here
        hold the same id, so that lookup raised MultipleObjectsReturned -> 500."""
        Player.objects.filter(pk=self.player_a.pk).update(
            agent_assignments={"home_node": 1, "agents": []}
        )
        Player.objects.filter(pk=self.player_b.pk).update(
            agent_assignments={"home_node": 2, "agents": []}
        )
        self.client.cookies[
            f"{settings.COOKIE_GAME_PREFIX}{self.game_a.game_id}"
        ] = signed_game_cookie(self.game_a.game_id)
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game_a.game_id}"
        ] = signed_player_cookie(self.game_a.game_id, self.player_a.player_id)

        with muted():
            response = self.client.get(
                f"/api/game/{self.game_a.game_id}/{self.player_a.player_id}/"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent_assignments"]["home_node"], 1)


@override_settings(**TEST_BACKENDS)
class ResolverParityTests(TempMediaRootMixin, TransactionTestCase):
    """REST and the websocket must reach the same verdict from the same cookies.

    The check used to be written twice, and the two had already drifted:
    HasGameAccess validated the game id embedded in the game cookie,
    IsPlayerInGame did not look at the game cookie at all.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="host", password="pass")
        with muted():
            self.game = GameSession.objects.create(
                game_host=self.user,
                game_name="Parity",
                max_players=4,
                max_rounds=4,
                max_CO2_level=100,
                agent_per_player=1,
            )
            self.player = Player.objects.create(game=self.game, name="Mia")

    def cookie_pairs(self):
        return {
            f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}": signed_game_cookie(
                self.game.game_id
            ),
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}": signed_player_cookie(
                self.game.game_id, self.player.player_id
            ),
        }

    def test_valid_cookies_pass_both_ways(self):
        from game.auth import has_game_access, resolve_player_id

        cookies = self.cookie_pairs()

        self.assertTrue(has_game_access(cookies, self.game.game_id))
        self.assertEqual(
            resolve_player_id(cookies, self.game.game_id), self.player.player_id
        )

        with muted():
            player, close_code, _, _ = async_to_sync(resolve_player)(
                scope_with_cookies(**cookies), self.game.game_id
            )
        self.assertIsNone(close_code)
        self.assertEqual(player.player_id, self.player.player_id)

    def test_a_tampered_cookie_fails_both_ways(self):
        from game.auth import has_game_access, resolve_player_id

        cookies = self.cookie_pairs()
        game_name = f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}"
        cookies[game_name] = cookies[game_name][:-3] + "xyz"

        with muted():
            self.assertFalse(has_game_access(cookies, self.game.game_id))
            player, close_code, _, _ = async_to_sync(resolve_player)(
                scope_with_cookies(**cookies), self.game.game_id
            )
        self.assertIsNone(player)
        self.assertEqual(close_code, 4401)

    def test_missing_cookies_fail_both_ways(self):
        from game.auth import has_game_access, resolve_player_id

        self.assertFalse(has_game_access({}, self.game.game_id))
        self.assertIsNone(resolve_player_id({}, self.game.game_id))


@override_settings(**TEST_BACKENDS)
class RestPermissionTests(TempMediaRootMixin, TestCase):
    """The DRF permission classes, once they delegate to the resolver."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="host", password="pass")
        with muted():
            self.game = GameSession.objects.create(
                game_host=self.user,
                game_name="Permissions",
                max_players=4,
                max_rounds=4,
                max_CO2_level=100,
                agent_per_player=1,
            )
            self.player = Player.objects.create(game=self.game, name="Mia")
            self.other = Player.objects.create(game=self.game, name="Jan")

    def authenticate_as(self, player):
        self.client.cookies[
            f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}"
        ] = signed_game_cookie(self.game.game_id)
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = signed_player_cookie(self.game.game_id, player.player_id)

    def test_a_player_who_left_is_no_longer_in_the_game(self):
        with muted():
            self.player.left_at = timezone.now()
            self.player.save()
        self.authenticate_as(self.player)

        with muted():
            response = self.client.get(
                f"/api/game/{self.game.game_id}/{self.player.player_id}/"
            )

        self.assertEqual(response.status_code, 403)

    def test_you_cannot_view_the_game_as_another_player(self):
        """GetYourOwnGame takes player_id from the URL and hands out that
        player's agent assignments. The cookie's player and the URL's player
        must be the same one — every player_id is in the lobby roster."""
        self.authenticate_as(self.player)

        with muted():
            own = self.client.get(
                f"/api/game/{self.game.game_id}/{self.player.player_id}/"
            )
            other = self.client.get(
                f"/api/game/{self.game.game_id}/{self.other.player_id}/"
            )

        self.assertEqual(own.status_code, 200, msg="control: your own id must pass")
        self.assertEqual(other.status_code, 403)

    def test_you_cannot_submit_a_move_for_another_player(self):
        """Same hole on PlayerMoveView. The game is not active, so a request that
        gets past the permissions ends in 400 — which is how the control case
        proves the permission let it through."""
        self.authenticate_as(self.player)

        with muted():
            own = self.client.post(
                f"/api/game/{self.game.game_id}/player/{self.player.player_id}/move/",
                {},
                content_type="application/json",
            )
            other = self.client.post(
                f"/api/game/{self.game.game_id}/player/{self.other.player_id}/move/",
                {},
                content_type="application/json",
            )

        self.assertEqual(own.status_code, 400, msg="control: your own id must pass")
        self.assertEqual(other.status_code, 403)

    def test_you_cannot_delete_someone_elses_player(self):
        self.authenticate_as(self.player)

        with muted():
            response = self.client.delete(
                f"/api/game/{self.game.game_id}/player/{self.other.player_id}/"
            )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Player.objects.filter(pk=self.other.pk).exists())

    def test_you_can_delete_your_own_player(self):
        self.authenticate_as(self.player)

        with muted():
            response = self.client.delete(
                f"/api/game/{self.game.game_id}/player/{self.player.player_id}/"
            )

        self.assertEqual(response.status_code, 204)

    def test_the_host_may_delete_any_player(self):
        self.client.force_login(self.user)

        with muted():
            response = self.client.delete(
                f"/api/game/{self.game.game_id}/player/{self.other.player_id}/"
            )

        self.assertEqual(response.status_code, 204)


@override_settings(**TEST_BACKENDS)
class HostActsForSeatTests(TempMediaRootMixin, TestCase):
    """IsPlayerInGame's second branch. Roadmap.md 1.6.

    The host plays seats at the host machine and sends their moves under the
    seat's player_id in the URL. The host is recognised by the session, not by
    a cookie for that seat, and only for a seat played at the host machine.

    The game is not active, so a request that gets past the permissions ends
    in 400 on the move view. That is how a test tells "let through" from 403.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="host", password="pass")
        self.other_host = User.objects.create_user(username="other", password="pass")
        with muted():
            self.game = GameSession.objects.create(
                game_host=self.user,
                game_name="Am Host",
                max_players=4,
                max_rounds=4,
                max_CO2_level=100,
                agent_per_player=1,
            )
            self.host_row = Player.objects.create(
                game=self.game, name="Host", user=self.user
            )
            self.seat = Player.objects.create(
                game=self.game, name="Ohne Handy", controlled_by_host=True
            )
            self.student = Player.objects.create(game=self.game, name="Mia")

    def move(self, player):
        with muted():
            return self.client.post(
                f"/api/game/{self.game.game_id}/player/{player.player_id}/move/",
                {},
                content_type="application/json",
            )

    def as_host_with_own_cookies(self):
        """The host as GameSessionCreateView leaves them: logged in, and both
        cookies for the host's own row."""
        self.client.force_login(self.user)
        self.client.cookies[
            f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}"
        ] = signed_game_cookie(self.game.game_id)
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = signed_player_cookie(self.game.game_id, self.host_row.player_id)

    def test_the_host_may_move_for_a_seat_at_the_host_machine(self):
        self.as_host_with_own_cookies()

        self.assertEqual(self.move(self.seat).status_code, 400)

    def test_the_host_needs_no_cookie_for_it(self):
        self.client.force_login(self.user)

        self.assertEqual(self.move(self.seat).status_code, 400)

    def test_the_host_may_read_the_seats_game_view(self):
        """GetYourOwnGame hands out the seat's agent assignments."""
        Player.objects.filter(pk=self.seat.pk).update(
            agent_assignments={"home_node": 7, "agents": []}
        )
        self.client.force_login(self.user)

        with muted():
            response = self.client.get(
                f"/api/game/{self.game.game_id}/{self.seat.player_id}/"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent_assignments"]["home_node"], 7)

    def test_the_host_may_not_move_for_a_students_seat(self):
        self.as_host_with_own_cookies()

        self.assertEqual(self.move(self.student).status_code, 403)

    def test_the_host_may_not_move_for_a_seat_that_left(self):
        Player.objects.filter(pk=self.seat.pk).update(left_at=timezone.now())
        self.client.force_login(self.user)

        self.assertEqual(self.move(self.seat).status_code, 403)

    def test_another_games_host_may_not_move_for_the_seat(self):
        self.client.force_login(self.other_host)

        self.assertEqual(self.move(self.seat).status_code, 403)

    def test_a_student_may_not_move_for_a_seat_at_the_host_machine(self):
        self.client.cookies[
            f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}"
        ] = signed_game_cookie(self.game.game_id)
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = signed_player_cookie(self.game.game_id, self.student.player_id)

        self.assertEqual(self.move(self.seat).status_code, 403)

    def test_the_host_still_reaches_their_own_row_by_cookie(self):
        """A guard, green from the start: the host row is not host-controlled,
        so the new branch does not cover it. The cookie still does."""
        self.as_host_with_own_cookies()

        self.assertEqual(self.move(self.host_row).status_code, 400)


@override_settings(**TEST_BACKENDS)
class WhoAmITests(TempMediaRootMixin, TestCase):
    """The third reader of the player cookie.

    WhoAmIView unsigned the cookie itself instead of asking the resolver. With
    the game-bound format it would read "<game_id>:<player_id>" as the player id,
    find nobody, and the SPA would lose its identity on every page load.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="host", password="pass")
        with muted():
            self.game = GameSession.objects.create(
                game_host=self.user,
                game_name="WhoAmI",
                max_players=4,
                max_rounds=4,
                max_CO2_level=100,
                agent_per_player=1,
            )
            self.other_game = GameSession.objects.create(
                game_host=self.user,
                game_name="Other",
                max_players=4,
                max_rounds=4,
                max_CO2_level=100,
                agent_per_player=1,
            )
            self.player = Player.objects.create(game=self.game, name="Mia")

    def whoami(self, game_id):
        with muted():
            return self.client.get(f"/api/whoami/?game_id={game_id}")

    def test_whoami_reads_the_game_bound_player_cookie(self):
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = signed_player_cookie(self.game.game_id, self.player.player_id)

        response = self.whoami(self.game.game_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kind"], "player")
        self.assertEqual(
            response.json()["player"]["playerId"], self.player.player_id
        )

    def test_whoami_ignores_an_expired_cookie(self):
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = signed_player_cookie(self.game.game_id, self.player.player_id)

        fresh = self.whoami(self.game.game_id)
        with override_settings(COOKIE_AGE=0):
            expired = self.whoami(self.game.game_id)

        self.assertEqual(fresh.status_code, 200, msg="control: a fresh cookie passes")
        self.assertEqual(expired.status_code, 401)

    def test_whoami_ignores_a_cookie_from_another_game(self):
        """A guard: a cookie minted for one game, renamed to another."""
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.other_game.game_id}"
        ] = signed_player_cookie(self.game.game_id, self.player.player_id)

        response = self.whoami(self.other_game.game_id)

        self.assertEqual(response.status_code, 401)


@override_settings(**TEST_BACKENDS)
class SlidingCookieTests(TempMediaRootMixin, TestCase):
    """Every visit renews both cookies. Roadmap.md 1.6, the pause.

    A class that stops at the bell and comes back next week must still hold
    its seats. The cookies used to live COOKIE_AGE from the join, however
    often the player came back. whoami is the call the SPA makes on every page
    load, so it re-issues them there. Same format, fresh timestamp: nobody is
    logged out by the change.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="host", password="pass")
        with muted():
            self.game = GameSession.objects.create(
                game_host=self.user,
                game_name="Nach der Pause",
                max_players=4,
                max_rounds=4,
                max_CO2_level=100,
                agent_per_player=1,
            )
            self.player = Player.objects.create(game=self.game, name="Mia")

    def old_player_cookie(self, days_ago):
        signed_at = time.time() - days_ago * 24 * 60 * 60
        with patch("django.core.signing.time.time", return_value=signed_at):
            return signed_player_cookie(self.game.game_id, self.player.player_id)

    def whoami(self):
        with muted():
            return self.client.get(f"/api/whoami/?game_id={self.game.game_id}")

    def renewed(self, response, prefix):
        return response.cookies.get(f"{prefix}{self.game.game_id}")

    def test_whoami_renews_both_cookies(self):
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = self.old_player_cookie(days_ago=13)

        response = self.whoami()

        self.assertEqual(response.status_code, 200)
        for prefix in (settings.COOKIE_PLAYER_PREFIX, settings.COOKIE_GAME_PREFIX):
            cookie = self.renewed(response, prefix)
            self.assertIsNotNone(cookie, msg=f"{prefix} cookie was not renewed")
            self.assertEqual(cookie["max-age"], settings.COOKIE_AGE)
            self.assertTrue(cookie["httponly"])

    def test_the_renewed_player_cookie_is_fresh_and_keeps_its_format(self):
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = self.old_player_cookie(days_ago=13)

        cookie = self.renewed(self.whoami(), settings.COOKIE_PLAYER_PREFIX)

        # Signed within the last minute; the one sent was 13 days old.
        payload = signing.TimestampSigner(salt=settings.COOKIE_PLAYER_SALT).unsign(
            cookie.value, max_age=60
        )
        self.assertEqual(payload, f"{self.game.game_id}:{self.player.player_id}")

    def test_the_renewed_game_cookie_names_its_game(self):
        from game.auth import has_game_access

        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = signed_player_cookie(self.game.game_id, self.player.player_id)

        cookie = self.renewed(self.whoami(), settings.COOKIE_GAME_PREFIX)

        self.assertIsNotNone(cookie)
        self.assertTrue(
            has_game_access(
                {f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}": cookie.value},
                self.game.game_id,
            )
        )

    def test_a_host_holding_a_seat_cookie_gets_it_renewed_too(self):
        self.client.force_login(self.user)
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = signed_player_cookie(self.game.game_id, self.player.player_id)

        response = self.whoami()

        self.assertEqual(response.json()["kind"], "host")
        self.assertIsNotNone(self.renewed(response, settings.COOKIE_PLAYER_PREFIX))

    def test_nothing_is_renewed_without_a_player(self):
        """A guard, green from the start."""
        response = self.whoami()

        self.assertEqual(response.status_code, 401)
        self.assertIsNone(self.renewed(response, settings.COOKIE_PLAYER_PREFIX))
        self.assertIsNone(self.renewed(response, settings.COOKIE_GAME_PREFIX))

    def test_an_expired_cookie_is_not_renewed(self):
        """A guard, green from the start. Renewal extends a live cookie; it
        doesn't bring a dead one back."""
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = self.old_player_cookie(days_ago=15)

        response = self.whoami()

        self.assertEqual(response.status_code, 401)
        self.assertIsNone(self.renewed(response, settings.COOKIE_PLAYER_PREFIX))

    def test_a_player_who_left_gets_nothing(self):
        """A guard, green from the start."""
        Player.objects.filter(pk=self.player.pk).update(left_at=timezone.now())
        self.client.cookies[
            f"{settings.COOKIE_PLAYER_PREFIX}{self.game.game_id}"
        ] = signed_player_cookie(self.game.game_id, self.player.player_id)

        response = self.whoami()

        self.assertIsNone(self.renewed(response, settings.COOKIE_PLAYER_PREFIX))


class SettingsHardeningTests(TestCase):
    """The HTTPS flags, and the dead CORS config."""

    def _cookie_flags_under(self, **environment):
        """Import settings.py again under a chosen environment, and report the
        two flags it derives.

        They are computed at import from os.environ, and DiscoverRunner forces
        settings.DEBUG to False for every run — so the skip guard this test
        used to carry never fired, whatever DJANGO_DEBUG said, and the
        assertion reported the environment the run happened to have: green in
        the container, where compose sets DJANGO_DEBUG=False, red on a bare
        host shell and on a CI runner, which set nothing. Re-importing under a
        known environment tests the derivation itself, the same way on every
        machine and under either settings module.
        """
        import importlib
        import os
        import shutil
        import tempfile
        from unittest import mock

        from co2mmute import settings as settings_module

        media_root = tempfile.mkdtemp(prefix="co2mmute-settings-reload-")
        self.addCleanup(shutil.rmtree, media_root, True)
        environment.setdefault("DJANGO_MEDIA_ROOT", media_root)
        environment.setdefault(
            "DJANGO_SECRET_KEY", "a-real-enough-key-for-this-test-0123456789"
        )

        try:
            with mock.patch.dict(os.environ, environment, clear=True):
                reloaded = importlib.reload(settings_module)
                # Django's own default is False, so a deleted derivation reads
                # as the insecure value rather than an AttributeError — which
                # is both what would ship and the clearer failure message.
                return (
                    getattr(reloaded, "SESSION_COOKIE_SECURE", False),
                    getattr(reloaded, "CSRF_COOKIE_SECURE", False),
                )
        finally:
            # Leave the module holding the values this run really has.
            importlib.reload(settings_module)

    def test_cookies_are_secure_when_debug_is_off(self):
        """Django's defaults are False, so `hasattr` proves nothing — assert the
        value. DEBUG off is the case that matters: it is how the compose stack
        and the live box run."""
        session_secure, csrf_secure = self._cookie_flags_under(DJANGO_DEBUG="False")

        self.assertTrue(session_secure)
        self.assertTrue(csrf_secure)

    def test_a_debug_box_is_allowed_to_stay_insecure(self):
        """The other half of the same rule, and why the flags are derived
        rather than hard-coded: a plain http dev box still has to work, so
        DEBUG on hands out unsecured cookies on purpose."""
        session_secure, csrf_secure = self._cookie_flags_under(DJANGO_DEBUG="True")

        self.assertFalse(session_secure)
        self.assertFalse(csrf_secure)

    def test_the_environment_can_override_either_way(self):
        """DJANGO_SECURE_COOKIES wins over the DEBUG default, in both
        directions — that is what makes a hardened DEBUG box possible, and it
        is the switch settings_test re-derives for itself."""
        self.assertEqual(
            self._cookie_flags_under(DJANGO_DEBUG="True", DJANGO_SECURE_COOKIES="True"),
            (True, True),
        )
        self.assertEqual(
            self._cookie_flags_under(
                DJANGO_DEBUG="False", DJANGO_SECURE_COOKIES="False"
            ),
            (False, False),
        )

    def test_hsts_does_not_over_reach(self):
        """A guard, green from the start: the host is a subdomain of
        tu-berlin.de and this project does not get to make promises on behalf of
        the university's other services. includeSubDomains and preload stay off
        even once SECURE_HSTS_SECONDS is turned on."""
        from django.conf import settings as django_settings

        self.assertFalse(django_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertFalse(django_settings.SECURE_HSTS_PRELOAD)

    def test_corsheaders_is_gone(self):
        """In INSTALLED_APPS with no middleware — dead config. nginx makes
        everything same-origin, so there is nothing to allow."""
        from django.conf import settings as django_settings

        self.assertNotIn("corsheaders", django_settings.INSTALLED_APPS)
