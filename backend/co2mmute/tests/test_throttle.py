"""Rate limiting: the seat code, the login and the sign-up.

Three doors, one mechanism (`co2mmute/throttle.py`), so they are one topic
rather than three additions to three feature files.

**What is counted is the point of the design.** A classroom sits behind one
school NAT, so every phone in the room shares an IP — counting *attempts* would
throttle a class for playing. So:

- the seat code and the login count **failures** only. A class redeeming valid
  codes is never counted; somebody guessing produces nothing but misses.
- the sign-up counts **successes**, because a failed sign-up guesses at nothing
  and the abuse being stopped is mass account creation.

**No raw IP is stored.** `client_key` hashes the address with a `SECRET_KEY`
salt, so what lives in Redis for the window is a digest that cannot be read
back — the same data-minimisation the rest of the project is built on, and it
is why `legal/dsgvo.html` §2 can describe this in one sentence.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from game.models import Player
from game.seats import issue_code
from game.tests._helpers import (
    TempMediaRootMixin,
    create_game_session,
    create_host,
    muted,
)

User = get_user_model()

LOGIN_URL = "/accounts/login/"
SIGNUP_URL = "/accounts/signup/"

LOCAL_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "throttle-tests",
    }
}


@override_settings(CACHES=LOCAL_CACHE)
class ClientKeyTests(TestCase):
    """Which address is counted, and what is left of it afterwards."""

    def setUp(self):
        cache.clear()

    def test_the_stored_key_is_not_the_address(self):
        from co2mmute.throttle import client_key

        request = self.client.request(REMOTE_ADDR="203.0.113.9").wsgi_request

        key = client_key(request)

        self.assertNotIn("203.0.113.9", key)
        self.assertNotIn("203.0.113", key)

    def test_the_same_address_gives_the_same_key(self):
        from co2mmute.throttle import client_key

        one = self.client.request(REMOTE_ADDR="203.0.113.9").wsgi_request
        two = self.client.request(REMOTE_ADDR="203.0.113.9").wsgi_request

        self.assertEqual(client_key(one), client_key(two))

    def test_two_addresses_give_two_keys(self):
        from co2mmute.throttle import client_key

        one = self.client.request(REMOTE_ADDR="203.0.113.9").wsgi_request
        two = self.client.request(REMOTE_ADDR="203.0.113.10").wsgi_request

        self.assertNotEqual(client_key(one), client_key(two))

    def test_x_real_ip_wins_over_remote_addr(self):
        """nginx sets `X-Real-IP` from `$remote_addr`, overwriting whatever the
        client sent. Behind the proxy `REMOTE_ADDR` is nginx itself, so without
        this the whole internet shares one counter."""
        from co2mmute.throttle import client_key

        proxied = self.client.request(
            REMOTE_ADDR="172.18.0.5", HTTP_X_REAL_IP="203.0.113.9"
        ).wsgi_request
        direct = self.client.request(REMOTE_ADDR="203.0.113.9").wsgi_request

        self.assertEqual(client_key(proxied), client_key(direct))

    def test_x_forwarded_for_is_ignored(self):
        """`$proxy_add_x_forwarded_for` appends to whatever the client sent, so
        its leftmost entry is attacker-controlled: trusting it would let one
        guesser spend a fresh quota on every request."""
        from co2mmute.throttle import client_key

        spoofed = self.client.request(
            REMOTE_ADDR="203.0.113.9", HTTP_X_FORWARDED_FOR="10.0.0.1, 203.0.113.9"
        ).wsgi_request
        plain = self.client.request(REMOTE_ADDR="203.0.113.9").wsgi_request

        self.assertEqual(client_key(spoofed), client_key(plain))


@override_settings(CACHES=LOCAL_CACHE)
class WindowTests(TestCase):
    """The counter itself."""

    def setUp(self):
        cache.clear()

    def test_it_allows_up_to_the_limit(self):
        """A limit of 3 means three events go through and the fourth does not,
        so nothing is refused while the count is still below it."""
        from co2mmute.throttle import over_limit, record

        for _ in range(2):
            record("scope", "key", window=60)
            self.assertFalse(over_limit("scope", "key", limit=3))

    def test_it_refuses_once_the_limit_is_reached(self):
        from co2mmute.throttle import over_limit, record

        for _ in range(3):
            record("scope", "key", window=60)

        self.assertTrue(over_limit("scope", "key", limit=3))

    def test_two_keys_do_not_share_a_counter(self):
        from co2mmute.throttle import over_limit, record

        for _ in range(4):
            record("scope", "one", window=60)

        self.assertFalse(over_limit("scope", "two", limit=3))

    def test_two_scopes_do_not_share_a_counter(self):
        from co2mmute.throttle import over_limit, record

        for _ in range(4):
            record("login", "key", window=60)

        self.assertFalse(over_limit("signup", "key", limit=3))

    def test_clearing_forgets_the_counter(self):
        """A successful login drops the failures before it, so a host who
        mistypes four times and then gets it right is not locked out."""
        from co2mmute.throttle import clear, over_limit, record

        for _ in range(4):
            record("scope", "key", window=60)
        clear("scope", "key")

        self.assertFalse(over_limit("scope", "key", limit=3))


@override_settings(CACHES=LOCAL_CACHE)
class LoginThrottleTests(TestCase):
    """`/accounts/login/` — guessing a host's password."""

    def setUp(self):
        cache.clear()
        self.user = create_host(username="host")

    def _guess(self, password="wrong-password"):
        return self.client.post(
            LOGIN_URL, {"username": "host", "password": password}
        )

    def test_a_wrong_password_is_refused_as_before(self):
        response = self._guess()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_too_many_wrong_passwords_are_answered_429(self):
        from co2mmute.throttle import LOGIN_LIMIT

        for _ in range(LOGIN_LIMIT):
            self._guess()

        response = self._guess()

        self.assertEqual(response.status_code, 429)

    def test_the_right_password_is_refused_once_the_limit_is_reached(self):
        """Otherwise the throttle is no throttle at all: a guesser who finds the
        password on attempt 11 would still be let in."""
        from co2mmute.throttle import LOGIN_LIMIT

        for _ in range(LOGIN_LIMIT):
            self._guess()

        response = self._guess(password="password123")

        self.assertEqual(response.status_code, 429)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_a_successful_login_clears_the_failures(self):
        from co2mmute.throttle import LOGIN_LIMIT

        for _ in range(LOGIN_LIMIT - 1):
            self._guess()

        self.client.post(LOGIN_URL, {"username": "host", "password": "password123"})
        self.client.logout()
        response = self._guess()

        self.assertEqual(response.status_code, 200)

    def test_the_refusal_is_german_and_names_no_user(self):
        from co2mmute.throttle import LOGIN_LIMIT

        for _ in range(LOGIN_LIMIT):
            self._guess()

        body = self._guess().content.decode()

        self.assertIn("Zu viele", body)
        self.assertNotIn("host", body.lower().split("host@")[0].replace("hostname", ""))

    def test_another_address_is_not_throttled(self):
        """A school NAT is one address; a guesser is another. The counter is
        per address, so one room's mistakes never reach another's."""
        from co2mmute.throttle import LOGIN_LIMIT

        for _ in range(LOGIN_LIMIT + 1):
            self.client.post(
                LOGIN_URL,
                {"username": "host", "password": "wrong-password"},
                REMOTE_ADDR="203.0.113.9",
            )

        response = self.client.post(
            LOGIN_URL,
            {"username": "host", "password": "wrong-password"},
            REMOTE_ADDR="203.0.113.10",
        )

        self.assertEqual(response.status_code, 200)


