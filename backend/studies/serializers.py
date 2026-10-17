from game.models import GameSession
from rest_framework import serializers

from studies.models import Participant, ResearchNote, Study, validate_flat_meta


class StudySerializer(serializers.ModelSerializer):
    games = serializers.SerializerMethodField()
    codes = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()

    class Meta:
        model = Study
        fields = ("id", "name", "description", "created_at", "games", "codes", "notes")
        read_only_fields = ("id", "created_at")

    # Counts, for the list; the detail page fetches the rows themselves.
    def get_games(self, study) -> int:
        return study.games.count()

    def get_codes(self, study) -> int:
        return study.codes.count()

    def get_notes(self, study) -> int:
        return study.notes.count()

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Gib der Studie einen Namen.")
        return value


class ParticipantSerializer(serializers.ModelSerializer):
    used = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = ("id", "code", "created_at", "used")

    def get_used(self, participant) -> bool:
        return participant.seats.exists()


class NoteSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    games = serializers.SlugRelatedField(
        many=True,
        slug_field="game_id",
        queryset=GameSession.objects.all(),
        required=False,
    )
    meta = serializers.JSONField(required=False)

    class Meta:
        model = ResearchNote
        fields = (
            "id",
            "author",
            "games",
            "about_date",
            "created_at",
            "updated_at",
            "text",
            "meta",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_author(self, note) -> str | None:
        return note.author.get_username() if note.author else None

    def validate_meta(self, value):
        from django.core.exceptions import ValidationError

        try:
            validate_flat_meta(value)
        except ValidationError as error:
            raise serializers.ValidationError(error.messages)
        return value

    def validate(self, attrs):
        study = self.context["study"]
        for game in attrs.get("games", []):
            link = getattr(game, "study_link", None)
            if link is None or link.study_id != study.pk:
                raise serializers.ValidationError(
                    {
                        "games": f"Das Spiel {game.game_id} gehört nicht zu dieser Studie."
                    }
                )
        return attrs
