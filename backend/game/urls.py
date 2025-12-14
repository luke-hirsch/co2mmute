from django.urls import path
from game.rest_views import PlayerListView, PlayerDetailView

app_name = "game"

urlpatterns = [
    path("player/<str:game_id>/", PlayerDetailView.as_view(), name="player-list"),
    path("player/<str:game_id>/list/", PlayerListView.as_view(), name="player-list"),
]
