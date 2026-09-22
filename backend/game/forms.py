from django import forms
from django.utils import timezone

from .models import GameSession, Player


class GameSessionCreateForm(forms.ModelForm):
    lobby_open = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        help_text="Optional – lege fest, wann die Lobby aufmacht.",
    )

    class Meta:
        model = GameSession
        fields = [
            "game_name",
            "game_password",
            "game_map",
            "map_updates",
            "max_players",
            "agent_per_player",
            "max_rounds",
            "max_CO2_level",
            "people_per_agent",
            "idle_end_days",
            "lobby_open",
        ]
        labels = {
            "game_name": "Name des Spiels",
            "game_password": "Passwort für die Lobby",
            "game_map": "Karte",
            "map_updates": "Kartenänderungen zulassen",
            "max_players": "Plätze insgesamt",
            "agent_per_player": "Fahrgäste pro Person",
            "max_rounds": "Runden",
            "max_CO2_level": "CO₂-Budget (kg)",
            "people_per_agent": "Menschen pro Fahrgast",
            "idle_end_days": "Ende nach Tagen ohne Spiel",
            "lobby_open": "Lobby öffnet um",
        }
        help_texts = {
            "game_password": "Optional – ohne Passwort kommt jeder in die Lobby.",
            "map_updates": (
                "Schickt Kartenänderungen während des Spiels an alle Geräte."
            ),
            "max_players": "So viele Plätze hat das Spiel insgesamt.",
            "agent_per_player": ("So viele Fahrgäste bekommt jede Person zu Beginn."),
            "max_rounds": ("So viele Runden werden gefahren, wenn das Budget reicht."),
            "max_CO2_level": "Ist das Budget aufgebraucht, ist das Spiel vorbei.",
            "people_per_agent": (
                "Für so viele Menschen steht ein Fahrgast in der Simulation."
            ),
            "idle_end_days": (
                "Ein Spiel, das so lange niemand spielt, endet von selbst – "
                "angehalten oder nicht. Einen Tag später werden die "
                "Spielernamen entfernt."
            ),
        }
        widgets = {
            "game_name": forms.TextInput(attrs={"autocomplete": "off"}),
            "game_password": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                    "placeholder": "z. B. ECO-42",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            defaults = {
                "map_updates": True,
                "max_players": 16,
                "agent_per_player": 4,
                "max_rounds": 6,
                "max_CO2_level": 500,
                "people_per_agent": 1000,
                "idle_end_days": 30,
                "lobby_open": timezone.localtime(timezone.now()).replace(
                    second=0, microsecond=0
                ),
            }
            for field_name, value in defaults.items():
                self.initial.setdefault(field_name, value)
                self.fields[field_name].initial = self.initial[field_name]
        # styling
        base_class = (
            "block w-full rounded-md bg-white px-3 py-2 text-base text-gray-900 "
            "outline outline-1 outline-gray-300 focus:outline-2 "
            "focus:outline-indigo-600   dark:bg-white/5 dark:text-white "
            "dark:outline-white/10"
        )
        checkbox_class = (
            "h-4 w-4 rounded border-gray-300 text-indigo-600 "
            "focus:ring-indigo-500 dark:bg-white/5 dark:border-white/10"
        )
        self.fields["game_map"].required = True

        self.fields["game_map"].empty_label = None  # type: ignore
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", checkbox_class)
            else:
                field.widget.attrs.setdefault("class", base_class)

    def clean(self):
        cleaned_data = super().clean()
        max_players = cleaned_data.get("max_players")
        agent_per_player = cleaned_data.get("agent_per_player")
        max_rounds = cleaned_data.get("max_rounds")
        max_co2_level = cleaned_data.get("max_CO2_level")

        if max_players is not None and max_players < 1:
            self.add_error("max_players", "Es muss mindestens einen Platz geben.")

        if agent_per_player is not None:
            if agent_per_player < 1:
                self.add_error(
                    "agent_per_player",
                    "Jede Person braucht mindestens einen Fahrgast.",
                )
            if max_players is not None and agent_per_player > max_players:
                self.add_error(
                    "agent_per_player",
                    "Mehr Fahrgäste pro Person als Plätze im Spiel geht nicht.",
                )

        if max_rounds is not None and max_rounds < 1:
            self.add_error(
                "max_rounds", "Es muss mindestens eine Runde gefahren werden."
            )

        if max_co2_level is not None and max_co2_level < 1:
            self.add_error(
                "max_CO2_level", "Das CO₂-Budget muss mindestens ein Kilogramm sein."
            )

        people_per_agent = cleaned_data.get("people_per_agent")
        if people_per_agent is not None and people_per_agent < 1:
            self.add_error(
                "people_per_agent",
                "Ein Fahrgast muss für mindestens einen Menschen stehen.",
            )

        return cleaned_data

    def clean_lobby_open(self):
        lobby_open = self.cleaned_data.get("lobby_open")
        if lobby_open is None:
            return lobby_open
        if timezone.is_naive(lobby_open):
            lobby_open = timezone.make_aware(
                lobby_open, timezone.get_current_timezone()
            )
        return lobby_open


class PlayerCreateForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ["name"]
        labels = {"name": "Dein Name"}
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = (
            "block w-full rounded-md bg-white px-3 py-2 text-base text-gray-900 "
            "outline outline-1 outline-gray-300 focus:outline-2 "
            "focus:outline-indigo-600 dark:bg-white/5 dark:text-white "
            "dark:outline-white/10"
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", base_class)


class JoinSessionForm(forms.Form):
    game_id = forms.CharField(
        max_length=6,
        label="Spiel-ID",
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "autocapitalize": "characters"}
        ),
    )
    game_password = forms.CharField(
        max_length=50,
        required=False,
        label="Passwort",
        widget=forms.PasswordInput(render_value=False),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        text_class = (
            "block w-full rounded-md bg-white px-3 py-2 text-base text-gray-900 "
            "outline outline-1 outline-gray-300 focus:outline-2 "
            "focus:outline-indigo-600 dark:bg-white/5 dark:text-white "
            "dark:outline-white/10"
        )
        self.fields["game_id"].widget.attrs.setdefault("class", text_class)
        self.fields["game_password"].widget.attrs.setdefault("class", text_class)

    def clean_game_id(self):
        game_id = self.cleaned_data["game_id"].strip().upper()
        if not game_id:
            raise forms.ValidationError("Gib eine Spiel-ID ein.")
        return game_id
