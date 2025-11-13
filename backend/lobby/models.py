from io import BytesIO
import uuid
import logging
import qrcode
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class GameSession(models.Model):
    game_host = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    game_name = models.CharField(max_length=100)
    game_id = models.CharField(max_length=6, unique=True)
    game_password = models.CharField(max_length=50, null=True, blank=True)
    game_qr_code = models.ImageField(upload_to="qr_codes/", null=True, blank=True)
    map = models.ForeignKey(
        "maps.GameMap", on_delete=models.SET_NULL, null=True, blank=True
    )
    map_updates = models.BooleanField(default=False)
    max_players = models.PositiveIntegerField()
    agent_per_player = models.PositiveIntegerField()
    max_rounds = models.PositiveIntegerField()
    max_CO2_level = models.PositiveIntegerField()  # in kg

    lobby_open = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.game_name

    def save(self, *args, **kwargs):
        if not self.game_id:
            self.game_id = self.generate_unique_game_id()
        if not self.game_qr_code:
            qr_code_path, qr_image = self.generate_qr_code()
            self.game_qr_code.save(qr_code_path, qr_image, save=False)
        if (
            timezone.now() < self.lobby_open
            or self.started_at is not None
            or self.ended_at is not None
            or self.map is None
        ):
            self.is_active = False
        super().save(*args, **kwargs)

    def generate_unique_game_id(self):
        i = 0
        while True:
            i += 1
            game_id = str(uuid.uuid4())[:6].upper()
            if not GameSession.objects.filter(game_id=game_id).exists():
                logger.info(f"Generated unique game_id '{game_id}' after {i} attempts.")
                return game_id

    def generate_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=4,
        )
        qr.add_data(f"http://example.com/join/{self.game_id}")
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer)
        buffer.seek(0)

        return f"qr_codes/{self.game_id}.png", ContentFile(buffer.read())


class Player(models.Model):
    name = models.CharField(max_length=100)
    player_id = models.CharField(max_length=6, editable=False, null=True, blank=True)
    user = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    game = models.ForeignKey(GameSession, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} in {self.game.game_name}"

    def save(self, *args, **kwargs):
        if not self.player_id:
            self.player_id = self.generate_unique_player_id()

        super().save(*args, **kwargs)

    def generate_unique_player_id(self):
        i = 0
        while True:
            i += 1
            player_id = str(uuid.uuid4())[:6].upper()
            if not Player.objects.filter(game=self.game, player_id=player_id).exists():
                logger.info(
                    f"Generated unique game_id '{player_id}' after {i} attempts."
                )
                return player_id
