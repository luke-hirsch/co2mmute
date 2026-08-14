from asgiref.sync import async_to_sync

from django.test import TestCase
from django.core import signing

from django.conf import settings

from django.contrib.auth import get_user_model


from game.models import GameSession, Player
from game.ws_auth import resolve_player


class WsAuthTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="host", password="pass")

        self.game = GameSession.objects.create(
            game_host=self.user,
            game_name="Test",
            max_players=4,
            max_rounds=4,
            max_CO2_level=100,
            agent_per_player=1,
        )
        self.player = Player.objects.create(game=self.game, name="Tester")

    def _make_scope_with_cookies(self, game_id, player_id):
        player_cookie_name = f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"
        game_cookie_name = f"{settings.COOKIE_GAME_PREFIX}{game_id}"

        player_signer = signing.TimestampSigner(salt=settings.COOKIE_PLAYER_SALT)
        signed_player = player_signer.sign(str(player_id))

        game_cookie_content = f"{game_id}:token"
        game_signer = signing.TimestampSigner(salt=settings.COOKIE_GAME_SALT)
        signed_game = game_signer.sign(game_cookie_content)

        cookie_header = (
            f"{player_cookie_name}={signed_player}; {game_cookie_name}={signed_game}"
        )
        scope = {"headers": [(b"cookie", cookie_header.encode())]}
        return scope

    def test_resolve_player_success(self):
        scope = self._make_scope_with_cookies(self.game.game_id, self.player.player_id)
        player, close_code, reason, is_host = async_to_sync(resolve_player)(
            scope, self.game.game_id
        )
        self.assertIsNone(close_code)
        self.assertIsNone(reason)
        self.assertIsNotNone(player)
        self.assertFalse(is_host)  # Regular player, not host
        if player:
            self.assertEqual(player.player_id, self.player.player_id)

    def test_resolve_player_missing_cookie(self):
        scope = {"headers": []}
        player, close_code, reason, is_host = async_to_sync(resolve_player)(
            scope, self.game.game_id
        )
        self.assertIsNone(player)
        self.assertEqual(close_code, 4401)
