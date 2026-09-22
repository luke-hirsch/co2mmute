from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

PROFILE_URL = "/accounts/profile/"


def _host(username="host", email="host@example.com", **extra):
    return User.objects.create_user(
        username=username,
        email=email,
        password="password123",
        **extra,
    )


class ProfilePanelTests(TestCase):
    """The panel stops promising and starts working.

    `/accounts/profile/` carried a card headed "Profil bearbeiten" whose body
    read "noch nicht implementiert. Demnächst!" — a to-do list rendered to the
    one page every host sees after logging in.
    """

    def setUp(self):
        self.user = _host(first_name="Sebastian")
        self.client.force_login(self.user)

    def test_the_page_offers_a_form(self):
        response = self.client.get(PROFILE_URL)

        form = response.context["form"]

        self.assertEqual(
            sorted(form.fields), ["email", "first_name", "username"]
        )

    def test_the_form_starts_on_the_current_values(self):
        response = self.client.get(PROFILE_URL)

        form = response.context["form"]

        self.assertEqual(form.initial["username"], "host")
        self.assertEqual(form.initial["email"], "host@example.com")
        self.assertEqual(form.initial["first_name"], "Sebastian")

    def test_nothing_is_promised_for_later_any_more(self):
        """The card said what it could not do. Either it works or it goes."""
        response = self.client.get(PROFILE_URL)

        promises = [
            line.strip()
            for line in response.content.decode().splitlines()
            if "noch nicht implementiert" in line or "Demnächst" in line
        ]

        self.assertEqual(promises, [])

    def test_the_games_list_is_still_there(self):
        """The view grew a form; it must not lose what it already rendered."""
        response = self.client.get(PROFILE_URL)

        self.assertIn("game_sessions", response.context)
        self.assertIn("change_password_url", response.context)
        self.assertIn("create_session_url", response.context)

    def test_a_stranger_is_sent_to_the_login(self):
        self.client.logout()

        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_a_stranger_cannot_post_either(self):
        """LoginRequiredMixin has to cover the new verb, not just the old one."""
        self.client.logout()

        response = self.client.post(PROFILE_URL, {"username": "eindringling"})

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertFalse(User.objects.filter(username="eindringling").exists())


class ProfileEditTests(TestCase):
    def setUp(self):
        self.user = _host(first_name="Sebastian")
        self.client.force_login(self.user)

    def _post(self, follow=False, **overrides):
        data = {
            "username": "host",
            "email": "host@example.com",
            "first_name": "Sebastian",
        }
        data.update(overrides)
        return self.client.post(PROFILE_URL, data, follow=follow)

    def test_the_display_name_can_change(self):
        response = self._post(first_name="Basti")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.first_name, "Basti")

    def test_the_username_can_change(self):
        self._post(username="spielleitung")

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "spielleitung")

    def test_the_email_can_change(self):
        self._post(email="neu@example.com")

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "neu@example.com")

    def test_a_save_lands_back_on_the_profile(self):
        response = self._post(first_name="Basti")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], PROFILE_URL)

    def test_a_save_says_so(self):
        """base.html renders no messages block, so the page must carry one."""
        response = self._post(first_name="Basti", follow=True)

        self.assertEqual(response.status_code, 200)
        messages = [str(m) for m in response.context["messages"]]

        self.assertEqual(len(messages), 1)
        self.assertIn(messages[0], response.content.decode())

    def test_changing_the_username_does_not_log_you_out(self):
        """Session auth hashes the password, not the name — pin it anyway."""
        self._post(username="spielleitung")

        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, 200)

    def test_whitespace_around_a_value_is_dropped(self):
        self._post(username="  spielleitung  ")

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "spielleitung")


class ProfileUniquenessTests(TestCase):
    """The trap: an update is not a signup.

    `SignupForm.clean_username` asks whether *anybody* holds the name. On an
    update the answer is yes — you do. Saving the form without touching the
    name has to work, or the form refuses every edit to any other field.
    """

    def setUp(self):
        self.user = _host(first_name="Sebastian")
        self.other = _host(username="kollegin", email="kollegin@example.com")
        self.client.force_login(self.user)

    def _post(self, follow=False, **overrides):
        data = {
            "username": "host",
            "email": "host@example.com",
            "first_name": "Sebastian",
        }
        data.update(overrides)
        return self.client.post(PROFILE_URL, data, follow=follow)

    def test_keeping_your_own_username_is_not_a_conflict(self):
        response = self._post(first_name="Basti")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.first_name, "Basti")

    def test_keeping_your_own_email_is_not_a_conflict(self):
        response = self._post(username="spielleitung")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.username, "spielleitung")

    def test_somebody_elses_username_is_refused(self):
        response = self._post(username="kollegin")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(self.user.username, "host")

    def test_somebody_elses_username_is_refused_in_any_case(self):
        response = self._post(username="Kollegin")

        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)

    def test_somebody_elses_email_is_refused(self):
        response = self._post(email="kollegin@example.com")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(self.user.email, "host@example.com")

    def test_an_empty_username_is_refused(self):
        response = self._post(username="   ")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(self.user.username, "host")

    def test_an_empty_email_is_refused(self):
        response = self._post(email="")

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)

    def test_a_refusal_is_not_english(self):
        """The funnel detector covers the rendered page; this covers the form.

        Wording stays free — the assertion is "not English", never a sentence.
        """
        response = self._post(username="kollegin", email="kollegin@example.com")

        self.assertEqual(response.status_code, 200)
        errors = " ".join(
            " ".join(messages) for messages in response.context["form"].errors.values()
        ).lower()

        for word in ("already", "exists", "please", "in use", "username", "email"):
            self.assertNotIn(word, errors)
