import logging

from channels.auth import get_user
from channels.db import database_sync_to_async
from co2mmute.utils import get_cookie_from_scope
from django.conf import settings
from django.utils.timezone import now

from game.auth import has_game_access, resolve_player_id

from .models import GameSession, Player

logger = logging.getLogger(__name__)

# Centralized cookie constants (single source of truth)


class HostPlayer:
    def __init__(self, user_obj, game):
        self.user_id = user_obj.pk
        self.player_id = f"{user_obj.username[0:5]}"
        self.name = f"{user_obj.username} (Host)"
        self.is_muted = False
        self.controlled_by_host = True
        self.joined_at = now()
        self.user = user_obj
        self.game = game


async def resolve_player(scope, game_id: str):
    # get_user needs scope["session"], which only exists behind SessionMiddleware.
    # Guard it rather than assume: the routing wraps the consumer, but a scope
    # built by hand (tests, or any future non-HTTP entry point) does not.
    user = None
    if "session" in scope:
        user = await get_user(scope)

    @database_sync_to_async
    def _get_host_player(user_obj, game_id_inner):
        if not user_obj or not user_obj.is_authenticated:
            return None
        game_session = GameSession.objects.filter(
            game_id=game_id_inner, game_host=user_obj
        ).first()
        if not game_session:
            return None
        return HostPlayer(user_obj, game_session)

    host_player = await _get_host_player(user, game_id)
    if host_player:
        return host_player, None, None, True

    cookies = {
        name: get_cookie_from_scope(scope, name)
        for name in (
            f"{settings.COOKIE_GAME_PREFIX}{game_id}",
            f"{settings.COOKIE_PLAYER_PREFIX}{game_id}",
        )
    }
    cookies = {k: v for k, v in cookies.items() if v}

    if not has_game_access(cookies, game_id):
        return None, 4401, "no-game-access", False

    player_id = resolve_player_id(cookies, game_id)
    if not player_id:
        return None, 4401, "no-player-cookie", False

    @database_sync_to_async
    def _get_player(game_id_inner, player_id_inner):
        player = (
            Player.objects.filter(
                game__game_id=game_id_inner,
                player_id=player_id_inner,
                left_at__isnull=True,
            )
            .select_related("game")
            .first()
        )
        if not player:
            # Never log player_id lists here — the names come with them.
            # CLAUDE.md: player names must not reach logs. Roadmap.md 1.3.
            return None, "player-not-found"
        if player.game.ended_at is not None:
            return None, "game-ended"
        return player, None

    player, error = await _get_player(game_id, player_id)
    if error == "player-not-found":
        return None, 4403, "player-not-in-game", False
    if error == "game-ended":
        return None, 4403, "game-ended", False

    return player, None, None, False
