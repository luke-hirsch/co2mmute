from http import cookies
from django.core import signing
from channels.db import database_sync_to_async
from django.conf import settings
from .models import Player


# Centralized cookie constants (single source of truth)


def get_cookie(scope, name: str):
    header_bytes = dict(scope.get("headers", {})).get(b"cookie", b"")
    if not header_bytes:
        return None
    jar = cookies.SimpleCookie()
    jar.load(header_bytes.decode("utf-8"))
    morsel = jar.get(name)
    return morsel.value if morsel else None


def unsign(value: str, salt: str):
    # will raise signing.BadSignature if invalid
    return signing.loads(value, salt=salt)


async def resolve_player(scope, game_id: str):
    # Read raw cookies
    player_cookie_name = f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"
    game_cookie_name = f"{settings.COOKIE_GAME_PREFIX}{game_id}"

    raw_player = get_cookie(scope, player_cookie_name)
    raw_game = get_cookie(scope, game_cookie_name)

    if not raw_player or not raw_game:
        return None, 4401, "missing-cookie"

    try:
        player_id = unsign(raw_player, settings.COOKIE_PLAYER_SALT)
        # validate game cookie and extract embedded game_id
        game_cookie_value = unsign(raw_game, settings.COOKIE_GAME_SALT)
        # Format is "game_id:token" - validate game_id matches
        if ":" not in game_cookie_value:
            return None, 4401, "malformed-game-cookie"
        cookie_game_id, _ = game_cookie_value.split(":", 1)
        if cookie_game_id != game_id:
            return None, 4401, "game-id-mismatch"
    except signing.BadSignature:
        return None, 4401, "bad-signature"

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
            return None, "player-not-found"

        # Validate game is in an acceptable state for WebSocket connections
        # Reject if game has ended (ended_at is not None)
        game = player.game
        if game.ended_at is not None:
            return None, "game-ended"

        return player, None

    player, error = await _get_player_with_game_check(game_id, player_id)
    if error:
        if error == "player-not-found":
            return None, 4403, "player-not-in-game"
        elif error == "game-ended":
            return None, 4403, "game-ended"
        else:
            return None, 4403, "game-invalid-state"

    return player, None, None
