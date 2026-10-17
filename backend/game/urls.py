from django.urls import path

from game.views_join import (
    CodeView,
    LobbyStateView,
)
from game.views_rest import (
    GamePauseView,
    GameResumeView,
    GameSessionListCreateView,
    GameSessionDetailView,
    GameSummaryView,
    GetYourOwnGame,
    MuteUnmutePlayerView,
    PlayerDetailView,
    PlayerListView,
    PlayerMoveView,
    RoundReplayView,
    RoundTrafficHeatmapView,
    SeatCodeIssueView,
    SeatTakeoverView,
    StandardPersonasView,
)

app_name = "game"

urlpatterns = [
    # Literal prefixes first — the dynamic patterns below would swallow them.
    path("", GameSessionListCreateView.as_view(), name="session-list-create"),
    # A literal, so above every "<game_id>/…": one dynamic segment takes any word.
    path("personas/", StandardPersonasView.as_view(), name="standard-personas"),
    # Every code, game id, seat code or another kind: the length says which.
    path("code/<str:code>/", CodeView.as_view(), name="code"),
    path("<str:game_id>/lobby/", LobbyStateView.as_view(), name="lobby-state"),
    path("<str:game_id>/pause/", GamePauseView.as_view(), name="game-pause"),
    path("<str:game_id>/resume/", GameResumeView.as_view(), name="game-resume"),
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
        "<str:game_id>/player/<str:player_id>/code/",
        SeatCodeIssueView.as_view(),
        name="seat-code-issue",
    ),
    path(
        "<str:game_id>/player/<str:player_id>/takeover/",
        SeatTakeoverView.as_view(),
        name="seat-takeover",
    ),
    path(
        "<str:game_id>/player/<str:player_id>/mute/",
        MuteUnmutePlayerView.as_view(),
        name="player-mute",
    ),
    path(
        "<str:game_id>/round/<int:round_number>/traffic/",
        RoundTrafficHeatmapView.as_view(),
        name="round-traffic-heatmap",
    ),
    path(
        "<str:game_id>/round/<int:round_number>/replay/",
        RoundReplayView.as_view(),
        name="round-replay",
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
