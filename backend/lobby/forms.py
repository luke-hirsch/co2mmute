from django import forms
from .models import Session


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = [
            "session_name",
            "session_status",
            "session_password",
            "max_players",
            "max_agents",
            "max_rounds",
            "co2_budget",
            "rule_updates",
            "started_at",
            "ended_at",
            "cleanup_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
