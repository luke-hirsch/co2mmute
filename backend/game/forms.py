from django import forms

from .models import Player


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
