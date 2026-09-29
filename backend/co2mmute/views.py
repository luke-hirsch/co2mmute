from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.shortcuts import redirect, resolve_url
from django.urls import NoReverseMatch, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.views.generic import (
    CreateView,
    FormView,
    RedirectView,
    TemplateView,
)
from game.anon import anonymise_account
from game.auth import resolve_player_id
from game.cache import get_cached_game_session
from game.models import GameSession, Player
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from co2mmute.throttle import (
    LOGIN_LIMIT,
    LOGIN_WINDOW,
    SIGNUP_LIMIT,
    SIGNUP_WINDOW,
    clear,
    client_key,
    over_limit,
    record,
)
from co2mmute.utils import set_game_access_cookie, set_player_cookie

from .forms import AccountDeleteForm, SignupForm
from .serializers import HostAccountSerializer

THROTTLED_TEMPLATE = "registration/throttled.html"


def throttled(request, message: str, window: int):
    """The 429 both auth views answer with.

    A rendered page rather than a bare status, because these two are typed into
    a browser by a person: `/accounts/login/` and `/accounts/signup/` are the
    server-rendered funnel, not the API. 429 and not 403 so a log can tell the
    two apart at a glance.
    """
    from django.shortcuts import render

    return render(
        request,
        THROTTLED_TEMPLATE,
        {"throttle_message": message, "throttle_minutes": window // 60},
        status=429,
    )


class IndexView(TemplateView):
    template_name = "index.html"


class HintergrundView(TemplateView):
    template_name = "hintergrund.html"


class SpaView(TemplateView):
    template_name = "app.html"


class LoginView(DjangoLoginView):
    """`/accounts/login/` with a limit on wrong passwords — S9.

    Declared above `django.contrib.auth.urls` in `co2mmute/urls.py`, which is
    the whole of the wiring: the first matching pattern wins, so this replaces
    the stock view without touching the include.

    **Failures are counted, not attempts.** A classroom is one address behind
    the school's NAT, and a researcher who mistypes once should not spend a
    quota the rest of the room shares. A guesser, by definition, produces
    nothing but failures.

    **Per address only, not per username.** A per-account counter would let
    anybody lock a known host out of their own lesson by guessing at their name
    — trading a real denial of service for protection against a distributed
    attack nobody is mounting on a thesis prototype.
    """

    def post(self, request, *args, **kwargs):
        key = client_key(request)
        if over_limit("login", key, LOGIN_LIMIT):
            return throttled(
                request,
                "Zu viele Anmeldeversuche von diesem Anschluss.",
                LOGIN_WINDOW,
            )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        clear("login", client_key(self.request))
        return super().form_valid(form)

    def form_invalid(self, form):
        record("login", client_key(self.request), LOGIN_WINDOW)
        return super().form_invalid(form)


class SignUpView(CreateView):
    template_name = "registration/signup.html"
    form_class = SignupForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self._get_next_url()
        return context

    def post(self, request, *args, **kwargs):
        """**Successes** are what this one counts.

        A rejected sign-up form has guessed at nothing — there is no secret
        behind this door — so counting attempts would only lock somebody out of
        their own account for failing the password rules twice. The abuse worth
        stopping is a script making accounts, and every one of those succeeds.
        """
        if over_limit("signup", client_key(request), SIGNUP_LIMIT):
            return throttled(
                request,
                "Von diesem Anschluss wurden gerade viele Konten angelegt.",
                SIGNUP_WINDOW,
            )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        record("signup", client_key(self.request), SIGNUP_WINDOW)
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


class ProfileView(LoginRequiredMixin, RedirectView):
    """`/accounts/profile/` is a doorway into the SPA now. S13.

    The page itself is `frontend/src/routes/host.tsx`: the host's games and
    their account details, both of them things that change while you look at
    them — a game ends, a name is taken. It followed the create form across for
    the reason Lukas gave on 2026-09-28, that the host's own pages belong
    together.

    The URL stays because Django's `LOGIN_REDIRECT_URL` defaults to it, the
    footer and the app header point at it, and so do the account-deletion pages
    that were deliberately *not* ported — re-authentication and the goodbye
    page are credential flows, and those stay server-rendered.
    """

    pattern_name = None
    url = "/app/host"
    permanent = False


class AccountView(APIView):
    """`GET`/`PATCH api/account/` — the host edits their own account. S13.

    Only ever the requesting user: there is no pk in the path and none is
    accepted, so the endpoint cannot be pointed at somebody else's row. That is
    also why it is an `APIView` rather than a `RetrieveUpdateAPIView` with a
    queryset — there is no lookup to get wrong.

    Password and account deletion are not here. Both are credential flows with
    a re-authentication step (`AccountDeleteForm` asks for the password, because
    the host machine stands in a classroom and is often still logged in), and
    they stay on Django's own pages.
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(HostAccountSerializer(request.user).data)

    def patch(self, request):
        serializer = HostAccountSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # No `update_session_auth_hash` here, deliberately: the session auth
        # hash is an HMAC of the *password*, so renaming yourself does not
        # invalidate it. Calling it would suggest it did. That a rename does
        # not log the host out is pinned by a test rather than by this comment.
        return Response(serializer.data)


class LogoutView(DjangoLogoutView):
    http_method_names = ["get", "post", "options", "head"]

    def get(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# commute/views.py (or game/views.py, wherever you keep API views)

# adjust import


class WhoAmIView(APIView):
    def get(self, request, format=None):
        user = request.user
        game_id = (request.query_params.get("game_id") or "").strip().upper()

        player = None
        if game_id:
            player = self._get_player_from_cookie(request, game_id)

        if user and user.is_authenticated:
            user_data = {
                "authenticated": True,
                "id": user.id,
                "isStaff": user.is_staff,
                "isActive": user.is_active,
                "username": user.username,
                "email": user.email,
                "firstName": user.first_name,
                "lastName": user.last_name,
            }

            try:
                expiration_seconds = int(
                    getattr(settings, "JWT_EXPIRATION_SECONDS", 300)
                )
                algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")
                exp = now() + timedelta(seconds=expiration_seconds)
                payload = {"user_id": user.id, "username": user.username, "exp": exp}
                token = jwt.encode(payload, settings.SECRET_KEY, algorithm=algorithm)
                if isinstance(token, bytes):
                    token = token.decode("utf-8")
                user_data.update(
                    {"token": token, "token_expires_at": int(exp.timestamp())}
                )
            except Exception:
                pass

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
            user_data.update(
                {
                    "kind": self._get_kind_for_authenticated_user(
                        user, game_id, player
                    ),
                }
            )

            return self._renew_cookies(Response(user_data), game_id, player)

        if player:
            response = Response(
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
            return self._renew_cookies(response, game_id, player)

        return Response(
            {
                "kind": "anonymous",
                "authenticated": False,
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    def _renew_cookies(self, response, game_id, player):
        """Every visit re-issues both cookies with a fresh timestamp, so a
        class that comes back within COOKIE_AGE of its last visit finds its
        seats again. Same format as before: nobody is logged out.
        Roadmap.md 1.6."""
        if player is None:
            return response
        response = set_game_access_cookie(self.request, response, game_id)
        return set_player_cookie(self.request, response, game_id, str(player.player_id))

    def _get_player_from_cookie(self, request, game_id):
        player_id = resolve_player_id(request.COOKIES, game_id)
        if not player_id:
            return None
        return Player.objects.filter(
            game__game_id=game_id, player_id=player_id, left_at__isnull=True
        ).first()

    def _get_kind_for_authenticated_user(self, user, game_id, player):
        if not game_id:
            return "user"

        cached_game = get_cached_game_session(game_id)
        if cached_game and cached_game.game_host == user:
            return "host"
        if cached_game and player:
            return "player"
        return "user"


class AccountDeleteView(LoginRequiredMixin, FormView):
    """DSGVO erasure, from the one page a host ever sees.

    What deletion means is game/anon.py's answer, not this view's: the row
    stays and the name goes, because game_host is CASCADE.
    """

    template_name = "registration/account_delete.html"
    form_class = AccountDeleteForm
    success_url = reverse_lazy("account-deleted")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["running_games"] = GameSession.objects.filter(
            game_host=self.request.user, ended_at__isnull=True
        ).count()
        return context

    def form_valid(self, form):
        anonymise_account(self.request.user)
        logout(self.request)
        return super().form_valid(form)


class AccountDeletedView(TemplateView):
    """The last page the account sees, so it cannot want a login."""

    template_name = "registration/account_deleted.html"
