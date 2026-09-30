import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from game.models import GameSession
from game.tests._helpers import TempMediaRootMixin, create_game_session, muted

User = get_user_model()

PROFILE_URL = "/accounts/profile/"
ACCOUNT_URL = "/api/account/"
DELETE_URL = "/accounts/profile/delete/"
DELETED_URL = "/accounts/deleted/"


def _host(username="host", email="host@example.com", **extra):
    return User.objects.create_user(
        username=username,
        email=email,
        password="password123",
        **extra,
    )


class ProfileRedirectTests(TestCase):
    """`/accounts/profile/` is a doorway into the SPA. S13.

    The page followed the create form across, because the host's own pages
    belong together (Lukas, 2026-09-28). The URL stays because Django's
    `LOGIN_REDIRECT_URL` defaults to it and because the footer, the app header
    and the account-deletion pages all point at it.
    """

    def setUp(self):
        self.user = _host(first_name="Sebastian")

    def test_a_host_lands_in_the_spa(self):
        self.client.force_login(self.user)

        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/app/host")

    def test_a_stranger_is_sent_to_the_login_first(self):
        """Not into the SPA, which would only bounce them back a tick later."""
        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_the_form_is_gone(self):
        """Two forms for one account is the class of bug this project has."""
        import co2mmute.forms as forms

        self.assertFalse(hasattr(forms, "ProfileForm"))


class AccountEndpointTests(TestCase):
    """`GET`/`PATCH api/account/` — what `ProfileForm` used to do.

    Only ever the requesting user: there is no pk in the path and none is
    accepted, so the endpoint cannot be pointed at somebody else's row.
    """

    def setUp(self):
        self.user = _host(first_name="Sebastian")
        self.client.force_login(self.user)

    def _patch(self, **fields):
        return self.client.patch(
            ACCOUNT_URL, json.dumps(fields), content_type="application/json"
        )

    def test_it_answers_with_the_current_values(self):
        response = self.client.get(ACCOUNT_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "username": "host",
                "email": "host@example.com",
                "first_name": "Sebastian",
            },
        )

    def test_a_stranger_gets_nothing(self):
        self.client.logout()

        self.assertIn(self.client.get(ACCOUNT_URL).status_code, (401, 403))

    def test_a_stranger_cannot_write_either(self):
        self.client.logout()

        response = self._patch(username="eindringling")

        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(User.objects.filter(username="eindringling").exists())

    def test_the_display_name_can_change(self):
        response = self._patch(first_name="Basti")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.first_name, "Basti")

    def test_the_username_can_change(self):
        self._patch(username="spielleitung")

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "spielleitung")

    def test_the_email_can_change(self):
        self._patch(email="neu@example.com")

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "neu@example.com")

    def test_the_answer_carries_the_saved_values(self):
        """The screen renders what comes back rather than what it sent."""
        response = self._patch(first_name="Basti")

        self.assertEqual(response.json()["first_name"], "Basti")

    def test_changing_the_username_does_not_log_you_out(self):
        """Session auth hashes the password, not the name — pin it anyway.

        `AccountView.patch` deliberately does *not* call
        `update_session_auth_hash`, which would suggest a rename invalidated
        the session. This is what says it does not.
        """
        self._patch(username="spielleitung")

        self.assertEqual(self.client.get(ACCOUNT_URL).status_code, 200)

    def test_whitespace_around_a_value_is_dropped(self):
        self._patch(username="  spielleitung  ")

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "spielleitung")

    def test_the_display_name_may_be_empty(self):
        self._patch(first_name="")

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "")