@override_settings(CACHES=LOCAL_CACHE)
class SignupThrottleTests(TestCase):
    """`/accounts/signup/` — mass account creation.

    Successes are counted, not attempts: a would-be host fumbling the password
    rules has guessed at nothing, and locking them out of their own sign-up is
    the one thing this must not do.
    """

    def setUp(self):
        cache.clear()

    def _sign_up(self, username):
        return self.client.post(
            SIGNUP_URL,
            {
                "username": username,
                "email": f"{username}@example.com",
                "password": "Lange-Passphrase7",
            },
        )

    def test_one_sign_up_goes_through(self):
        response = self._sign_up("first")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="first").exists())

    def test_too_many_sign_ups_are_answered_429(self):
        from co2mmute.throttle import SIGNUP_LIMIT

        for index in range(SIGNUP_LIMIT):
            self.client.logout()
            self._sign_up(f"host{index}")

        self.client.logout()
        response = self._sign_up("one-too-many")

        self.assertEqual(response.status_code, 429)
        self.assertFalse(User.objects.filter(username="one-too-many").exists())

    def test_a_rejected_form_is_not_counted(self):
        from co2mmute.throttle import SIGNUP_LIMIT

        for index in range(SIGNUP_LIMIT + 2):
            self.client.post(
                SIGNUP_URL,
                {
                    "username": f"host{index}",
                    "email": "",
                    "password": "x",
                },
            )

        response = self._sign_up("after-the-fumbling")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="after-the-fumbling").exists())


