import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from game.models import GameSession, Player

from ._helpers import (
    TEST_BACKENDS,
    TempMediaRootMixin,
    create_game_session,
    create_host,
    muted,
)


class GameSessionModelTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temp_media_root = tempfile.mkdtemp(prefix="co2mmute-tests-")
        cls._override = override_settings(MEDIA_ROOT=cls.temp_media_root)
        cls._override.enable()
        cls.user = get_user_model().objects.create_user(
            username="host", email="host@example.com", password="password123"
        )

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls.temp_media_root, ignore_errors=True)
        super().tearDownClass()

    def _create_game_session(self, **overrides):
        defaults = {
            "game_host": self.user,
            "game_name": overrides.get("game_name", "Test Game"),
            "max_players": overrides.get("max_players", 6),
            "max_rounds": overrides.get("max_rounds", 4),
            "max_CO2_level": overrides.get("max_CO2_level", 100),
            "agent_per_player": overrides.get("agent_per_player", 1),
        }
        defaults.update(overrides)
        return GameSession.objects.create(**defaults)

    def test_create_game_generates_id_and_qr_code(self):
        game = self._create_game_session()

        self.assertEqual(len(game.game_id), 6)
        self.assertTrue(game.game_id.isupper())
        self.assertTrue(game.game_qr_code.name.startswith("qr_codes/"))
        self.assertTrue(os.path.exists(game.game_qr_code.path))

    def test_read_game_returns_expected_instance(self):
        game = self._create_game_session(game_name="Retrieve Game")

        fetched = GameSession.objects.get(pk=game.pk)
        self.assertEqual(fetched.game_name, "Retrieve Game")
        self.assertEqual(fetched.game_id, game.game_id)
        self.assertEqual(fetched.game_host, self.user)

    def test_update_game_preserves_id_and_refreshes_fields(self):
        game = self._create_game_session()
        original_id = game.game_id
        original_updated_at = game.updated_at

        game.game_name = "Updated Game"
        game.max_players = 8
        game.save()
        game.refresh_from_db()

        self.assertEqual(game.game_id, original_id)
        self.assertEqual(game.game_name, "Updated Game")
        self.assertEqual(game.max_players, 8)
        self.assertNotEqual(game.updated_at, original_updated_at)

    def test_delete_game_removes_record_and_qr_code(self):
        game = self._create_game_session()
        qr_path = game.game_qr_code.path

        game.delete()

        self.assertFalse(GameSession.objects.filter(pk=game.pk).exists())
        self.assertFalse(os.path.exists(qr_path))

    def test_saving_with_existing_qr_code_does_not_generate_new_one(self):
        custom_qr = ContentFile(b"custom image bytes", name="custom.png")
        game = self._create_game_session(game_qr_code=custom_qr)
        original_name = game.game_qr_code.name

        game.game_name = "Custom QR Game"
        game.save()
        game.refresh_from_db()

        self.assertEqual(game.game_qr_code.name, original_name)


@override_settings(**TEST_BACKENDS)
class PlayerHostRowTests(TempMediaRootMixin, TestCase):
    """Player.objects.host_rows() / without_host_rows().

    GameSessionCreateView gives the host a Player row of their own. What marks it
    is the account link (user == game.game_host), not controlled_by_host:
    Roadmap.md 1.6 gives controlled_by_host its literal meaning — a student
    playing on the host machine — and those rows are players like any other.
    """

    def setUp(self):
        self.host = create_host()
        self.other_host = create_host(username="other-host")
        with muted():
            self.game = create_game_session(self.host)
            self.other_game = create_game_session(self.other_host)
            self.host_row = Player.objects.create(
                game=self.game,
                user=self.host,
                name="Host",
                controlled_by_host=True,
            )
            self.player = Player.objects.create(game=self.game, name="Mia")
            self.at_the_host_machine = Player.objects.create(
                game=self.game, name="Ohne Handy", controlled_by_host=True
            )

    def test_host_rows_finds_exactly_the_hosts_own_row(self):
        self.assertEqual(
            list(Player.objects.filter(game=self.game).host_rows()), [self.host_row]
        )

    def test_without_host_rows_keeps_players_and_host_controlled_players(self):
        self.assertCountEqual(
            Player.objects.filter(game=self.game).without_host_rows(),
            [self.player, self.at_the_host_machine],
        )

    def test_a_host_account_is_only_the_host_in_its_own_game(self):
        """A host account holding a row in someone else's game is a player
        there. Nothing sets Player.user on a join today — this pins the rule to
        the game's host rather than to "has an account"."""
        with muted():
            visiting = Player.objects.create(
                game=self.other_game, user=self.host, name="Zu Besuch"
            )

        self.assertNotIn(visiting, Player.objects.host_rows())
        self.assertIn(visiting, Player.objects.without_host_rows())