class AccountUniquenessTests(TestCase):
    """The trap: an update is not a signup.

    `SignupForm.clean_username` asks whether *anybody* holds the name. On an
    update the answer is yes — you do. Saving without touching the name has to
    work, or every edit to any other field is refused.
    """

    def setUp(self):
        self.user = _host(first_name="Sebastian")
        self.other = _host(username="kollegin", email="kollegin@example.com")
        self.client.force_login(self.user)

    def _patch(self, **fields):
        return self.client.patch(
            ACCOUNT_URL, json.dumps(fields), content_type="application/json"
        )

    def test_keeping_your_own_username_is_not_a_conflict(self):
        response = self._patch(username="host", first_name="Basti")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.first_name, "Basti")

    def test_keeping_your_own_email_is_not_a_conflict(self):
        response = self._patch(email="host@example.com", username="spielleitung")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.username, "spielleitung")

    def test_somebody_elses_username_is_refused(self):
        response = self._patch(username="kollegin")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())
        self.assertEqual(self.user.username, "host")

    def test_somebody_elses_username_is_refused_in_any_case(self):
        response = self._patch(username="Kollegin")

        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())

    def test_somebody_elses_email_is_refused(self):
        response = self._patch(email="kollegin@example.com")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())
        self.assertEqual(self.user.email, "host@example.com")

    def test_an_empty_username_is_refused(self):
        response = self._patch(username="   ")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())
        self.assertEqual(self.user.username, "host")

    def test_an_empty_email_is_refused(self):
        response = self._patch(email="")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    def test_a_name_with_a_space_in_it_is_refused(self):
        """Django's own validator, with its English message replaced."""
        response = self._patch(username="spiel leitung")

        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())

    def test_a_refusal_is_not_english(self):
        """Wording stays free — the assertion is "not English", never a
        sentence. These are the strings the React screen renders, so they are
        copy now rather than a backstop nobody sees."""
        response = self._patch(username="kollegin", email="kollegin@example.com")

        self.assertEqual(response.status_code, 400)
        errors = " ".join(
            " ".join(str(m) for m in messages)
            for messages in response.json().values()
        ).lower()

        for word in ("already", "exists", "please", "in use", "username", "email"):
            self.assertNotIn(word, errors)


class AccountDeleteTests(TempMediaRootMixin, TestCase):
    """The panel can edit an account; DSGVO says it must be able to end one.

    What "delete" means here is settled in game/anon.py and pinned in
    game/tests/test_privacy.py: the row stays, the name goes, running games
    end. These tests are about the way in — the confirm page, the password,
    the logout.
    """

    def setUp(self):
        self.user = _host(first_name="Sebastian")
        self.client.force_login(self.user)

    def _delete(self, password="password123", follow=False):
        with muted():
            return self.client.post(
                DELETE_URL, {"password": password}, follow=follow
            )

    def test_the_way_out_is_reachable_for_a_logged_in_host(self):
        """DSGVO erasure has to be something a host can actually reach.

        It used to be asserted by grepping the profile template for the URL.
        The profile page is React since S13, so the link itself is pinned there
        — `frontend/e2e/host-page.spec.ts` clicks it — and what stays here is
        that the page it leads to answers.

        The status code is the whole assertion on purpose: a content check
        would go green against the login redirect an anonymous request gets.
        """
        response = self.client.get(DELETE_URL)

        self.assertEqual(response.status_code, 200)

    def test_the_confirm_page_needs_a_login(self):
        self.client.logout()

        response = self.client.get(DELETE_URL)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_a_stranger_cannot_post_the_deletion(self):
        self.client.logout()

        response = self.client.post(DELETE_URL, {"password": "password123"})

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.username, "host")

    def test_the_confirm_page_counts_the_running_games(self):
        """The host has to see what pressing this costs the class."""
        with muted():
            create_game_session(self.user, game_name="Laufend")

        response = self.client.get(DELETE_URL)

        self.assertEqual(response.context["running_games"], 1)

    def test_an_ended_game_is_not_counted(self):
        with muted():
            game = create_game_session(self.user, game_name="Fertig")
        GameSession.objects.filter(pk=game.pk).update(
            ended_at=timezone.now(), is_active=False
        )

        response = self.client.get(DELETE_URL)

        self.assertEqual(response.context["running_games"], 0)

    def test_the_confirm_page_is_german(self):
        """The rest of the funnel was translated in 5bfaf66; this page is new."""
        response = self.client.get(DELETE_URL)

        self.assertEqual(response.status_code, 200)
        text = re.sub(r"<[^>]+>", " ", response.content.decode()).lower()

        for word in (" delete ", " password ", " cancel ", " confirm "):
            self.assertNotIn(word, text)

    def test_a_wrong_password_changes_nothing(self):
        response = self._delete(password="falsch")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.username, "host")
        self.assertTrue(self.user.is_active)

    def test_no_password_changes_nothing(self):
        response = self._delete(password="")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.username, "host")

    def test_the_refusal_is_not_english(self):
        response = self._delete(password="falsch")

        errors = " ".join(
            " ".join(messages)
            for messages in response.context["form"].errors.values()
        ).lower()

        for word in ("password", "incorrect", "please", "field", "required"):
            self.assertNotIn(word, errors)

    def test_the_right_password_anonymises_the_account(self):
        self._delete()

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, f"geloescht-{self.user.pk}")
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.email, "")

    def test_the_deletion_ends_the_running_game(self):
        with muted():
            game = create_game_session(self.user, game_name="Laufend")
            GameSession.objects.filter(pk=game.pk).update(is_active=True)

        self._delete()

        game.refresh_from_db()
        self.assertIsNotNone(game.ended_at)
        self.assertEqual(game.end_reason, GameSession.EndReason.HOST)

    def test_it_lands_on_the_goodbye_page(self):
        response = self._delete()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], DELETED_URL)

    def test_the_deletion_logs_you_out(self):
        self._delete()

        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_the_goodbye_page_reads_when_logged_out(self):
        """It is the last thing the account ever sees; it cannot need a login."""
        self.client.logout()

        response = self.client.get(DELETED_URL)

        self.assertEqual(response.status_code, 200)