@override_settings(CACHES=LOCAL_CACHE)
class SeatCodeThrottleTests(TempMediaRootMixin, TestCase):
    """`GET/POST api/game/seat/<code>/` — guessing a six-character code.

    31^6 is 887 million, which is only a number while guessing is free. GET is
    the cheaper vector of the two: it does not use a code up, so a guesser can
    sweep with it and never disturb a real seat.
    """

    def setUp(self):
        cache.clear()
        self.host = create_host()
        self.game = create_game_session(self.host)
        self.seat = Player.objects.create(game=self.game, name="Ana")

    def _miss(self, code="ZZZZZZ"):
        return self.client.get(f"/api/game/seat/{code}/")

    def test_an_unknown_code_is_404_as_before(self):
        self.assertEqual(self._miss().status_code, 404)

    def test_too_many_misses_are_answered_429(self):
        from co2mmute.throttle import SEAT_CODE_LIMIT

        for _ in range(SEAT_CODE_LIMIT):
            self._miss()

        self.assertEqual(self._miss().status_code, 429)

    def test_the_post_shares_the_counter_with_the_get(self):
        """Otherwise the limit is twice what it says."""
        from co2mmute.throttle import SEAT_CODE_LIMIT

        for _ in range(SEAT_CODE_LIMIT):
            self._miss()

        response = self.client.post("/api/game/seat/ZZZZZZ/")

        self.assertEqual(response.status_code, 429)

    def test_a_real_code_still_works_after_a_few_misses(self):
        """The classroom case: someone mistypes twice and then gets it right."""
        code = issue_code(self.seat)
        self._miss()
        self._miss()

        response = self.client.get(f"/api/game/seat/{code}/")

        self.assertEqual(response.status_code, 200)

    def test_valid_lookups_are_never_counted(self):
        """A whole class redeeming codes behind one NAT must not be throttled,
        which is why this counts misses rather than requests."""
        from co2mmute.throttle import SEAT_CODE_LIMIT

        for _ in range(SEAT_CODE_LIMIT + 5):
            code = issue_code(self.seat)
            self.assertEqual(
                self.client.get(f"/api/game/seat/{code}/").status_code, 200
            )

        self.assertEqual(self._miss().status_code, 404)

    def test_the_refusal_says_why(self):
        from co2mmute.throttle import SEAT_CODE_LIMIT

        for _ in range(SEAT_CODE_LIMIT):
            self._miss()

        body = self._miss().json()

        self.assertEqual(body.get("reason"), "throttled")
