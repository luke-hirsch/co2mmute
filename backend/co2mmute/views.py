from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView as DjangoLogoutView
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
from game.models import GameSession


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


class WhoAmIView(APIView):
    """
    API endpoint that returns the current authenticated user's information.
    """

    def get(self, request, format=None):
        user = request.user
        if user.is_authenticated:
            user_data = {
                "authenticated": True,
                "id": user.id,
                "is_staff": user.is_staff,
                "is_active": user.is_active,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
            # Try to attach a short-lived JWT token to the response.
            try:
                expiration_seconds = int(
                    getattr(settings, "JWT_EXPIRATION_SECONDS", 300)
                )
                algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")
                exp = datetime.now() + timedelta(seconds=expiration_seconds)
                payload = {
                    "user_id": user.id,
                    "username": user.username,
                    "exp": exp,
                }
                token = jwt.encode(payload, settings.SECRET_KEY, algorithm=algorithm)
                # jwt.encode may return bytes in some versions — ensure string
                if isinstance(token, bytes):
                    token = token.decode("utf-8")
                user_data.update(
                    {
                        "token": token,
                        "token_expires_at": int(exp.timestamp()),
                    }
                )
            except Exception:
                # Don't break the endpoint if token creation fails (e.g., PyJWT not installed).
                pass

            return Response(user_data)
        else:
            return Response(
                {"authenticated": False}, status=status.HTTP_401_UNAUTHORIZED
            )
