from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class IndexViewTest(TestCase):
    def test_session_view(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


class AuthViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.password = "ValidPass1!"
        self.user = user_model.objects.create_user(
            username="roundcreator",
            email="roundcreator@example.com",
            password=self.password,
        )

    def test_login_page_accessible(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("login_form", response.context)
        self.assertIn("signup_form", response.context)

    def test_existing_user_can_login_with_username(self):
        response = self.client.post(
            reverse("login"),
            {
                "mode": "login",
                "username": self.user.username,
                "password": self.password,
            },
        )
        self.assertRedirects(response, reverse("index"))

    def test_existing_user_can_login_with_email(self):
        response = self.client.post(
            reverse("login"),
            {
                "mode": "login",
                "username": self.user.email,
                "password": self.password,
            },
        )
        self.assertRedirects(response, reverse("index"))

    def test_signup_rejects_password_failing_validators(self):
        user_model = get_user_model()
        response = self.client.post(
            reverse("login"),
            {
                "mode": "signup",
                "username": "newplayer",
                "email": "newplayer@example.com",
                "password1": "Validpass!",
                "password2": "Validpass!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(user_model.objects.filter(username="newplayer").exists())
        form = response.context["signup_form"]
        combined_errors = form.errors.get("password1", []) + form.errors.get(
            "password2", []
        )
        self.assertTrue(any("numeric digit" in error for error in combined_errors))

    def test_successful_signup_creates_user_and_logs_in(self):
        user_model = get_user_model()
        response = self.client.post(
            reverse("login"),
            {
                "mode": "signup",
                "username": "permanentplayer",
                "email": "permanent@example.com",
                "password1": "Str0ngPass!",
                "password2": "Str0ngPass!",
            },
        )
        self.assertRedirects(response, reverse("index"))

        user = user_model.objects.get(username="permanentplayer")
        self.assertEqual(user.email, "permanent@example.com")
        self.assertTrue(user.has_usable_password())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
