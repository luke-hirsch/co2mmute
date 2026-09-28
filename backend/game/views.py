import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import CreateView, RedirectView, TemplateView

from .cache import get_cached_game_session
from .forms import JoinSessionForm, PlayerCreateForm
from .mixins import GameAccessCookieMixin, PlayerCookieMixin
from .models import Player

logger = logging.getLogger(__name__)


class GameSessionCreateView(LoginRequiredMixin, RedirectView):
    """`/game/create/` is now a doorway into the SPA. S13.

    The form itself is `frontend/src/routes/game/create.tsx`, because the two
    calibrated numbers it offers have to follow the class size as the host
    types it — `people_per_agent` divides the map's commuters between the
    Fahrgäste, so changing the seats changes it. Server-rendered, that
    derivation happened once per GET and a host who changed the Platzzahl had
    to pull both numbers across by hand (`docs/testfaelle.md` H-13).

    The URL stays because everything points at it: the landing page twice, the
    footer, the profile page, the end-of-game screen and six e2e specs. A
    redirect keeps every one of them working and leaves exactly one screen.

    `LoginRequiredMixin` stays too, and it is the reason this is a Django view
    rather than an nginx rule: an anonymous visitor belongs on the login page,
    not on a React screen that would bounce them there a second later.
    """

    pattern_name = None
    url = "/app/game/create"
    permanent = False


class ShareSessionView(LoginRequiredMixin, RedirectView):
    """`/game/<id>/share/` — the join QR, which the host lobby already shows.

    Not a port: a deletion. `HostLobbyScreen` puts the game id in a departure
    board with the QR under it, sized for a projector, and has done since F4 —
    so this page was a second screen answering one question, which is the thing
    this project keeps having to undo. It redirects into the lobby.

    A started game has no QR worth showing anyway: joining answers `started`.

    The URL stays because the host's game list links to it and so might a
    bookmark. Nothing is looked up here on purpose — whether a game id exists is
    not a stranger's business, and the game screen refuses what it must.
    """

    pattern_name = None
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return f"/app/game/{kwargs['game_id']}/"


class GameDeleteView(LoginRequiredMixin, RedirectView):
    """`/game/<id>/delete/` — deleting a game, which `/app/host` now does.

    The confirm page it replaces existed because an `<a href>` cannot send
    DELETE and the REST endpoint was the only thing that could delete a game.
    The React list can send DELETE, asks in a dialog that names what goes with
    it, and does not leave the page.

    **The rule the page carried moved with it**: a running game is refused, so
    `end_reason` gets written while it is still known. That refusal now lives in
    `GameSessionDetailView.destroy` (409 `running`) — on the endpoint, where
    both doors have to pass through it, rather than on one of them.
    """

    pattern_name = None
    url = "/app/host"
    permanent = False


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
                    # add_error needs cleaned_data, which an unbound form does
                    # not have — this branch used to raise AttributeError, so
                    # the QR code of a running game answered a 500.
                    form = self.form_class(data={"game_id": game_id})
                    form.is_valid()
                    form.add_error(
                        "game_id",
                        "Dieses Spiel läuft schon. Such dir ein anderes.",
                    )
            else:
                form = self.form_class(data={"game_id": game_id})
                form.is_valid()
                form.add_error("game_id", "Es gibt kein Spiel mit dieser ID.")

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
                form.add_error("game_id", "Es gibt kein Spiel mit dieser ID.")

            else:
                if game_session.started_at:
                    form.add_error(
                        "game_id",
                        "Dieses Spiel läuft schon. Such dir ein anderes.",
                    )

                show_password = bool(game_session.game_password)
                if show_password:
                    password = form.cleaned_data.get("game_password")
                    if not password:
                        awaiting_password = True
                    elif password != game_session.game_password:
                        form.add_error("game_password", "Das Passwort stimmt nicht.")

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
            messages.error(request, "Dieses Spiel gibt es nicht.")
            return redirect("session-join-direct", game_id=game_id)

        if not self._has_join_permission(request):
            messages.error(
                request, "Tritt dem Spiel erst bei, bevor du einen Namen wählst."
            )
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
            messages.error(self.request, "Das Spiel läuft schon.")
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
                "Beim Anlegen ist etwas schiefgegangen. Versuch es nochmal.",
            )

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
