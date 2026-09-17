import importlib
import os
import shutil
import tempfile
import uuid
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from game.models import GameSession, Player

from ._helpers import (
    TEST_BACKENDS,
    TempMediaRootMixin,
    create_form_data,
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
        # Not isupper(): an all-digit hex id is valid and has no cased letters.
        self.assertEqual(game.game_id, game.game_id.upper())
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
    """Player.objects.host_rows() / without_host_rows() / playing().

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

    def test_playing_leaves_out_the_host_row_and_players_who_left(self):
        """The one counting rule. Rounds, votes, stats acks and the lobby's
        max_players all wait for, or count, exactly these seats."""
        with muted():
            Player.objects.create(game=self.game, name="Weg", left_at=timezone.now())

        self.assertCountEqual(
            Player.objects.filter(game=self.game).playing(),
            [self.player, self.at_the_host_machine],
        )

    def test_playing_is_scoped_by_the_filter_before_it(self):
        with muted():
            elsewhere = Player.objects.create(game=self.other_game, name="Anderswo")

        self.assertNotIn(elsewhere, Player.objects.filter(game=self.game).playing())
        self.assertIn(elsewhere, Player.objects.playing())

    def test_the_create_view_makes_a_host_row_that_is_not_host_controlled(self):
        """From 1.6 on, controlled_by_host means "played at the host machine".
        The host's own row is found by its account."""
        self.client.force_login(self.host)

        with muted():
            response = self.client.post(
                "/game/create/", create_form_data(game_name="Frisch")
            )

        self.assertEqual(response.status_code, 302)
        game = GameSession.objects.get(game_name="Frisch")
        host_row = Player.objects.filter(game=game).host_rows().get()
        self.assertFalse(host_row.controlled_by_host)

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


def uuid_draws(*prefixes):
    """A uuid4 stand-in: these hex prefixes first, then real ones."""
    real_uuid4 = uuid.uuid4
    queue = [uuid.UUID(prefix.ljust(32, "0")) for prefix in prefixes]
    return lambda: queue.pop(0) if queue else real_uuid4()


@override_settings(**TEST_BACKENDS)
class PlayerIdTests(TempMediaRootMixin, TestCase):
    """player_id is what the player cookie names, so it must name one row.
    Roadmap.md 1.6; 1.7 hands out new ids and relies on it."""

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host)
            self.other_game = create_game_session(self.host, game_name="Anderes")
            self.mia = Player.objects.create(game=self.game, name="Mia")
        Player.objects.filter(pk=self.mia.pk).update(player_id="P-ABCD")
        self.mia.refresh_from_db()

    def test_a_new_id_is_p_and_four_hex_characters(self):
        with muted():
            jan = Player.objects.create(game=self.game, name="Jan")

        self.assertRegex(jan.player_id, r"^P-[0-9A-F]{4}$")

    def test_the_generator_skips_an_id_the_game_already_has(self):
        """It compared "ABCD" with the stored "P-ABCD" and never saw a
        collision."""
        seat = Player(game=self.game, name="Neu")

        with patch("game.models.uuid.uuid4", side_effect=uuid_draws("abcd", "beef")):
            self.assertEqual(seat.generate_unique_player_id(), "P-BEEF")

    def test_a_new_player_never_gets_a_taken_id(self):
        with patch(
            "game.models.uuid.uuid4", side_effect=uuid_draws("abcd", "beef")
        ), muted():
            seat = Player.objects.create(game=self.game, name="Neu")

        self.assertEqual(seat.player_id, "P-BEEF")

    def test_an_id_taken_in_another_game_is_fine(self):
        """Ids are unique per game, not overall."""
        seat = Player(game=self.other_game, name="Anderswo")

        with patch("game.models.uuid.uuid4", side_effect=uuid_draws("abcd")):
            self.assertEqual(seat.generate_unique_player_id(), "P-ABCD")

    def test_the_database_refuses_an_id_twice_in_one_game(self):
        with muted():
            jan = Player.objects.create(game=self.game, name="Jan")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Player.objects.filter(pk=jan.pk).update(player_id="P-ABCD")

    def test_the_database_allows_the_same_id_in_two_games(self):
        """A guard, green from the start."""
        with muted():
            elsewhere = Player.objects.create(game=self.other_game, name="Jan")

        Player.objects.filter(pk=elsewhere.pk).update(player_id="P-ABCD")


HOST_ROW_MIGRATION = "game.migrations.0008_host_rows_and_unique_player_ids"


@override_settings(**TEST_BACKENDS)
class HostRowMigrationTests(TempMediaRootMixin, TestCase):
    """0008 turns controlled_by_host off on the host rows that already exist.

    Its functions are called directly with the app registry. They only use
    apps.get_model(), so the real models stand in for the historical ones.
    """

    def setUp(self):
        self.host = create_host()
        with muted():
            self.game = create_game_session(self.host)
            # A host row the way GameSessionCreateView made it before 1.6.
            self.host_row = Player.objects.create(
                game=self.game, name="Host", user=self.host, controlled_by_host=True
            )
            self.seat = Player.objects.create(
                game=self.game, name="Ohne Handy", controlled_by_host=True
            )
            self.student = Player.objects.create(game=self.game, name="Mia")

    def migration(self):
        return importlib.import_module(HOST_ROW_MIGRATION)

    def test_host_rows_lose_the_flag(self):
        self.migration().host_rows_are_not_host_controlled(apps, None)

        self.host_row.refresh_from_db()
        self.assertFalse(self.host_row.controlled_by_host)

    def test_other_rows_keep_theirs(self):
        self.migration().host_rows_are_not_host_controlled(apps, None)

        self.seat.refresh_from_db()
        self.student.refresh_from_db()
        self.assertTrue(self.seat.controlled_by_host)
        self.assertFalse(self.student.controlled_by_host)

    def test_it_can_be_reversed(self):
        module = self.migration()
        module.host_rows_are_not_host_controlled(apps, None)

        module.host_rows_are_host_controlled(apps, None)

        self.host_row.refresh_from_db()
        self.seat.refresh_from_db()
        self.assertTrue(self.host_row.controlled_by_host)
        self.assertTrue(self.seat.controlled_by_host)

    def test_the_duplicate_fix_leaves_unique_ids_alone(self):
        ids_before = set(Player.objects.values_list("pk", "player_id"))

        self.migration().give_duplicate_player_ids_a_new_one(apps, None)

        self.assertEqual(set(Player.objects.values_list("pk", "player_id")), ids_before)
