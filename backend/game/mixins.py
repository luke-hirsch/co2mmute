import uuid
from django.conf import settings
from rest_framework.exceptions import ValidationError
from game.models import Player

# game/mixins.py


from .ws_auth import COOKIE_GAME_PREFIX, COOKIE_GAME_SALT, COOKIE_PLAYER_PREFIX, COOKIE_PLAYER_SALT


class GameAccessCookieMixin:
    cookie_prefix = COOKIE_GAME_PREFIX
    cookie_salt = COOKIE_GAME_SALT

    def _session_store(self, request):
        return request.session.setdefault("game_access_tokens", {})

    def get_or_create_game_token(self, request, game_id: str) -> str:
        store = self._session_store(request)
        token = store.get(game_id)
        if not token:
            token = uuid.uuid4().hex
            store[game_id] = token
            request.session.modified = True
        return token

    def set_game_access_cookie(self, request, response, game_id: str):
        token = self.get_or_create_game_token(request, game_id)
        secure_flag = (
            getattr(settings, "SESSION_COOKIE_SECURE", False) or request.is_secure()
        )

        response.set_signed_cookie(
            f"{self.cookie_prefix}{game_id}",
            token,
            salt=self.cookie_salt,
            httponly=True,
            secure=secure_flag,
            samesite="Lax",
        )
        return response


class PlayerCookieMixin:
    cookie_prefix = COOKIE_PLAYER_PREFIX
    cookie_salt = COOKIE_PLAYER_SALT

    def _player_session_store(self, request):
        return request.session.setdefault("player_by_game", {})

    def set_player_cookie(self, request, response, game_id: str, player_id: str):
        # mirror to session for convenience/debugging (optional)
        store = self._player_session_store(request)
        store[game_id] = player_id
        request.session.modified = True

        secure_flag = (
            getattr(settings, "SESSION_COOKIE_SECURE", False) or request.is_secure()
        )
        response.set_signed_cookie(
            f"{self.cookie_prefix}{game_id}",
            str(player_id),
            salt=self.cookie_salt,
            httponly=True,
            secure=secure_flag,
            samesite="Lax",
        )
        return response


class GameScopedQuerysetMixin:
    def get_queryset(self):
        game_id = self.kwargs.get("game_id")
        if not game_id:
            raise ValidationError("game id is required")
        return Player.objects.filter(game__game_id=game_id)
