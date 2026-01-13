from channels.db import database_sync_to_async
from channels.auth import get_user
from django.conf import settings
from django.core import signing
from .models import Player, GameSession
from .cookie_utils import get_cookie_from_scope, unsign_value
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Centralized cookie constants (single source of truth)


class HostPlayer:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.player_id = f"host_{user_id}"
        self.name = f"{username} (Host)"
        self.is_muted = False
        self.controlled_by_host = True
        self.joined_at = datetime.now()
        self.user = True


async def resolve_player(scope, game_id: str):
    user = await get_user(scope)

    @database_sync_to_async
    def _check_if_host_and_get_player(user_obj, game_id_inner):
        if not user_obj or not user_obj.is_authenticated:
            logger.debug("User not authenticated or None")
            return None

        game_session = (
            GameSession.objects.filter(game_id=game_id_inner, game_host=user_obj)
            .select_related()
            .first()
        )

        if not game_session:
            return None

        return HostPlayer(user_obj.id, user_obj.username)

    host_player = await _check_if_host_and_get_player(user, game_id)
    if host_player:
        return host_player, None, None, True

    player_cookie_name = f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"
    game_cookie_name = f"{settings.COOKIE_GAME_PREFIX}{game_id}"

    raw_player = get_cookie_from_scope(scope, player_cookie_name)
    raw_game = get_cookie_from_scope(scope, game_cookie_name)

    if not raw_player or not raw_game:
        logger.warning(
            f"Missing cookies for game {game_id}: player={bool(raw_player)}, game={bool(raw_game)}"
        )
        return None, 4401, "missing-cookie", False

    try:
        player_id = unsign_value(raw_player, settings.COOKIE_PLAYER_SALT)
        game_cookie_value = unsign_value(raw_game, settings.COOKIE_GAME_SALT)
        if ":" not in game_cookie_value:
            logger.warning(f"Malformed game cookie for {game_id}")
            return None, 4401, "malformed-game-cookie", False
        cookie_game_id, _ = game_cookie_value.split(":", 1)
        if cookie_game_id != game_id:
            logger.warning(
                f"Game ID mismatch for {game_id}: cookie has {cookie_game_id}"
            )
            return None, 4401, "game-id-mismatch", False
    except signing.BadSignature as e:
        logger.warning(f"Bad signature for game {game_id}: {e}")
        return None, 4401, "bad-signature", False

    # DB lookup with game state validation
    @database_sync_to_async
    def _get_player_with_game_check(game_id_inner, player_id_inner):
        player = (
            Player.objects.filter(
                game__game_id=game_id_inner, player_id=player_id_inner
            )
            .select_related("game")
            .first()
        )

        if not player:
            logger.warning(
                f"Player not found: game_id={game_id_inner}, player_id={player_id_inner}"
            )
            # Log all players in this game for debugging
            all_players = Player.objects.filter(
                game__game_id=game_id_inner
            ).values_list("player_id", "name")
            logger.debug(f"Players in game {game_id_inner}: {list(all_players)}")
            return None, "player-not-found"

        game = player.game
        if game.ended_at is not None:
            return None, "game-ended"

        return player, None

    player, error = await _get_player_with_game_check(game_id, player_id)
    if error:
        logger.warning(
            f"Player check failed for game {game_id}, player {player_id}: {error}"
        )
        if error == "player-not-found":
            return None, 4403, "player-not-in-game", False
        elif error == "game-ended":
            return None, 4403, "game-ended", False
        else:
            return None, 4403, "game-invalid-state", False

    return player, None, None, False
