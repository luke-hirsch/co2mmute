from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from content.views import PageDetailView
from game.views import (
    GameSessionCreateView,
    JoinSessionView,
    PlayerCreateView,
    PlayerUpdateView,
    PostGameView,
    ShareSessionView,
    SimulationLogDownloadView,
)
from maps.views import MapDetailView, MapListView, MapUploadView

from .views import (
    CookiesView,
    DsgvoView,
    ImpressumView,
    IndexView,
    LogoutView,
    ProfileView,
    SignUpView,
    SpaView,
    WhoAmIView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", IndexView.as_view(), name="index"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("accounts/signup/", SignUpView.as_view(), name="signup"),
    path("accounts/profile/", ProfileView.as_view(), name="profile"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("legal/dsgvo/", DsgvoView.as_view(), name="dsgvo"),
    path("legal/impressum/", ImpressumView.as_view(), name="impressum"),
    path("legal/cookies/", CookiesView.as_view(), name="cookies"),
    path("game/create/", GameSessionCreateView.as_view(), name="session-create"),
    path("game/<game_id>/share/", ShareSessionView.as_view(), name="session-share"),
    path("game/<game_id>/summary/", PostGameView.as_view(), name="session-summery"),
    path("game/<game_id>/simulation-log/", SimulationLogDownloadView.as_view(), name="simulation-log"),
    path("join/", JoinSessionView.as_view(), name="session-join"),
    path("join/<game_id>/", JoinSessionView.as_view(), name="session-join-direct"),
    path(
        "game/<game_id>/player/create/",
        PlayerCreateView.as_view(),
        name="player-create",
    ),
    path(
        "game/<game_id>/player/<player_id>/update/",
        PlayerUpdateView.as_view(),
        name="player-update",
    ),
    path("map/upload/", MapUploadView.as_view(), name="map-upload"),
    path("map/list/", MapListView.as_view(), name="map-list"),
    path("map/<int:pk>/", MapDetailView.as_view(), name="map-detail"),

    path("api/game/", include("game.urls")),
    path("api/whoami/", WhoAmIView.as_view(), name="whoami"),
    path("api/maps/", include("maps.urls")),
    path("content/", include("content.urls", namespace="content")),
    re_path(r"^app(?:/.*)?$", SpaView.as_view(), name="app"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
