from django.conf import settings
from django.core import signing
from rest_framework.permissions import BasePermission

from .cache import get_cached_game_session
from .models import Player


class HasGameAccess(BasePermission):
    message = "You do not have access to this game session."

    def has_permission(self, request, view):
        game_id = view.kwargs.get("game_id")
        if not game_id:
            return False

        if request.user.is_authenticated:
            session = get_cached_game_session(game_id)
            if session and session.game_host_id == request.user.id:
                return True

        tokens = request.session.get("game_access_tokens") or {}
        session_token = tokens.get(game_id)
        if not session_token:
            return False

        cookie_name = f"{settings.COOKIE_GAME_PREFIX}{game_id}"
        try:
            cookie_value = request.get_signed_cookie(
                cookie_name, salt=settings.COOKIE_GAME_SALT
            )
            # Extract embedded game_id and token from "game_id:token" format
            if ":" not in cookie_value:
                return False
            cookie_game_id, cookie_token = cookie_value.split(":", 1)
            # Verify game_id matches and token matches
            return cookie_game_id == game_id and cookie_token == session_token
        except (KeyError, signing.BadSignature):
            return False


class IsPlayerInGame(BasePermission):
    message = "You are not a player in this game session."

    def has_permission(self, request, view):
        game_id = view.kwargs.get("game_id")
        if not game_id:
            return False

        cookie_name = f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"

        try:
            player_id = request.get_signed_cookie(
                cookie_name, salt=settings.COOKIE_PLAYER_SALT
            )
        except (KeyError, signing.BadSignature):
            return False

        # Verify that player exists AND belongs to that game
        return Player.objects.filter(
            game__game_id=game_id, player_id=player_id
        ).exists()
