"""The credential pages: log in, sign up, the two password flows, log out. S22.

These stay server-rendered on purpose — anything that asks for a password is
Django's, because the host machine stands in a room and is often still logged
in. They were also the last pages the design pass had not reached, and under the Tailwind UI boilerplate four things
were wrong that no test had looked at:

- a wrong password came back as the same empty form, with no word of why;
- sign-up answered in English, and listed the password rules as a Python list
  (`['This password is too short. …', …]`), quotes HTML-escaped;
- "Angemeldet bleiben" was a checkbox nothing read: every login lasted the full
  session age, ticked or not;
- the password-reset form, its two follow-up pages and the password change did
  not compile, so "Passwort vergessen?" on the login page and "Passwort ändern"
  on the host page both answered a 500.

The last one is pinned project-wide in `test_sanity.EveryTemplateCompilesTests`;
what is here is what a person meets on each page.

Same rule as every other copy test in this project: nothing asserts an exact
sentence. A refusal has to *be there* and has to *not be English*; the wording
stays free to improve.
"""

import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from game.tests._helpers import create_host, english_in, visible_text

User = get_user_model()

LOGIN_URL = "/accounts/login/"
SIGNUP_URL = "/accounts/signup/"
LOGOUT_URL = "/accounts/logout/"
RESET_URL = "/accounts/password_reset/"
RESET_DONE_URL = "/accounts/password_reset/done/"
RESET_COMPLETE_URL = "/accounts/reset/done/"
CHANGE_URL = "/accounts/password_change/"
CHANGE_DONE_URL = "/accounts/password_change/done/"

GOOD_PASSWORD = "Fahrrad-2026!"

# The login counts wrong passwords per address (S9); keep that counter out of
# Redis, which no test run has, and out of the next test.
LOCAL_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "credential-tests",
    }
}


def page_text(response):
    return visible_text(response.content.decode())


def alerts(response):
    """The text of everything the page marks `role="alert"`.

    That attribute is what a screen reader announces, so it is also the honest
    test of "the page says something went wrong" — an error that exists only in
    the form object and never reaches the markup is the bug this module found.
    """
    html = response.content.decode()
    found = re.findall(r'role="alert"[^>]*>(.*?)</(?:div|ul|p)>', html, flags=re.S)
    return [visible_text(chunk) for chunk in found if visible_text(chunk)]


@override_settings(CACHES=LOCAL_CACHE)
class LoginFailureTests(TestCase):
    """A wrong password has to say so."""

    def setUp(self):
        cache.clear()
        self.user = create_host(username="host", password=GOOD_PASSWORD)

    def _login(self, username="host", password="falsch"):
        return self.client.post(LOGIN_URL, {"username": username, "password": password})

    def test_a_wrong_password_says_so(self):
        response = self._login()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(len(alerts(response)), 1, page_text(response)[:400])

    def test_the_refusal_is_german(self):
        response = self._login()

        self.assertTrue(alerts(response))
        self.assertEqual(english_in(" ".join(alerts(response))), [])

    def test_an_unknown_name_reads_exactly_like_a_wrong_password(self):
        """Otherwise the page answers "does this account exist" for anybody."""
        wrong_password = alerts(self._login())
        cache.clear()
        unknown_name = alerts(self._login(username="niemand"))

        self.assertTrue(wrong_password)
        self.assertEqual(wrong_password, unknown_name)

    def test_the_name_stays_in_the_field(self):
        response = self._login()

        self.assertIn('value="host"', response.content.decode())

    def test_empty_fields_are_refused_in_german(self):
        response = self._login(username="", password="")

        self.assertEqual(response.status_code, 200)
        messages = alerts(response)
        self.assertEqual(len(messages), 2, page_text(response)[:400])
        self.assertEqual(english_in(" ".join(messages)), [])

    def test_the_page_itself_is_german(self):
        response = self.client.get(LOGIN_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(english_in(page_text(response)), [], page_text(response)[:400])


@override_settings(CACHES=LOCAL_CACHE)
class RememberMeTests(TestCase):
    """"Angemeldet bleiben" decides how long the login lasts.

    The host machine stands in a room, often projected and often still logged
    in, so the default is the short one: without the box the session ends with
    the browser. With it, the session lasts `SESSION_COOKIE_AGE`, as every
    login did before. `legal/cookies.html` §2.1 says both.
    """

    def setUp(self):
        cache.clear()
        self.user = create_host(username="host", password=GOOD_PASSWORD)

    def _login(self, **extra):
        return self.client.post(
            LOGIN_URL, {"username": "host", "password": GOOD_PASSWORD, **extra}
        )

    def test_the_box_is_on_the_page(self):
        response = self.client.get(LOGIN_URL)

        self.assertRegex(
            response.content.decode(), r'<input[^>]*type="checkbox"[^>]*name="remember_me"'
        )

    def test_without_the_box_the_login_ends_with_the_browser(self):
        self._login()

        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_with_the_box_the_login_lasts(self):
        self._login(remember_me="on")

        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)


