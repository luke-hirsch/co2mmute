from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/lobby/(?P<game_id>[A-Z0-9]+)/$", consumers.LobbyConsumer.as_asgi()),
    re_path(r"ws/chat/(?P<game_id>[A-Z0-9]+)/$", consumers.ChatConsumer.as_asgi()),
]
