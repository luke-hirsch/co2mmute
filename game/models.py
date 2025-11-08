import uuid
from django.db import models


class MoveChoice(models.TextChoices):
    """placeholder class for coin flip choices. will not be used as soon as real game engine is implemented"""

    ROCK = "r", "rock"
    PAPER = "p", "paper"
    SCISSORS = "s", "scissors"


class Session(models.Model):
    class SessionStatus(models.TextChoices):
        OPEN = "open", "Open"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        TERMINATED = "terminated", "Terminated"

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="created_sessions",
    )
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    session_status = models.CharField(
        max_length=10,
        choices=SessionStatus.choices,
        default=SessionStatus.OPEN,
    )
    max_rounds = models.PositiveSmallIntegerField(default=10)
    wins_to_win = models.PositiveSmallIntegerField(default=5)
    ended_at = models.DateTimeField(null=True, blank=True)
    cleanup_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.session_id} ({self.session_status})"


class Player(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "session"),
                name="unique_player_per_session",
            ),
        ]

    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="game_players",
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="players",
    )
    score = models.IntegerField(default=0)

    def __str__(self):
        return f"Player {self.user.username} in Session {self.session.session_id} with score {self.score}"


class Round(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("session", "round_number"),
                name="unique_round_number_per_session",
            ),
        ]

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="rounds",
    )
    round_number = models.PositiveSmallIntegerField()
    result = models.CharField(
        choices=MoveChoice.choices,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"Round {self.round_number} in Session {self.session.session_id} with result {self.result}"


class PlayerMove(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("player", "round"),
                name="unique_player_move_per_round",
            ),
        ]

    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="moves",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
        related_name="moves",
    )
    move_choice = models.CharField(
        max_length=10,
        choices=MoveChoice.choices,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"Move by {self.player.user.username} at {self.timestamp}"
