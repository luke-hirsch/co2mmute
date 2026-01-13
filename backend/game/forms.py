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
        help_text="Optionally choose when the lobby should open.",
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
            "lobby_open",
        ]
        labels = {
            "game_name": "Session name",
            "game_password": "Lobby password",
            "game_map": "Map",
            "map_updates": "Enable map updates",
            "max_players": "Maximum players",
            "agent_per_player": "Agents per player",
            "max_rounds": "Maximum rounds",
            "max_CO2_level": "Maximum CO₂ level (kg)",
            "lobby_open": "Lobby opens at",
        }
        help_texts = {
            "game_password": "Optional – leave blank for an open lobby.",
            "map_updates": "Send live map updates to players during the session.",
            "max_players": "Total number of player slots available.",
            "agent_per_player": "Number of agents assigned to each player.",
            "max_rounds": "How many rounds the session should run for.",
            "max_CO2_level": "Upper limit before the game ends.",
        }
        widgets = {
            "game_name": forms.TextInput(attrs={"autocomplete": "off"}),
            "game_password": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                    "placeholder": "e.g. ECO-42",
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
            self.add_error("max_players", "Please allow at least one player.")

        if agent_per_player is not None:
            if agent_per_player < 1:
                self.add_error(
                    "agent_per_player", "Each player needs at least one agent."
                )
            if max_players is not None and agent_per_player > max_players:
                self.add_error(
                    "agent_per_player",
                    "Agents per player cannot exceed the maximum number of players.",
                )

        if max_rounds is not None and max_rounds < 1:
            self.add_error("max_rounds", "Maximum rounds must be at least one.")

        if max_co2_level is not None and max_co2_level < 1:
            self.add_error(
                "max_CO2_level", "Maximum CO₂ level must be at least one kilogram."
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
        labels = {"name": "Display name"}
        help_texts = {"name": "Pick the name that other players will see in the lobby."}
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
        label="Session ID",
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "autocapitalize": "characters"}
        ),
    )
    game_password = forms.CharField(
        max_length=50,
        required=False,
        label="Session password",
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
            raise forms.ValidationError("Please enter a session ID.")
        return game_id
