from django.contrib import admin
from django.urls import path, include, re_path
from .views import (
    IndexView,
    LogoutView,
    SignUpView,
    DsgvoView,
    ImpressumView,
    SpaView,
    ProfileView,
    WhoAmIView,
)
from game.views import (
    GameSessionCreateView,
    ShareSessionView,
    JoinSessionView,
    PlayerCreateView,
    PlayerUpdateView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", IndexView.as_view(), name="index"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("accounts/signup/", SignUpView.as_view(), name="signup"),
    path("accounts/profile/", ProfileView.as_view(), name="profile"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("legal/dsgvo", DsgvoView.as_view(), name="dsgvo"),
    path("legal/impressum", ImpressumView.as_view(), name="impressum"),
    path("game/create/", GameSessionCreateView.as_view(), name="session-create"),
    path("game/<game_id>/share/", ShareSessionView.as_view(), name="session-share"),
    path("join/", JoinSessionView.as_view(), name="session-join"),
    path("join/<game_id>/", JoinSessionView.as_view(), name="session-join-direct"),
    path(
        "game/<game_id>/player/create", PlayerCreateView.as_view(), name="player-create"
    ),
    path(
        "game/<game_id>/player/<player_id>/update",
        PlayerUpdateView.as_view(),
        name="player-update",
    ),
    path("api/game/", include("game.urls")),
    path("api/whoami/", WhoAmIView.as_view(), name="whoami"),
    path("api/game_data/", include("game_data.urls")),
    path("api/maps/", include("maps.urls")),
    re_path(r"^app(?:/.*)?$", SpaView.as_view(), name="app"),
]
