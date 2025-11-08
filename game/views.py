from django.views.generic.edit import CreateView
from .models import Session

# Create your views here.


class SessionCreateView(CreateView):
    model = Session
    fields = ["max_rounds", "wins_to_win"]
    template_name = "game/session_form.html"
    success_url = "/sessions/"
