from django.urls import path
from game.views_rest import PlayerListView, PlayerDetailView

app_name = "game"

urlpatterns = [
    # List players in a game
    path("player/<str:game_id>/list/", PlayerListView.as_view(), name="player-list"),
    # Detail for a single player in a game
    path(
        "player/<str:game_id>/<str:player_id>/",
        PlayerDetailView.as_view(),
        name="player-detail",
    ),
]
