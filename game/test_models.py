from django.test import TestCase

from .models import Session, Player, Round, PlayerMove
from django.contrib.auth.models import User


class SessionModelTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="sessioncreator",
            password="securepassword",
        )
        self.session = Session.objects.create(session_status="active", created_by=user)

    def test_session_str(self):
        session = Session.objects.get(id=self.session.pk)
        self.assertEqual(
            str(session),
            f"Session {self.session.session_id} ({self.session.session_status})",
        )


class PlayerModelTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="playeruser",
            password="securepassword",
        )
        session = Session.objects.create(session_status="active", created_by=user)
        self.player = Player.objects.create(user=user, session=session, score=10)

    def test_player_str(self):
        player = Player.objects.get(id=self.player.pk)
        self.assertEqual(
            str(player),
            f"Player {self.player.user.username} in Session {self.player.session.session_id} with score {self.player.score}",
        )


class RoundModelTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="roundcreator",
            password="securepassword",
        )
        session = Session.objects.create(session_status="active", created_by=user)
        self.round = Round.objects.create(
            session=session, round_number=1, result="heads"
        )

    def test_round_str(self):
        round_instance = Round.objects.get(id=self.round.pk)
        self.assertEqual(
            str(round_instance),
            f"Round {self.round.round_number} in Session {self.round.session.session_id} with result {self.round.result}",
        )


class PlayerMoveModelTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="movemaker",
            password="securepassword",
        )
        session = Session.objects.create(session_status="active", created_by=user)
        player = Player.objects.create(user=user, session=session, score=0)
        round_instance = Round.objects.create(session=session, round_number=1)
        self.player_move = PlayerMove.objects.create(
            player=player,
            round=round_instance,
            move_choice="rock",
        )

    def test_player_move_str(self):
        player_move = PlayerMove.objects.get(id=self.player_move.pk)
        self.assertEqual(
            str(player_move),
            f"Move by {self.player_move.player.user.username} at {self.player_move.timestamp}",
        )
