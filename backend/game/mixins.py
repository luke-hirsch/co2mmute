import uuid
from django.conf import settings
from rest_framework.exceptions import ValidationError
from game.models import Player
from typing import Any, Mapping


class GameAccessCookieMixin:
    cookie_prefix = settings.COOKIE_GAME_PREFIX
    cookie_salt = settings.COOKIE_GAME_SALT

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

        # Embed game_id into cookie value for validation in ws_auth
        cookie_value = f"{game_id}:{token}"

        response.set_signed_cookie(
            f"{self.cookie_prefix}{game_id}",
            cookie_value,
            salt=self.cookie_salt,
            httponly=True,
            secure=secure_flag,
            samesite="Lax",
            max_age=settings.COOKIE_AGE,
        )
        return response


class PlayerCookieMixin:
    cookie_prefix = settings.COOKIE_PLAYER_PREFIX
    cookie_salt = settings.COOKIE_PLAYER_SALT

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
            max_age=settings.COOKIE_AGE,
        )
        return response


class GameScopedQuerysetMixin:
    kwargs: Mapping[str, Any]

    def get_queryset(self):
        game_id = self.kwargs.get("game_id")
        if not game_id:
            raise ValidationError("game id is required")
        return Player.objects.filter(game__game_id=game_id)
