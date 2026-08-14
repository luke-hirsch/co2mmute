from django.urls import path

from game.views_join import JoinSessionAPIView, LobbyStateView, SessionLookupView
from game.views_rest import (
    GameSessionDetailView,
    GameSummaryView,
    GetYourOwnGame,
    PlayerDetailView,
    PlayerListView,
    PlayerMoveView,
    RoundTrafficHeatmapView,
)

app_name = "game"

urlpatterns = [
    # Literal prefixes first — the dynamic patterns below would swallow them.
    path("lookup/<str:game_id>/", SessionLookupView.as_view(), name="session-lookup"),
    path("join/<str:game_id>/", JoinSessionAPIView.as_view(), name="session-join-api"),
    path("<str:game_id>/lobby/", LobbyStateView.as_view(), name="lobby-state"),
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
    # Must stay last: two dynamic segments match almost anything.
    path(
        "<str:game_id>/<str:player_id>/",
        GetYourOwnGame.as_view(),
        name="player-game-session-detail",
    ),
]
