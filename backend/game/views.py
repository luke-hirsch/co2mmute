from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, TemplateView
from .cache import cache_game_session, get_cached_game_session
from .mixins import GameAccessCookieMixin, PlayerCookieMixin
from .forms import GameSessionCreateForm, JoinSessionForm, PlayerCreateForm
from .models import GameSession, Player
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class GameSessionCreateView(
    GameAccessCookieMixin, PlayerCookieMixin, LoginRequiredMixin, CreateView
):
    template_name = "game/create_session.html"
    form_class = GameSessionCreateForm
    model = GameSession
    object: Optional[GameSession]

    def form_valid(self, form):
        form.instance.game_host = self.request.user
        response = super().form_valid(form)
        cache_game_session(form.instance)

        # Create a player record for the game host automatically
        user = self.request.user
        host_name = "Host"
        if hasattr(user, "get_full_name"):
            full_name = user.get_full_name()  # type: ignore
            if full_name.strip():
                host_name = f"{full_name} (Host)"

        host_player, created = Player.objects.get_or_create(
            game=form.instance,
            user=self.request.user,
            defaults={
                "name": host_name,
                "controlled_by_host": True,
            },
        )

        # Ensure player_id is generated
        if not host_player.player_id:
            host_player.refresh_from_db()

        messages.success(
            self.request, f"Game Session '{form.instance.game_name}' created."
        )

        # Set both game and player cookies for the host
        response = self.set_game_access_cookie(
            self.request, response, form.instance.game_id
        )
        player_id = host_player.player_id
        if player_id:
            response = self.set_player_cookie(
                self.request, response, form.instance.game_id, player_id
            )
        return response

    def get_success_url(self):
        if self.object:
            return f"/app/lobby/{self.object.game_id}/"
        logger.error("Game session object is None after creation.")
        raise ValueError("Game session not found after creation.")


class ShareSessionView(LoginRequiredMixin, TemplateView):
    template_name = "game/share_session.html"

    def dispatch(self, request, *args, **kwargs):
        self.game_session = get_object_or_404(
            GameSession, game_id=kwargs["game_id"], game_host=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        join_url = self.request.build_absolute_uri(
            reverse(
                "session-join-direct", kwargs={"game_id": self.game_session.game_id}
            )
        )
        context.update(
            {
                "game_session": self.game_session,
                "join_url": join_url,
            }
        )
        return context


class JoinSessionView(GameAccessCookieMixin, TemplateView):
    template_name = "game/join_session.html"
    form_class = JoinSessionForm

    def get(self, request, *args, **kwargs):
        game_id = (kwargs.get("game_id") or "").upper()
        initial = {"game_id": game_id} if game_id else None
        form = self.form_class(initial=initial)

        game_session = None
        show_password = False

        if game_id:
            game_session = get_cached_game_session(game_id)
            if game_session:
                show_password = bool(game_session.game_password)
            else:
                form = self.form_class(data={"game_id": game_id})
                form.is_valid()
                form.add_error("game_id", "No session found with that ID.")

        return self.render_to_response(
            {
                "form": form,
                "game_session": game_session,
                "show_password": show_password,
            }
        )

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        game_session = None
        show_password = False
        awaiting_password = False

        if form.is_valid():
            game_id = form.cleaned_data["game_id"].upper()

            game_session = get_cached_game_session(game_id)
            if not game_session:
                form.add_error("game_id", "No session found with that ID.")
            else:
                show_password = bool(game_session.game_password)
                if show_password:
                    password = form.cleaned_data.get("game_password")
                    if not password:
                        awaiting_password = True
                    elif password != game_session.game_password:
                        form.add_error("game_password", "Incorrect password.")

            if not form.errors and not awaiting_password and game_session:
                self._mark_joined(request, game_session)

                response = redirect(
                    "player-create",
                    game_id=game_session.game_id,
                )
                return self.set_game_access_cookie(
                    request,
                    response,
                    game_session.game_id,
                )

        return self.render_to_response(
            {
                "form": form,
                "game_session": game_session,
                "show_password": show_password or awaiting_password,
            }
        )

    def _mark_joined(self, request, game_session):
        joined_ids = request.session.get("joined_game_ids", [])
        if game_session.game_id not in joined_ids:
            joined_ids.append(game_session.game_id)
            request.session["joined_game_ids"] = joined_ids
            request.session.modified = True


class PlayerCreateView(
    GameAccessCookieMixin,
    PlayerCookieMixin,
    CreateView,
):
    template_name = "game/create_player.html"
    form_class = PlayerCreateForm
    model = Player

    def dispatch(self, request, *args, **kwargs):
        game_id = kwargs["game_id"]
        self.game_session = get_cached_game_session(game_id)

        if not self.game_session:
            messages.error(request, "We could not find that session.")
            return redirect("session-join-direct", game_id=game_id)

        if not self._has_join_permission(request):
            messages.error(request, "Please join the session before creating a player.")
            return redirect("session-join-direct", game_id=game_id)

        return super().dispatch(request, *args, **kwargs)

    def _has_join_permission(self, request):
        if (
            request.user.is_authenticated
            and self.game_session
            and request.user == self.game_session.game_host
        ):
            return True

        joined_ids = request.session.get("joined_game_ids", [])
        return self.game_session is not None and self.game_session.game_id in joined_ids

    def form_valid(self, form):
        form.instance.game = self.game_session
        logger.info(
            f"PlayerCreateView.form_valid() called, creating player: {form.cleaned_data}"
        )

        # Manually save the form instead of using super().form_valid()
        # This allows us to set cookies BEFORE creating the response
        player = form.save()
        logger.info(f"Player saved: id={player.id}, player_id={player.player_id}")
        if not self.game_session:
            raise ValueError("GameSession not found")
        if not player.player_id:
            logger.error(
                f"Failed to generate player_id for player {player.id} in game {self.game_session.game_id}"
            )
            messages.error(
                self.request,
                "An error occurred while creating your player. Please try again.",
            )
            return redirect("player-create", game_id=self.game_session.game_id)

        # Create the redirect response first
        success_url = f"/app/lobby/{self.game_session.game_id}/"
        response = redirect(success_url)
        logger.info(f"Created redirect response to: {success_url}")

        # Set cookies on the response
        logger.info(
            f"Setting cookies for player {player.player_id} in game {self.game_session.game_id}"
        )
        response = self.set_game_access_cookie(
            self.request,
            response,
            self.game_session.game_id,
        )
        response = self.set_player_cookie(
            self.request,
            response,
            self.game_session.game_id,
            player.player_id,
        )
        logger.info("Cookies set on response")

        messages.success(
            self.request,
            f"Welcome to {self.game_session.game_name}, {player.name or 'player'}!",
        )
        return response

    def get_success_url(self):
        if self.game_session:
            return f"/app/lobby/{self.game_session.game_id}/"
        logger.error("Game session is None when determining success URL.")
        raise ValueError("Game session not found during player creation.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["game_session"] = self.game_session
        return context


class PlayerUpdateView(PlayerCookieMixin, TemplateView):
    template_name = "game/update_player.html"
