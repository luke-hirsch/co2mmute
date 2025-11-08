from django.test import TestCase
from django.contrib.auth.models import User


class SessionCreateViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="securepassword",
        )

    def test_session_create_view_get_unauthenticated(self):
        response_without_login = self.client.get("/game/sessions/create/")
        self.assertEqual(response_without_login.status_code, 302)

    def test_session_create_view_get_authenticated(self):
        self.client.login(username="testuser", password="securepassword")
        response_with_login = self.client.get("/game/sessions/create/")
        self.assertEqual(response_with_login.status_code, 200)
