from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Session
from django.urls import reverse


class SessionTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.validPassword = "ValidPass1!"
        self.postTestSessionName = "Post Test Session"
        self.sessionUser1 = user_model.objects.create_user(
            username="SessionCreator1",
            email="session1@example.com",
            password=self.validPassword,
        )
        self.sessionUser2 = user_model.objects.create_user(
            username="SessionCreator2",
            email="session2@example.com",
            password=self.validPassword,
        )
        self.session1 = Session.objects.create(
            created_by=self.sessionUser1,
            session_password="ValidSessionPass1!",
        )
        self.session2 = Session.objects.create(
            created_by=self.sessionUser2, session_name="Session without password"
        )

    def test_session_creation(self):
        self.assertEqual(self.session1.created_by, self.sessionUser1)
        self.assertEqual(self.session1.session_password, "ValidSessionPass1!")
        self.assertEqual(self.session2.created_by, self.sessionUser2)
        self.assertIsNone(self.session2.session_password)

    def test_session_form_login_required(self):
        response1 = self.client.get(reverse("session_create"))
        self.assertEqual(response1.status_code, 302)

    def test_session_form_logged_in(self):
        self.client.login(
            username=self.sessionUser1.username, password=self.validPassword
        )
        response3 = self.client.get(reverse("session_create"))
        self.assertEqual(response3.status_code, 200)

    def test_session_create_session(self):
        self.client.login(
            username=self.sessionUser1.username, password=self.validPassword
        )
        response = self.client.post(
            reverse("session_create"),
            {
                "session_name": self.postTestSessionName,
                "session_password": "AnotherValidPass1!",
                "max_players": 4,
                "max_agents": 3,
            },
        )
        self.assertEqual(response.status_code, 302)
        created_session = Session.objects.filter(
            created_by=self.sessionUser1, session_name=self.postTestSessionName
        )
        self.assertEqual(len(created_session), 1)
        self.assertIsNotNone(created_session)
        created_session = created_session[0]
        self.assertEqual(created_session.max_players, 4)
        self.assertEqual(created_session.max_agents, 3)
        self.assertEqual(created_session.session_name, self.postTestSessionName)

    def test_listview_sessions(self):
        self.client.login(
            username=self.sessionUser1.username, password=self.validPassword
        )
        response = self.client.get(reverse("session_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.sessionUser1.username)
        self.assertNotContains(response, self.sessionUser2.username)
