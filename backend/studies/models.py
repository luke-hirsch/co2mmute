"""A study: games the research group looks at together, and the people in them.

The app is optional. `game` never imports it — a foreign key from a game to a
study would break `game` and its migrations the moment the app is switched off —
so everything here points at `game`, never the other way round.
"""

import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from game.seats import CODE_ALPHABET

# A game id has 6 characters and a seat code 7; the length is what tells a
# participant code apart, so the join page and the privacy text read this.
PARTICIPANT_CODE_LENGTH = 8


def new_participant_code() -> str:
    return "".join(
        secrets.choice(CODE_ALPHABET) for _ in range(PARTICIPANT_CODE_LENGTH)
    )


class Study(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name_plural = "studies"

    def __str__(self):
        return self.name


class Participant(models.Model):
    """A code a person plays with. It names nobody: the site never stores whose."""

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="codes")
    # Unique across all studies: a code is looked up on its own.
    code = models.CharField(max_length=PARTICIPANT_CODE_LENGTH, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("pk",)

    def __str__(self):
        return self.code


class StudyGame(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="games")
    # A game is in at most one study.
    game = models.OneToOneField(
        "game.GameSession", on_delete=models.CASCADE, related_name="study_link"
    )

    class Meta:
        ordering = ("pk",)


class StudySeat(models.Model):
    """Which participant code sat on which seat.

    The participant is PROTECT: a seat's moves are the data, and a code that
    tied them together must not vanish under them. Deleting the game deletes its
    seats, which frees the code.
    """

    participant = models.ForeignKey(
        Participant, on_delete=models.PROTECT, related_name="seats"
    )
    player = models.OneToOneField(
        "game.Player", on_delete=models.CASCADE, related_name="study_seat"
    )
    game = models.ForeignKey("game.GameSession", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            # A code plays once per game.
            models.UniqueConstraint(
                fields=("participant", "game"), name="one_seat_per_code_and_game"
            ),
        ]


def validate_flat_meta(value):
    """`{"Feld": "Wert"}`: string keys, string, number or boolean values."""
    if not isinstance(value, dict):
        raise ValidationError("Das muss eine Liste aus Feld und Wert sein.")
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValidationError("Jedes Feld braucht einen Namen.")
        if not isinstance(item, (str, int, float, bool)):
            raise ValidationError(
                f"»{key}«: Der Wert muss Text, eine Zahl oder ja/nein sein."
            )


class ResearchNote(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="notes")
    # The account may go; the note stays.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    games = models.ManyToManyField("game.GameSession", blank=True, related_name="+")
    about_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    text = models.TextField(blank=True)
    meta = models.JSONField(default=dict, blank=True, validators=[validate_flat_meta])

    class Meta:
        ordering = ("-created_at", "-pk")
