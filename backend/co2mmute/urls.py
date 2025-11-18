from django.contrib import admin
from django.urls import path, include
from .views import IndexView, SpaView, SignUpView, DsgvoView, ImpressumView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", IndexView.as_view(), name="index"),
    path("app/", SpaView.as_view(), name="app"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/signup", SignUpView.as_view(), name="signup"),
    path("legal/dsgvo", DsgvoView.as_view(), name="dsgvo"),
    path("legal/impressum", ImpressumView.as_view(), name="dsgvo"),
    path("api/game/", include("game.urls")),
    path("api/game_data/", include("game_data.urls")),
    path("api/maps/", include("maps.urls")),
    path("api/lobby/", include("maps.urls")),
]
