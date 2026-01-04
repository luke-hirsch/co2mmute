from typing import Any, cast
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/lobby/(?P<game_id>[A-Za-z0-9_-]+)/$",
        cast(Any, consumers.LobbyConsumer.as_asgi()),
    ),
    re_path(
        r"ws/chat/(?P<game_id>[A-Za-z0-9_-]+)/$",
        cast(Any, consumers.ChatConsumer.as_asgi()),
    ),
    re_path(
        r"ws/gamestate/(?P<game_id>[A-Za-z0-9_-]+)/$",
        cast(Any, consumers.GameStateConsumer.as_asgi()),
    ),
]
