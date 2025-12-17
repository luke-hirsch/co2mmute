from django.conf import settings
from django.core import signing
from rest_framework.permissions import BasePermission

from .models import GameSession, Player


class HasGameAccess(BasePermission):
    message = "You do not have access to this game session."

    cookie_prefix = settings.COOKIE_GAME_PREFIX
    cookie_salt = settings.COOKIE_GAME_SALT

    def has_permission(self, request, view):
        game_id = view.kwargs.get("game_id")
        if not game_id:
            return False

        if request.user.is_authenticated:
            if GameSession.objects.filter(
                game_id=game_id, game_host=request.user
            ).exists():
                return True

        tokens = request.session.get("game_access_tokens") or {}
        session_token = tokens.get(game_id)
        if not session_token:
            return False

        cookie_name = f"{self.cookie_prefix}{game_id}"
        try:
            cookie_token = request.get_signed_cookie(cookie_name, salt=self.cookie_salt)
        except (KeyError, signing.BadSignature):
            return False

        return cookie_token == session_token


class IsPlayerInGame(BasePermission):
    message = "You are not a player in this game session."

    player_cookie_prefix = settings.COOKIE_PLAYER_PREFIX
    player_cookie_salt = settings.COOKIE_PLAYER_SALT

    def has_permission(self, request, view):
        game_id = view.kwargs.get("game_id")
        if not game_id:
            return False

        cookie_name = f"{self.player_cookie_prefix}{game_id}"

        try:
            player_id = request.get_signed_cookie(
                cookie_name, salt=self.player_cookie_salt
            )
        except (KeyError, signing.BadSignature):
            return False

        # Verify that player exists AND belongs to that game
        return Player.objects.filter(
            game__game_id=game_id, player_id=player_id
        ).exists()
