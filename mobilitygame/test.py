from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class IndexViewTest(TestCase):
    def setUp(self):
        pass

    def test_sesion_view(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


class LoginViewTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="roundcreator",
            password="securepassword",
        )

    def test_login_page_accessible(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_guest_login_creates_user_without_password(self):
        user_model = get_user_model()
        self.client.logout()

        response = self.client.post(
            reverse("login"),
            {"username": "guestplayer"},
        )
        self.assertEqual(response.status_code, 302)

        user = user_model.objects.get(username="guestplayer")
        self.assertFalse(user.has_usable_password())

    def test_existing_user_can_login_with_password(self):
        self.client.logout()
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": "securepassword"},
        )
        self.assertEqual(response.status_code, 302)

    def test_new_user_requires_email_when_password_provided(self):
        user_model = get_user_model()
        self.client.logout()

        response = self.client.post(
            reverse("login"),
            {"username": "newplayer", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(user_model.objects.filter(username="newplayer").exists())
        self.assertIn(
            "Bitte geben Sie eine E-Mail-Adresse an, um ein neues Konto zu erstellen.",
            response.context["form"].non_field_errors(),
        )

    def test_create_permanent_user_with_email(self):
        user_model = get_user_model()
        self.client.logout()

        response = self.client.post(
            reverse("login"),
            {
                "username": "permanentplayer",
                "password": "S3cur3Pass!",
                "email": "permanent@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)

        user = user_model.objects.get(username="permanentplayer")
        self.assertEqual(user.email, "permanent@example.com")
        self.assertTrue(user.has_usable_password())
