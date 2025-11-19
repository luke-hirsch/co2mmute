from django.contrib import admin
from django.urls import path, include, re_path
from .views import IndexView, SignUpView, DsgvoView, ImpressumView, SpaView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", IndexView.as_view(), name="index"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/signup", SignUpView.as_view(), name="signup"),
    path("legal/dsgvo", DsgvoView.as_view(), name="dsgvo"),
    path("legal/impressum", ImpressumView.as_view(), name="impressum"),
    path("api/game/", include("game.urls")),
    path("api/game_data/", include("game_data.urls")),
    path("api/maps/", include("maps.urls")),
    path("api/lobby/", include("lobby.urls")),
    re_path(r"^app(?:/.*)?$", SpaView.as_view(), name="app"),
]
