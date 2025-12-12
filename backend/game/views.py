from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, TemplateView

from .forms import GameSessionCreateForm, JoinSessionForm, PlayerCreateForm
from .models import GameSession, Player


class GameSessionCreateView(LoginRequiredMixin, CreateView):
    template_name = "game/create_session.html"
    form_class = GameSessionCreateForm
    model = GameSession

    def form_valid(self, form):
        form.instance.game_host = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request, f"Game Session '{form.instance.game_name}' created."
        )
        return response

    def get_success_url(self):
        return f"/app/lobby/{self.object.game_id}/"


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
            reverse("session-join-direct", kwargs={"game_id": self.game_session.game_id})
        )
        context.update(
            {
                "game_session": self.game_session,
                "join_url": join_url,
            }
        )
        return context


class JoinSessionView(TemplateView):
    template_name = "game/join_session.html"
    form_class = JoinSessionForm

    def get(self, request, *args, **kwargs):
        game_id = (kwargs.get("game_id") or "").upper()
        initial = {"game_id": game_id} if game_id else None
        form = self.form_class(initial=initial)
        game_session = None
        show_password = False

        if game_id:
            game_session = GameSession.objects.filter(game_id=game_id).first()
            if game_session:
                show_password = bool(game_session.game_password)
            else:
                # Bind the form so the value persists and show a friendly error.
                form = self.form_class(data={"game_id": game_id})
                form.is_valid()
                form.add_error("game_id", "No session found with that ID.")

        context = self.get_context_data(
            form=form,
            game_session=game_session,
            show_password=show_password,
        )
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        game_session = None
        show_password = False
        awaiting_password = False

        if form.is_valid():
            game_id = form.cleaned_data["game_id"]
            try:
                game_session = GameSession.objects.get(game_id=game_id)
            except GameSession.DoesNotExist:
                form.add_error("game_id", "No session found with that ID.")
            else:
                show_password = bool(game_session.game_password)
                if show_password:
                    password = form.cleaned_data.get("game_password")
                    if not password:
                        awaiting_password = True
                    elif password != game_session.game_password:
                        form.add_error("game_password", "Incorrect password.")

            if not form.errors and not awaiting_password:
                self._mark_joined(request, game_session)
                return redirect("player-create", game_id=game_session.game_id)
        else:
            game_id = request.POST.get("game_id", "").strip().upper()
            if game_id:
                game_session = GameSession.objects.filter(game_id=game_id).first()
                show_password = bool(game_session and game_session.game_password)

        context = self.get_context_data(
            form=form,
            game_session=game_session,
            show_password=show_password or awaiting_password,
        )
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form", self.form_class())
        context["game_session"] = kwargs.get("game_session")
        context["show_password"] = kwargs.get("show_password", False)
        return context

    def _mark_joined(self, request, game_session):
        joined_ids = request.session.get("joined_game_ids", [])
        if game_session.game_id not in joined_ids:
            joined_ids.append(game_session.game_id)
            request.session["joined_game_ids"] = joined_ids
            request.session.modified = True


class PlayerCreateView(CreateView):
    template_name = "game/create_player.html"
    form_class = PlayerCreateForm
    model = Player

    def dispatch(self, request, *args, **kwargs):
        game_id = kwargs["game_id"]
        self.game_session = GameSession.objects.filter(game_id=game_id).first()
        if self.game_session is None:
            messages.error(request, "We could not find that session. Please try again.")
            return redirect("session-join-direct", game_id=game_id)
        if not self._has_join_permission(request):
            messages.error(request, "Please join the session before creating a player.")
            return redirect("session-join-direct", game_id=game_id)
        return super().dispatch(request, *args, **kwargs)

    def _has_join_permission(self, request):
        if request.user.is_authenticated and request.user == self.game_session.game_host:
            return True
        joined_ids = request.session.get("joined_game_ids", [])
        return self.game_session.game_id in joined_ids

    def form_valid(self, form):
        form.instance.game = self.game_session
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Welcome to {self.game_session.game_name}, {form.instance.name or 'player'}!",
        )
        self._mark_joined()
        return response

    def _mark_joined(self):
        joined_ids = self.request.session.get("joined_game_ids", [])
        if self.game_session.game_id not in joined_ids:
            joined_ids.append(self.game_session.game_id)
            self.request.session["joined_game_ids"] = joined_ids
            self.request.session.modified = True

    def get_success_url(self):
        return f"/app/lobby/{self.game_session.game_id}/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["game_session"] = self.game_session
        return context


class PlayerUpdateView(TemplateView):
    template_name = "game/update_player.html"