@override_settings(CACHES=LOCAL_CACHE)
class LoginLandsOnTheHostPageTests(TestCase):
    """One hop, not two.

    `LOGIN_REDIRECT_URL` was Django's default `/accounts/profile/`, which since
    S13 is itself a redirect into `/app/host` — so signing in was a chain, and
    `e2e/host.ts` had to wait out both links. S22 owns that decision.
    """

    def setUp(self):
        cache.clear()
        self.user = create_host(username="host", password=GOOD_PASSWORD)

    def test_a_login_goes_straight_to_the_host_page(self):
        response = self.client.post(
            LOGIN_URL, {"username": "host", "password": GOOD_PASSWORD}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/app/host")

    def test_next_still_wins(self):
        response = self.client.post(
            f"{LOGIN_URL}?next=/app/maps",
            {"username": "host", "password": GOOD_PASSWORD},
        )

        self.assertEqual(response["Location"], "/app/maps")

    def test_a_sign_up_lands_there_too(self):
        response = self.client.post(
            SIGNUP_URL,
            {"username": "neu", "email": "neu@example.com", "password": GOOD_PASSWORD},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/app/host")


@override_settings(CACHES=LOCAL_CACHE)
class SignupErrorTests(TestCase):
    """Sign-up refuses in German, one sentence per rule."""

    def setUp(self):
        cache.clear()

    def _signup(self, **data):
        body = {"username": "neu", "email": "neu@example.com", "password": GOOD_PASSWORD}
        body.update(data)
        return self.client.post(SIGNUP_URL, body)

    def _password_errors(self, password, **data):
        response = self._signup(password=password, **data)
        self.assertEqual(response.status_code, 400)
        return response, list(response.context["form"].errors.get("password", []))

    def test_the_page_is_german(self):
        response = self.client.get(SIGNUP_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(english_in(page_text(response)), [], page_text(response)[:400])

    def test_the_password_rules_are_said_before_they_are_broken(self):
        """The rules are four, and a person should read them before typing."""
        from co2mmute.forms import SignupForm

        help_text = str(SignupForm().fields["password"].help_text)

        self.assertIn("8", help_text)
        self.assertEqual(english_in(help_text), [])

    def test_the_password_rules_are_sentences_not_a_list(self):
        response, errors = self._password_errors("abc")

        self.assertGreater(len(errors), 1)
        for message in errors:
            self.assertFalse(message.startswith("["), message)
        self.assertNotIn("[&#x27;", response.content.decode())

    def test_every_broken_rule_is_named_in_german(self):
        cases = {
            "too short, no digit, no capital, no special character": "abc",
            "all digits": "12345678",
            "too common": "password",
            "too like the name": "fahrradfahrer1A!",
        }
        for why, password in cases.items():
            with self.subTest(why):
                response, errors = self._password_errors(password, username="fahrradfahrer")

                self.assertTrue(errors, why)
                self.assertEqual(english_in(" ".join(errors)), [], errors)
                self.assertTrue(alerts(response), page_text(response)[:400])

    def test_a_bad_username_is_refused_in_german(self):
        response = self._signup(username="a b!")

        errors = response.context["form"].errors["username"]
        self.assertEqual(english_in(" ".join(errors)), [], errors)

    def test_a_taken_username_is_refused_in_german(self):
        create_host(username="neu")

        response = self._signup()

        errors = response.context["form"].errors["username"]
        self.assertEqual(english_in(" ".join(errors)), [], errors)

    def test_a_bad_email_is_refused_in_german(self):
        response = self._signup(email="keine-adresse")

        errors = response.context["form"].errors["email"]
        self.assertEqual(english_in(" ".join(errors)), [], errors)

    def test_empty_fields_are_refused_in_german(self):
        response = self.client.post(SIGNUP_URL, {})

        errors = response.context["form"].errors
        self.assertEqual(set(errors), {"username", "email", "password"})
        for field, messages in errors.items():
            self.assertEqual(english_in(" ".join(messages)), [], field)

    def test_what_was_typed_stays(self):
        response = self._signup(password="abc")

        html = response.content.decode()
        self.assertIn('value="neu"', html)
        self.assertIn('value="neu@example.com"', html)


class PasswordResetFlowTests(TestCase):
    """"Passwort vergessen?", end to end.

    Three of these four pages did not compile until S22. Whether the box can
    actually send the mail is a question for its mail setup, not for this
    module — Django's test runner swaps in the in-memory backend.
    """

    def setUp(self):
        self.user = create_host(username="host", email="host@example.com")

    def _reset_link(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        return f"/accounts/reset/{uid}/{token}/"

    def test_every_page_answers_and_is_german(self):
        for url in (RESET_URL, RESET_DONE_URL, RESET_COMPLETE_URL, "/accounts/reset/xx/yy/"):
            with self.subTest(url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(english_in(page_text(response)), [], page_text(response)[:400])

    def test_a_known_address_gets_one_german_mail(self):
        response = self.client.post(RESET_URL, {"email": "host@example.com"})

        self.assertRedirects(response, RESET_DONE_URL)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(english_in(message.subject), [])
        body = visible_text(message.alternatives[0][0]) if message.alternatives else message.body
        self.assertEqual(english_in(body), [], body[:400])
        self.assertIn("/accounts/reset/", message.body + str(message.alternatives))

    def test_an_unknown_address_reads_the_same_and_sends_nothing(self):
        response = self.client.post(RESET_URL, {"email": "niemand@example.com"})

        self.assertRedirects(response, RESET_DONE_URL)
        self.assertEqual(len(mail.outbox), 0)

    def test_a_bad_address_is_refused_in_german(self):
        response = self.client.post(RESET_URL, {"email": "keine-adresse"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(alerts(response))
        self.assertEqual(english_in(" ".join(alerts(response))), [])

    def test_the_link_leads_to_a_german_form(self):
        response = self.client.get(self._reset_link(), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["validlink"])
        self.assertEqual(english_in(page_text(response)), [], page_text(response)[:400])

    def test_two_different_passwords_are_refused_in_german(self):
        form_url = self.client.get(self._reset_link())["Location"]

        response = self.client.post(
            form_url, {"new_password1": GOOD_PASSWORD, "new_password2": GOOD_PASSWORD + "x"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(english_in(" ".join(alerts(response))), [], alerts(response))
        self.assertTrue(alerts(response))

    def test_a_weak_password_is_refused_in_german(self):
        form_url = self.client.get(self._reset_link())["Location"]

        response = self.client.post(form_url, {"new_password1": "abc", "new_password2": "abc"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(alerts(response))
        self.assertEqual(english_in(" ".join(alerts(response))), [], alerts(response))

    def test_a_good_password_is_set(self):
        form_url = self.client.get(self._reset_link())["Location"]

        response = self.client.post(
            form_url, {"new_password1": GOOD_PASSWORD, "new_password2": GOOD_PASSWORD}
        )

        self.assertRedirects(response, RESET_COMPLETE_URL)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(GOOD_PASSWORD))


class PasswordChangeFlowTests(TestCase):
    """"Passwort ändern" on the host page — a 500 until S22."""

    def setUp(self):
        self.user = create_host(username="host", password="Alt-Passwort-1!")
        self.client.force_login(self.user)

    def test_the_page_answers_and_is_german(self):
        response = self.client.get(CHANGE_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(english_in(page_text(response)), [], page_text(response)[:400])

    def test_a_wrong_old_password_is_refused_in_german(self):
        response = self.client.post(
            CHANGE_URL,
            {
                "old_password": "falsch",
                "new_password1": GOOD_PASSWORD,
                "new_password2": GOOD_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(alerts(response))
        self.assertEqual(english_in(" ".join(alerts(response))), [], alerts(response))

    def test_the_new_password_is_set_and_you_stay_logged_in(self):
        response = self.client.post(
            CHANGE_URL,
            {
                "old_password": "Alt-Passwort-1!",
                "new_password1": GOOD_PASSWORD,
                "new_password2": GOOD_PASSWORD,
            },
        )

        self.assertRedirects(response, CHANGE_DONE_URL)
        done = self.client.get(CHANGE_DONE_URL)
        self.assertEqual(done.status_code, 200)
        self.assertTrue(done.wsgi_request.user.is_authenticated)
        self.assertEqual(english_in(page_text(done)), [], page_text(done)[:400])


class LogoutPageTests(TestCase):
    def test_logging_out_lands_on_a_german_page(self):
        self.client.force_login(create_host())

        response = self.client.get(LOGOUT_URL)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(english_in(page_text(response)), [], page_text(response)[:400])


class GeneratedImageIsGoneTests(TestCase):
    """The login and sign-up pages carried an AI-generated picture.

    Lukas, S10: "both still use the ai generated image". The pages are text
    and a form now, and the file goes with them rather than lingering in
    `static/` for the next template to pick up again.
    """

    def test_nothing_ships_it(self):
        backend = settings.BASE_DIR
        self.assertFalse((backend / "static" / "img" / "index_1.png").exists())
        for path in (backend / "template").rglob("*.html"):
            self.assertNotIn("index_1", path.read_text(encoding="utf-8"), str(path))
