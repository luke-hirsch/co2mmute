"""Player identity: the two signed cookies, and the one resolver behind them.

Players have no account and never will (CLAUDE.md, "players are minors"). All the
identity there is lives in `game_access_<game_id>` and `player_<game_id>`, so this
file is where the hardening in Roadmap.md 1.2 is pinned down.
"""

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import signing
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
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
    """A request that set_game_access_cookie / set_player_cookie can write to.

    Both helpers stash a token in request.session, so a bare RequestFactory
    request is not enough.
    """
    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: HttpResponse())(request)
    request.session.save()
    return request


class WsAuthTests(TestCase):
    """The two cases that have been failing since before phase 0.

    resolve_player calls channels.auth.get_user unconditionally, and get_user
    needs scope["session"], which a hand-built scope does not have:
    `ValueError: Cannot find session in scope`. 1.2 guards the call.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="host", password="pass")

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

        with override_settings(COOKIE_AGE=0):
            cookies = {
                f"{settings.COOKIE_GAME_PREFIX}{self.game.game_id}": signed_game_cookie(
                    self.game.game_id
                )
            }
            self.assertFalse(has_game_access(cookies, self.game.game_id))


@override_settings(**TEST_BACKENDS)
class GameBindingTests(TempMediaRootMixin, TestCase):
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


@override_settings(**TEST_BACKENDS)
class ResolverParityTests(TempMediaRootMixin, TestCase):
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


class SettingsHardeningTests(TestCase):
    """The HTTPS flags, and the dead CORS config."""

    def test_cookies_are_secure_when_debug_is_off(self):
        """Django's defaults are False, so `hasattr` proves nothing — assert the
        value. The compose stack runs with DJANGO_DEBUG=False, which is the case
        that matters; a DEBUG run is allowed to stay insecure so a plain http dev
        box still works."""
        from django.conf import settings as django_settings

        if django_settings.DEBUG:
            self.skipTest("secure cookies are deliberately off under DEBUG")

        self.assertTrue(django_settings.SESSION_COOKIE_SECURE)
        self.assertTrue(django_settings.CSRF_COOKIE_SECURE)

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
