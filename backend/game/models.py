from io import BytesIO
import logging
import uuid

import qrcode
from django.core.files.base import ContentFile
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class GameSession(models.Model):
    game_host = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    game_name = models.CharField(max_length=100)
    game_id = models.CharField(max_length=6, unique=True)
    game_password = models.CharField(max_length=50, null=True, blank=True)
    game_qr_code = models.ImageField(upload_to="qr_codes/", null=True, blank=True)
    game_map = models.ForeignKey(
        "maps.GameMap", on_delete=models.SET_NULL, null=True, blank=True
    )
    map_updates = models.BooleanField(default=False)
    max_players = models.PositiveIntegerField()
    agent_per_player = models.PositiveIntegerField()
    max_rounds = models.PositiveIntegerField()
    max_CO2_level = models.PositiveIntegerField()  # in kg
    lobby_open = models.BooleanField(default=True)
    chat_enabled = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return self.game_name

    def save(self, *args, **kwargs):
        if not self.game_id:
            self.game_id = self.generate_unique_game_id()
        if not self.game_qr_code:
            qr_code_path, qr_image = self.generate_qr_code()
            self.game_qr_code.save(qr_code_path, qr_image, save=False)

        # Only force is_active=False if conditions don't allow the game to be active
        # A game can be active if:
        # - Game has started (started_at is set)
        # - Game hasn't ended (ended_at is None)
        # - Map is selected (game_map is not None)
        if self.ended_at is not None or self.game_map is None:
            self.is_active = False

        super().save(*args, **kwargs)

    def generate_unique_game_id(self, max_retries=5):
        for _ in range(1, max_retries + 1):
            game_id = uuid.uuid4().hex[:6].upper()

            if not GameSession.objects.filter(game_id=game_id).exists():
                return game_id

        logger.error("Failed to generate unique game_id after multiple retries.")
        raise RuntimeError("Could not assign unique game_id.")

    def generate_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=4,
        )

        join_url = f"{settings.BASE_URL}/join/{self.game_id}/"
        qr.add_data(join_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer)
        buffer.seek(0)

        return f"{self.game_id}.png", ContentFile(buffer.read())


class Player(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    game = models.ForeignKey(GameSession, on_delete=models.CASCADE)
    player_id = models.CharField(max_length=6, editable=False, null=True, blank=True)
    user = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    is_muted = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    controlled_by_host = models.BooleanField(default=False)

    class Meta:
        ordering = ("game", "name", "joined_at")

    def __str__(self):
        return f"{self.name} in {self.game.game_name}"

    def save(self, *args, **kwargs):
        if not self.player_id:
            self.player_id = "P-" + str(self.generate_unique_player_id())

        super().save(*args, **kwargs)

    def generate_unique_player_id(self, max_retries=5):
        for _ in range(1, max_retries + 1):
            player_id = uuid.uuid4().hex[:4].upper()

            if not Player.objects.filter(game=self.game, player_id=player_id).exists():
                return player_id

        logger.error(
            f"Failed to generate unique player_id for game {self.game} after {max_retries} attempts."
        )
        raise RuntimeError("Could not assign a unique 6-char player ID.")


class GameRound(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    game = models.ForeignKey(
        GameSession, on_delete=models.CASCADE, related_name="rounds"
    )
    round_number = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("game", "round_number"),)
        ordering = ("game", "round_number")

    def __str__(self):
        return f"Round {self.round_number} of {self.game}"

    def save(self, *args, **kwargs):
        if not self.round_number:
            last_round = (
                GameRound.objects.filter(game=self.game)
                .order_by("-round_number")
                .first()
            )
            self.round_number = 1 if last_round is None else last_round.round_number + 1
        super().save(*args, **kwargs)


class PlayerMove(models.Model):
    game_round = models.ForeignKey(
        GameRound, on_delete=models.CASCADE, related_name="moves"
    )
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="moves")
    action = models.CharField(max_length=50)
    payload = models.JSONField(blank=True, default=dict)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("game_round", "player"),)
        ordering = ("game_round", "started_at")

    def __str__(self):
        return f"Move by {self.player} in round {self.game_round.round_number}"

    def clean(self):
        if self.player.game.pk != self.game_round.game.pk:
            raise ValidationError("Player must belong to the same game as the round.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
