from django.db import models
from lobby.models import Session, Player


class MoveChoice(models.TextChoices):
    """placeholder class for coin flip choices. will not be used as soon as real game engine is implemented"""

    ROCK = "rock", "Rock"
    PAPER = "paper", "Paper"
    SCISSORS = "scissors", "Scissors"


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
        return f"Move by {self.player.name} at {self.timestamp}"
