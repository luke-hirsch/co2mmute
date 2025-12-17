from http import cookies
from django.core import signing
from channels.db import database_sync_to_async
from django.conf import settings
from .models import Player


# Centralized cookie constants (single source of truth)
COOKIE_GAME_PREFIX = settings.COOKIE_GAME_PREFIX
COOKIE_GAME_SALT = settings.COOKIE_GAME_SALT
COOKIE_PLAYER_PREFIX = settings.COOKIE_PLAYER_PREFIX
COOKIE_PLAYER_SALT = settings.COOKIE_PLAYER_SALT


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
        # validate game cookie too (we don't need its value but must verify signature)
        _ = unsign(raw_game, settings.COOKIE_GAME_SALT)
    except signing.BadSignature:
        return None, 4401, "bad-signature"

    # DB lookup
    @database_sync_to_async
    def _get_player(game_id_inner, player_id_inner):
        return Player.objects.filter(
            game__game_id=game_id_inner, player_id=player_id_inner
        ).first()

    player = await _get_player(game_id, player_id)
    if not player:
        return None, 4403, "player-not-in-game"

    return player, None, None
