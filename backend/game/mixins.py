from rest_framework.exceptions import ValidationError
from game.models import Player
from game.cookie_utils import set_game_access_cookie, set_player_cookie
from typing import Any, Mapping


class GameAccessCookieMixin:
    def set_game_access_cookie(self, request, response, game_id: str):
        return set_game_access_cookie(request, response, game_id)


class PlayerCookieMixin:
    def set_player_cookie(self, request, response, game_id: str, player_id: str):
        return set_player_cookie(request, response, game_id, player_id)


class GameScopedQuerysetMixin:
    kwargs: Mapping[str, Any]

    def get_queryset(self):
        game_id = self.kwargs.get("game_id")
        if not game_id:
            raise ValidationError("game id is required")
        return Player.objects.filter(game__game_id=game_id)
