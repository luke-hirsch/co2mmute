import logging

from rest_framework.permissions import BasePermission

from .auth import has_game_access, resolve_player_id
from .cache import get_cached_game_session
from .models import Player

logger = logging.getLogger(__name__)


def _is_host(request, game_id: str) -> bool:
    if not request.user.is_authenticated:
        return False
    session = get_cached_game_session(game_id)
    return bool(session and session.game_host == request.user)


class HasGameAccess(BasePermission):
    message = "You do not have access to this game session."

    def has_permission(self, request, view):
        game_id = view.kwargs.get("game_id")
        if not game_id:
            return False
        if _is_host(request, game_id):
            return True
        return has_game_access(request.COOKIES, game_id)


class IsPlayerInGame(BasePermission):
    """The cookie's player is in this game — and, where the URL names a player,
    it is that player.

    PlayerMoveView and GetYourOwnGame take player_id from the URL. Without the
    comparison any player could act as any other player in the same game, and
    every player_id is in the lobby roster.
    """

    message = "You are not a player in this game session."

    def has_permission(self, request, view):
        game_id = view.kwargs.get("game_id")
        if not game_id:
            return False

        player_id = resolve_player_id(request.COOKIES, game_id)
        if not player_id:
            return False

        url_player_id = view.kwargs.get("player_id")
        if url_player_id and url_player_id != player_id:
            return False

        return Player.objects.filter(
            game__game_id=game_id, player_id=player_id, left_at__isnull=True
        ).exists()


class CanDeleteOwnPlayer(BasePermission):
    message = "You can only delete your own player record."

    def has_permission(self, request, view):
        if request.method != "DELETE":
            return True

        game_id = view.kwargs.get("game_id")
        player_id = view.kwargs.get("player_id")
        if not game_id or not player_id:
            return False

        if _is_host(request, game_id):
            return True

        return resolve_player_id(request.COOKIES, game_id) == player_id


class IsGameHost(BasePermission):
    message = "Only the game host can perform this action."

    def has_permission(self, request, view):
        game_id = view.kwargs.get("game_id")
        if not game_id:
            return False
        return _is_host(request, game_id)
