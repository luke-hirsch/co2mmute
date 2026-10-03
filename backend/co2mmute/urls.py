from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from game.views import GameDeleteView, GameSessionCreateView, ShareSessionView
from maps.views import MapDetailView, MapListView, MapUploadView

from .views import (
    AccountDeletedView,
    AccountDeleteView,
    AccountView,
    CookiesView,
    DsgvoView,
    DocView,
    ImpressumView,
    IndexView,
    LoginView,
    LogoutView,
    NavigationView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
    ProfileView,
    SignUpView,
    SpaView,
    WhoAmIView,
)

# route, template, url name, language, the same page in the other language
DOCS = (
    ("docs/schnellstart/", "docs/schnellstart.html", "docs-schnellstart", "de", "docs-quick-start"),
    ("docs/hintergrund/", "docs/hintergrund.html", "docs-hintergrund", "de", "docs-background"),
    ("docs/ablaufdiagramme/", "docs/ablaufdiagramme.html", "docs-ablaufdiagramme", "de", "docs-flowcharts"),
    ("docs/en/quick-start/", "docs/en/quick-start.html", "docs-quick-start", "en", "docs-schnellstart"),
    ("docs/en/background/", "docs/en/background.html", "docs-background", "en", "docs-hintergrund"),
    ("docs/en/flowcharts/", "docs/en/flowcharts.html", "docs-flowcharts", "en", "docs-ablaufdiagramme"),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", IndexView.as_view(), name="index"),
    # The docs on the site, F13: each page in German and in English, each
    # naming its twin. /hintergrund/ moved here and does not redirect — a link
    # to the old address is a 404, like the old join (S22).
    *[
        path(route, DocView.as_view(template_name=template, lang=lang, twin=twin), name=name)
        for route, template, name, lang, twin in DOCS
    ],
    # Above the auth include, which is what routes it: the first match wins,
    # so this replaces the stock LoginView with the rate-limited one without
    # the include having to know.
    path("accounts/login/", LoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("accounts/signup/", SignUpView.as_view(), name="signup"),
    path("accounts/profile/", ProfileView.as_view(), name="profile"),
    path(
        "accounts/profile/delete/",
        AccountDeleteView.as_view(),
        name="account-delete",
    ),
    path("accounts/deleted/", AccountDeletedView.as_view(), name="account-deleted"),
    # The three password views that take a form, with German ones — S22. Same
    # trick as the login above: declared before the include, so they win.
    path(
        "accounts/password_change/",
        PasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "accounts/password_reset/",
        PasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("accounts/", include("django.contrib.auth.urls")),
    path("legal/dsgvo/", DsgvoView.as_view(), name="dsgvo"),
    path("legal/impressum/", ImpressumView.as_view(), name="impressum"),
    path("legal/cookies/", CookiesView.as_view(), name="cookies"),
    path("game/create/", GameSessionCreateView.as_view(), name="session-create"),
    path("game/<game_id>/share/", ShareSessionView.as_view(), name="session-share"),
    path("game/<game_id>/delete/", GameDeleteView.as_view(), name="session-delete"),
    path("map/upload/", MapUploadView.as_view(), name="map-upload"),
    path("map/list/", MapListView.as_view(), name="map-list"),
    path("map/<int:pk>/", MapDetailView.as_view(), name="map-detail"),
    path("api/game/", include("game.urls")),
    path("api/whoami/", WhoAmIView.as_view(), name="whoami"),
    path("api/navigation/", NavigationView.as_view(), name="navigation"),
    path("api/account/", AccountView.as_view(), name="account"),
    path("api/maps/", include("maps.urls")),
    path("content/", include("content.urls", namespace="content")),
    re_path(r"^app(?:/.*)?$", SpaView.as_view(), name="app"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
