import logging
from typing import Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, TemplateView

from .cache import cache_game_session, get_cached_game_session
from .forms import GameSessionCreateForm, JoinSessionForm, PlayerCreateForm
from .mixins import GameAccessCookieMixin, PlayerCookieMixin
from .models import GameSession, Player

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
            return f"/app/game/{self.object.game_id}/"
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
                if game_session.started_at:
                    form.add_error(
                        "game_id",
                        "Game is already in progress. Please join a different game.",
                    )
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
                if game_session.started_at:
                    form.add_error(
                        "game_id",
                        "Game is already in progress. Please join a different game.",
                    )
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
        if self.game_session and self.game_session.is_active:
            messages.error(self.request, "Game has already started.")
            return redirect("session-join")

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

        success_url = f"/app/game/{self.game_session.game_id}/"
        response = redirect(success_url)

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
        logger.info(
            f"Set cookies for player {player.player_id} in game {self.game_session.game_id}"
        )

        messages.success(
            self.request,
            f"Welcome to {self.game_session.game_name}, {player.name or 'player'}!",
        )
        return response

    def get_success_url(self):
        if self.game_session:
            return f"/app/game/{self.game_session.game_id}/"
        logger.error("Game session is None when determining success URL.")
        raise ValueError("Game session not found during player creation.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["game_session"] = self.game_session
        return context


class PlayerUpdateView(PlayerCookieMixin, TemplateView):
    template_name = "game/update_player.html"


class PostGameView(GameAccessCookieMixin, PlayerCookieMixin, TemplateView):
    """this is a placeholder cbv"""

    template_name = "game/post_game.html"

    def dispatch(self, request, *args, **kwargs):
        game_id = kwargs.get("game_id", "").upper()
        self.game_session = get_object_or_404(GameSession, game_id=game_id)

        has_access = False
        if (
            request.user.is_authenticated
            and request.user == self.game_session.game_host
        ):
            has_access = True
        else:
            # Check if player joined this game (via session)
            joined_ids = request.session.get("joined_game_ids", [])
            if game_id in joined_ids:
                has_access = True

        if not has_access:
            messages.error(request, "You don't have access to this game summary.")
            return redirect("session-join")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        game = self.game_session
        players = Player.objects.filter(game=game, left_at__isnull=True)

        from .models import AgentRoute, AgentSimulationResult, GameRound, PlayerMove

        completed_rounds = GameRound.objects.filter(
            game=game, status=GameRound.Status.COMPLETED
        ).order_by("round_number")

        # Use stored round totals (populated by simulation or hardcoded fallback)
        total_co2_g = sum(r.total_emissions_g for r in completed_rounds)
        total_co2_kg = total_co2_g / 1000

        # Per-round stats for breakdown
        round_stats = []
        for game_round in completed_rounds:
            round_stats.append({
                "number": game_round.round_number,
                "emissions_kg": round(game_round.total_emissions_g / 1000, 2),
                "cost_eur": round(game_round.total_cost_eur, 2),
            })

        # Per-player stats: aggregate from simulation results across all rounds
        player_stats = []
        for player in players:
            moves = PlayerMove.objects.filter(
                player=player, session_round__in=completed_rounds
            )
            player_co2_g = 0.0
            player_cost_eur = 0.0
            modes_used = set()

            # Try simulation results first
            agent_results = AgentSimulationResult.objects.filter(
                agent_route__player_move__in=moves
            ).select_related("agent_route")

            if agent_results.exists():
                for result in agent_results:
                    player_co2_g += result.total_co2_g
                    player_cost_eur += result.mean_cost_eur
                    modes_used.add(result.agent_route.transport_mode)
            else:
                # Fallback: use AgentRoute transport modes with simple factors
                agent_routes = AgentRoute.objects.filter(player_move__in=moves)
                fallback_emissions = {
                    "car": 166.8, "public": 60.0, "bike": 18.0, "walk": 0.0,
                }
                for route in agent_routes:
                    dist_km = route.total_distance_m / 1000
                    player_co2_g += fallback_emissions.get(route.transport_mode, 0) * dist_km
                    modes_used.add(route.transport_mode)

            player_stats.append({
                "name": player.name,
                "player_id": player.player_id,
                "co2_kg": round(player_co2_g / 1000, 2),
                "cost_eur": round(player_cost_eur, 2),
                "modes": ", ".join(sorted(modes_used)) if modes_used else "—",
                "move_count": moves.count(),
            })

        player_stats.sort(key=lambda x: x["co2_kg"])
        for i, stat in enumerate(player_stats):
            stat["rank"] = i + 1

        rounds_played = completed_rounds.count()

        # max_CO2_level is in kg
        co2_limit_exceeded = total_co2_kg > game.max_CO2_level
        co2_percentage = round(
            (total_co2_kg / max(game.max_CO2_level, 1)) * 100, 1
        )

        context.update({
            "game": game,
            "player_stats": player_stats,
            "total_co2": round(total_co2_kg, 2),
            "max_co2": game.max_CO2_level,
            "co2_percentage": co2_percentage,
            "co2_limit_exceeded": co2_limit_exceeded,
            "rounds_played": rounds_played,
            "max_rounds": game.max_rounds,
            "player_count": len(player_stats),
            "winner": player_stats[0] if player_stats else None,
            "round_stats": round_stats,
        })

        return context