class HostPageRedirectTests(TempMediaRootMixin, TestCase):
    """The three funnel URLs that became doorways. S13.

    All three keep working because things point at them — the profile page from
    `LOGIN_REDIRECT_URL`, the footer and the app header; the share and delete
    URLs from the host's own game list and from anybody's bookmarks.

    What the pages behind them did is not gone, it moved:

    - the profile's form → `PATCH api/account/`
    - its game list and per-game delete → `GET api/game/` and
      `DELETE api/game/<id>/`
    - the share page → the host lobby, which has shown the game id and the join
      QR on a projector-sized departure board since F4. That one is a deletion
      rather than a port.
    - the delete page's "a running game is refused" →
      `GameSessionDetailView.destroy`, so both doors enforce it.
    """

    def setUp(self):
        self.host = _host()
        with muted():
            self.game = create_game_session(self.host, game_name="Wegwerfspiel")

    def test_the_share_url_goes_to_the_lobby(self):
        self.client.force_login(self.host)

        response = self.client.get(f"/game/{self.game.game_id}/share/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/app/game/{self.game.game_id}/")

    def test_the_delete_url_goes_to_the_host_page(self):
        self.client.force_login(self.host)

        response = self.client.get(f"/game/{self.game.game_id}/delete/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/app/host")

    def test_neither_deletes_anything_by_itself(self):
        """A GET that deletes is the reason the confirm page existed at all."""
        self.client.force_login(self.host)

        self.client.get(f"/game/{self.game.game_id}/delete/")

        self.assertTrue(GameSession.objects.filter(pk=self.game.pk).exists())

    def test_a_visitor_is_sent_to_the_login(self):
        for path in ("share", "delete"):
            with self.subTest(path=path):
                response = self.client.get(f"/game/{self.game.game_id}/{path}/")

                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response["Location"])


class MapPageRedirectTests(TestCase):
    """`/map/list/` and `/map/<pk>/` are doorways into the SPA. S18.

    Both pages were Django's, in English, and the list printed a `description`
    `GameMap` does not have. `/app/maps` is the list now and `/app/maps/<pk>/`
    the detail. The URLs stay because `base.html` names `map-list` in both of
    its menus and a bookmark might name either.
    """

    def setUp(self):
        self.staff = _host(username="staff", is_staff=True)

    def test_the_list_goes_to_the_spa_index(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("map-list"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/app/maps/")

    def test_a_detail_page_goes_to_its_spa_page(self):
        self.client.force_login(self.staff)

        response = self.client.get("/map/7/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/app/maps/7/")

    def test_a_visitor_is_sent_to_the_login(self):
        for path in ("/map/list/", "/map/7/"):
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response["Location"])
