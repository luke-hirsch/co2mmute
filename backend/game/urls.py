from django.urls import path
from game.views_rest import (
    PlayerListView,
    PlayerDetailView,
    GameSessionDetailView,
    GetYourOwnGame,
    GameSessionListView,
)

app_name = "game"

urlpatterns = [
    # List players in a game
    path("<str:game_id>/player/", PlayerListView.as_view(), name="player-list"),
    # Detail for a single player in a game
    path(
        "<str:game_id>/player/<str:player_id>/",
        PlayerDetailView.as_view(),
        name="player-detail",
    ),
    path(
        "<str:game_id>/",
        GameSessionDetailView.as_view(),
        name="game-session-detail",
    ),
    path(
        "<str:game_id>/<str:player_id>/",
        GetYourOwnGame.as_view(),
        name="player-game-session-detail",
    ),
    path("sessions/", GameSessionListView.as_view(), name="game-session-list"),
]
