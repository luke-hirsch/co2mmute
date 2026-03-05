from django.urls import path
from game.views_rest import (
    PlayerListView,
    PlayerDetailView,
    GameSessionDetailView,
    GetYourOwnGame,
    GameSessionListView,
    PlayerMoveView,
    RoundTrafficHeatmapView,
    GameSummaryView,
)

app_name = "game"

urlpatterns = [
    path("<str:game_id>/player/", PlayerListView.as_view(), name="player-list"),
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
    path(
        "<str:game_id>/player/<str:player_id>/move/",
        PlayerMoveView.as_view(),
        name="player-move",
    ),
    path(
        "<str:game_id>/round/<int:round_number>/traffic/",
        RoundTrafficHeatmapView.as_view(),
        name="round-traffic-heatmap",
    ),
    path(
        "<str:game_id>/summary/",
        GameSummaryView.as_view(),
        name="game-summary",
    ),
]
