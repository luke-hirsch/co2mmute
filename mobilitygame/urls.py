from django.contrib import admin
from django.urls import path, include

from django.contrib.auth.views import (
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)

from .views import AuthView, IndexView

urlpatterns = [
    path("admin/", admin.site.urls),
    # auth views
    path(
        "login/",
        AuthView.as_view(),
        name="login",
    ),
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path(
        "password-reset/",
        PasswordResetView.as_view(template_name="password_reset.html"),
        name="password_reset",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(template_name="password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/done/",
        PasswordResetDoneView.as_view(template_name="password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password-reset-complete/",
        PasswordResetCompleteView.as_view(template_name="password_reset_complete.html"),
        name="password_reset_complete",
    ),
    # main views
    path("", IndexView.as_view(), name="index"),
    path("game/", include("game.urls")),
]
