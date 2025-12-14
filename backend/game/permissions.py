from django.core import signing
from rest_framework.permissions import BasePermission

from .models import GameSession


class HasGameAccess(BasePermission):
    message = "You do not have access to this game session."

    cookie_prefix = "game_access_"
    cookie_salt = "game-access-token"

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
            cookie_token = request.get_signed_cookie(
                cookie_name, salt=self.cookie_salt
            )
        except (KeyError, signing.BadSignature):
            return False

        return cookie_token == session_token
