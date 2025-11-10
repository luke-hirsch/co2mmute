import uuid
from django.db import models
from django.contrib.auth.password_validation import validate_password


class MoveChoice(models.TextChoices):
    """placeholder class for coin flip choices. will not be used as soon as real game engine is implemented"""

    ROCK = "rock", "Rock"
    PAPER = "paper", "Paper"
    SCISSORS = "scissors", "Scissors"


class Session(models.Model):
    class SessionStatus(models.TextChoices):
        OPEN = "open", "Open"
        ACTIVE = "active", "Active"
        TERMINATED = "terminated", "Terminated"

    # session metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="created_sessions",
    )
    session_id = models.CharField(max_length=6, editable=False)
    session_status = models.CharField(
        max_length=10,
        choices=SessionStatus.choices,
        default=SessionStatus.OPEN,
    )
    session_name = models.CharField(max_length=150, default="New Session")
    session_password = models.CharField(max_length=128, null=True, blank=True)
    qr_code = models.ImageField(upload_to="qr_codes/", null=True, blank=True)
    # game settings
    # map = models.ForeignKey(
    #     "Map",
    #     on_delete=models.DEFAULT, default=1, related_name="sessions"
    # )  # placeholder for future map model
    max_players = models.PositiveSmallIntegerField(default=4)
    max_agents = models.PositiveSmallIntegerField(default=4)
    max_rounds = models.PositiveSmallIntegerField(default=10)
    co2_budget = models.PositiveIntegerField(default=1000)  # in kg
    rule_updates = models.BooleanField(default=False)
    # timestamps for game phases
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    cleanup_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.session_id} ({self.session_status})"

    def __save__(self, *args, **kwargs):
        # Ensure that max_players is at least 2
        if self.max_players < 1:
            raise ValueError("max_players must be at least 1.")
        if self.max_agents < 1:
            raise ValueError("max_agents must be at least 1.")
        if self.session_password:
            validate_password(self.session_password, self.created_by)
        if not self.session_id:
            # Generate a unique 6-character alphanumeric session ID
            active_statuses = [
                Session.SessionStatus.ACTIVE,
                Session.SessionStatus.OPEN,
            ]
            while True:
                new_id = uuid.uuid4().hex[:6].upper()
                if not Session.objects.filter(
                    session_id=new_id,
                    session_status__in=active_statuses,
                ).exists():
                    self.session_id = new_id
                    break
        if not self.qr_code:
            self.create_qr_code()
        super().save(*args, **kwargs)

    def create_qr_code(self):
        """Placeholder method for QR code generation."""
        pass


class Player(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "session"),
                name="unique_player_per_session",
            ),
        ]

    name = models.CharField(max_length=150)
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        related_name="players",
        null=True,
        blank=True,
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="players",
    )
    score = models.IntegerField(default=0)

    def __str__(self):
        return f"Player {self.name} in Session {self.session.session_id} with score {self.score}"


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
