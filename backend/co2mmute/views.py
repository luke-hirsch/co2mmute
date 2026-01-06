from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.core import signing
from django.shortcuts import redirect, resolve_url
from django.urls import NoReverseMatch
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, TemplateView
import jwt
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .forms import SignupForm
from game.cache import get_cached_game_session
from game.models import GameSession, Player


class IndexView(TemplateView):
    template_name = "index.html"


class SpaView(TemplateView):
    template_name = "app.html"


class SignUpView(CreateView):
    template_name = "registration/signup.html"
    form_class = SignupForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self._get_next_url()
        return context

    def form_valid(self, form):
        self.object = form.save()
        login(self.request, self.object)
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        response = super().form_invalid(form)
        response.status_code = 400
        return response

    def get_success_url(self):
        redirect_target = self._get_next_url()
        if redirect_target and url_has_allowed_host_and_scheme(
            redirect_target,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return redirect_target

        default_redirect = getattr(settings, "LOGIN_REDIRECT_URL", None)
        if default_redirect:
            try:
                return resolve_url(default_redirect)
            except NoReverseMatch:
                pass
        try:
            return resolve_url("profile")
        except NoReverseMatch:
            return "/"

    def _get_next_url(self):
        next_url = self.request.POST.get("next")
        if next_url is None:
            next_url = self.request.GET.get("next", "")
        return (next_url or "").strip()


class DsgvoView(TemplateView):
    template_name = "legal/dsgvo.html"


class ImpressumView(TemplateView):
    template_name = "legal/impressum.html"


class CookiesView(TemplateView):
    template_name = "legal/cookies.html"


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "registration/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_sessions = GameSession.objects.filter(
            game_host=self.request.user
        ).order_by("-created_at")
        context.update(
            {
                "game_sessions": user_sessions,
                "change_password_url": "password_change",
                "create_session_url": "session-create",
            }
        )
        return context


class LogoutView(DjangoLogoutView):
    http_method_names = ["get", "post", "options", "head"]

    def get(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# commute/views.py (or game/views.py, wherever you keep API views)

# adjust import


class WhoAmIView(APIView):
    """
    Returns identity for one of 4 cases:
    1. authenticated user (host/admin) - if user is logged in without game context
    2. host (authenticated user in game context) - if user is logged in AND is the game host
    3. player (authenticated or anonymous) - if player cookie exists for the game
    4. anonymous (no authentication, no player cookie)

    Pass ?game_id=ABC123 to provide game context.
    """

    def get(self, request, format=None):
        user = request.user
        game_id = (request.query_params.get("game_id") or "").strip().upper()

        # Try to get player from cookie if game_id is provided
        player = None
        if game_id:
            player = self._get_player_from_cookie(request, game_id)

        # Case 1 & 2: User is authenticated
        if user and user.is_authenticated:
            user_data = {
                "kind": self._get_kind_for_authenticated_user(user, game_id),
                "authenticated": True,
                "id": user.id,
                "isStaff": user.is_staff,
                "isActive": user.is_active,
                "username": user.username,
                "email": user.email,
                "firstName": user.first_name,
                "lastName": user.last_name,
            }

            # Optional: attach short-lived JWT
            try:
                expiration_seconds = int(
                    getattr(settings, "JWT_EXPIRATION_SECONDS", 300)
                )
                algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")
                exp = datetime.now() + timedelta(seconds=expiration_seconds)
                payload = {"user_id": user.id, "username": user.username, "exp": exp}
                token = jwt.encode(payload, settings.SECRET_KEY, algorithm=algorithm)
                if isinstance(token, bytes):
                    token = token.decode("utf-8")
                user_data.update(
                    {"token": token, "token_expires_at": int(exp.timestamp())}
                )
            except Exception:
                pass

            # If user is also a player in this game context, include player info
            if player:
                user_data.update(
                    {
                        "gameId": game_id,
                        "player": {
                            "playerId": player.player_id,
                            "name": player.name,
                        },
                    }
                )

            return Response(user_data)

        # Case 3: Anonymous player (with game context)
        if player:
            return Response(
                {
                    "kind": "player",
                    "authenticated": False,
                    "gameId": game_id,
                    "player": {
                        "playerId": player.player_id,
                        "name": player.name,
                    },
                }
            )

        # Case 4: Anonymous (no context)
        return Response(
            {
                "kind": "anonymous",
                "authenticated": False,
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    def _get_player_from_cookie(self, request, game_id):
        """Extract and validate player from signed cookie."""
        cookie_name = f"{settings.COOKIE_PLAYER_PREFIX}{game_id}"
        raw = request.COOKIES.get(cookie_name)
        if not raw:
            return None

        try:
            # Use TimestampSigner.unsign() to match the TimestampSigner.sign() in cookie_utils
            signer = signing.TimestampSigner(salt=settings.COOKIE_PLAYER_SALT)
            player_id = signer.unsign(raw, max_age=None)
        except signing.BadSignature:
            return None

        player = Player.objects.filter(
            game__game_id=game_id, player_id=player_id
        ).first()
        return player

    def _get_kind_for_authenticated_user(self, user, game_id):
        """Determine if authenticated user is 'host' or 'user'."""
        if not game_id:
            return "user"

        cached_game = get_cached_game_session(game_id)
        if cached_game and cached_game.game_host == user:
            return "host"

        return "user"
