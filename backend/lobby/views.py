from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, render, redirect
from django.views.generic import DetailView, ListView, View
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from .forms import SessionForm
from .models import Session


### Session Views ###
class SessionListView(ListView):
    model = Session
    template_name = "game/session_list.html"
    context_object_name = "sessions"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_staff or user.is_superuser:
            return qs
        return qs.filter(created_by=user)


class SessionDetailView(UserPassesTestMixin, DetailView):
    model = Session
    template_name = "game/session_detail.html"
    context_object_name = "session"

    def test_func(self):
        session = self.get_object()
        if not isinstance(session, Session):
            raise ValueError("Invalid session object")
        user = self.request.user
        return user.is_authenticated and (
            user == session.created_by or user.is_staff or user.is_superuser
        )


class SessionCreateView(CreateView, LoginRequiredMixin):
    model = Session
    form_class = SessionForm
    template_name = "game/session_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("session_detail", kwargs={"pk": self.object.pk})  # type: ignore


class SessionUpdateView(UserPassesTestMixin, UpdateView):
    model = Session
    form_class = SessionForm
    template_name = "game/session_form.html"

    def test_func(self):
        session = self.get_object()
        if not isinstance(session, Session):
            raise ValueError("Invalid session object")
        user = self.request.user
        return user.is_authenticated and (
            user == session.created_by or user.is_staff or user.is_superuser
        )

    def get_success_url(self):
        return reverse_lazy("session_detail", kwargs={"pk": self.object.pk})  # type: ignore


class SessionDeleteView(UserPassesTestMixin, DeleteView):
    model = Session
    template_name = "game/session_confirm_delete.html"
    success_url = reverse_lazy("session_list")

    def test_func(self):
        session = self.get_object()
        if not isinstance(session, Session):
            return False
        user = self.request.user
        return user.is_authenticated and (
            user == session.created_by or user.is_staff or user.is_superuser
        )


class JoinSessionView(View):
    def get(self, request, *args, **kwargs):
        """Display join session form."""
        session = get_object_or_404(Session, session_id=kwargs.get("session_id"))
        return render(request, "game/join_session.html", {"session": session})

    def post(self, request, *args, **kwargs):
        """Handle joining a session."""
        session = get_object_or_404(Session, session_id=kwargs.get("session_id"))
        if (
            session.session_password
            and request.POST.get("session_password") != session.session_password
        ):
            return render(
                request,
                "game/join_session.html",
                {
                    "session": session,
                    "msg": "Incorrect password. Please try again.",
                },
            )
        return redirect("game")
