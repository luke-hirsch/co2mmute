import logging
import uuid
from io import BytesIO

import qrcode
from co2mmute.utils import per_passenger
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models

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
    active_map_version = models.ForeignKey(
        "maps.MapVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_in_sessions",
    )
    max_players = models.PositiveIntegerField()
    agent_per_player = models.PositiveIntegerField()
    max_rounds = models.PositiveIntegerField()
    max_CO2_level = models.PositiveIntegerField()  # in kg
    chat_enabled = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False)

    # Simulation parameters
    people_per_agent = models.PositiveIntegerField(default=1000)
    tick_duration_min = models.PositiveSmallIntegerField(default=5)
    morning_departure_hour = models.PositiveSmallIntegerField(default=9)  # 9:00 AM
    evening_departure_hour = models.PositiveSmallIntegerField(default=17)  # 5:00 PM
    departure_std_dev_min = models.PositiveSmallIntegerField(default=10)  # Standard deviation for departure times

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
    # Agent assignments: {"home_node": int, "agents": [{"id": 1, "destination_node": int}, ...]}
    agent_assignments = models.JSONField(blank=True, null=True)

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
    total_emissions_g = models.FloatField(default=0.0)  # in grams
    total_cost_eur = models.FloatField(default=0.0)

    class BetweenRoundPhase(models.TextChoices):
        NONE = "none", "None"
        STATS = "stats", "Stats Review"
        DISCUSSION = "discussion", "Discussion"
        VOTING = "voting", "Voting"
        STALEMATE = "stalemate", "Stalemate"

    between_round_phase = models.CharField(
        max_length=20,
        choices=BetweenRoundPhase.choices,
        default=BetweenRoundPhase.NONE,
    )
    stalemate_count = models.PositiveSmallIntegerField(default=0)

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
    session_round = models.ForeignKey(
        GameRound, on_delete=models.CASCADE, related_name="moves"
    )
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="moves")
    action = models.CharField(max_length=50)
    payload = models.JSONField(blank=True, default=dict)
    moved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("session_round", "player"),)
        ordering = ("session_round", "moved_at")

    def __str__(self):
        return f"Move by {self.player} in round {self.session_round.round_number}"

    def clean(self):
        if self.player.game.pk != self.session_round.game.pk:
            raise ValidationError("Player must belong to the same game as the round.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class CarMobility(models.Model):
    session_round = models.ForeignKey(GameRound, on_delete=models.CASCADE)

    base_emissions_g_per_km = models.FloatField(default=166.8)  # g CO2e / vehicle-km
    base_cost_per_km = models.FloatField(default=0.32)  # € / vehicle-km

    def emissions_per_km(self, passengers_onboard: float = 1.0) -> float:
        return per_passenger(self.base_emissions_g_per_km, passengers_onboard)

    def cost_per_km(self, passengers_onboard: float = 1.0) -> float:
        return per_passenger(self.base_cost_per_km, passengers_onboard)


class TrainMobility(models.Model):
    session_round = models.ForeignKey(GameRound, on_delete=models.CASCADE)
    base_emissions_g_per_km = models.FloatField(default=3500.0)  # g CO2e / vehicle-km
    base_cost_per_km = models.FloatField(default=12.0)  # € / vehicle-km

    def emissions_per_km(self, passengers_onboard: float) -> float:
        return per_passenger(self.base_emissions_g_per_km, passengers_onboard)

    def cost_per_km(self, passengers_onboard: float) -> float:
        return per_passenger(self.base_cost_per_km, passengers_onboard)


class BusMobility(models.Model):
    session_round = models.ForeignKey(GameRound, on_delete=models.CASCADE)
    base_emissions_g_per_km = models.FloatField(default=1200.0)  # g CO2e / vehicle-km
    base_cost_per_km = models.FloatField(default=4.5)  # € / vehicle-km

    def emissions_per_km(self, passengers_onboard: float) -> float:
        return per_passenger(self.base_emissions_g_per_km, passengers_onboard)

    def cost_per_km(self, passengers_onboard: float) -> float:
        return per_passenger(self.base_cost_per_km, passengers_onboard)


class BikeMobility(models.Model):
    session_round = models.ForeignKey(GameRound, on_delete=models.CASCADE)

    emissions_g_per_km = models.FloatField(default=18.0)  # g CO2e / passenger-km
    cost_per_km = models.FloatField(default=0.08)  # € / passenger-km


class WalkingMobility(models.Model):
    session_round = models.ForeignKey(GameRound, on_delete=models.CASCADE)


# =============================================================================
# Route Storage Models (for traffic simulation)
# =============================================================================


class AgentRoute(models.Model):
    """Stores the route submitted by a player for a specific agent."""

    class TransportMode(models.TextChoices):
        CAR = "car", "Car"
        PUBLIC = "public", "Public Transport"
        BIKE = "bike", "Bike"
        WALK = "walk", "Walk"

    class Optimization(models.TextChoices):
        TIME = "time", "Fastest"
        DISTANCE = "distance", "Shortest"
        CO2 = "co2", "Lowest CO2"

    player_move = models.ForeignKey(
        PlayerMove, on_delete=models.CASCADE, related_name="routes"
    )
    agent_id = models.PositiveSmallIntegerField()
    transport_mode = models.CharField(
        max_length=20, choices=TransportMode.choices
    )
    optimization = models.CharField(
        max_length=20, choices=Optimization.choices, null=True, blank=True
    )
    total_distance_m = models.FloatField()
    estimated_time_min = models.FloatField()

    class Meta:
        unique_together = (("player_move", "agent_id"),)
        ordering = ("player_move", "agent_id")

    def __str__(self):
        return f"Route for agent {self.agent_id} in {self.player_move}"


class RouteSegment(models.Model):
    """Individual segment of a route (an edge with transport mode)."""

    class SegmentMode(models.TextChoices):
        CAR = "car", "Car"
        BUS = "bus", "Bus"
        TRAIN = "train", "Train"
        BIKE = "bike", "Bike"
        WALK = "walk", "Walk"

    agent_route = models.ForeignKey(
        AgentRoute, on_delete=models.CASCADE, related_name="segments"
    )
    order = models.PositiveSmallIntegerField()
    edge = models.ForeignKey("maps.Edge", on_delete=models.CASCADE)
    mode = models.CharField(max_length=20, choices=SegmentMode.choices)
    pt_line_id = models.PositiveIntegerField(null=True, blank=True)  # BusLine or TrainLine ID

    class Meta:
        ordering = ("agent_route", "order")
        unique_together = (("agent_route", "order"),)

    def __str__(self):
        return f"Segment {self.order} of {self.agent_route}"


# =============================================================================
# Simulation Result Models
# =============================================================================


class SimulationResult(models.Model):
    """Results of traffic simulation for a round."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    game_round = models.OneToOneField(
        GameRound, on_delete=models.CASCADE, related_name="simulation"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_co2_g = models.FloatField(default=0.0)
    total_cost_eur = models.FloatField(default=0.0)
    error_message = models.TextField(null=True, blank=True)
    detailed_log = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Simulation for {self.game_round}"


class AgentSimulationResult(models.Model):
    """Per-agent simulation results."""

    simulation = models.ForeignKey(
        SimulationResult, on_delete=models.CASCADE, related_name="agent_results"
    )
    agent_route = models.ForeignKey(
        AgentRoute, on_delete=models.CASCADE, related_name="simulation_results"
    )
    mean_trip_time_min = models.FloatField()
    mean_return_time_min = models.FloatField(default=0.0)
    mean_cost_eur = models.FloatField()
    total_co2_g = models.FloatField()
    congestion_delay_min = models.FloatField(default=0.0)
    wait_time_min = models.FloatField(default=0.0)  # For public transport

    class Meta:
        unique_together = (("simulation", "agent_route"),)

    def __str__(self):
        return f"Result for {self.agent_route}"


class EdgeTrafficSnapshot(models.Model):
    """Traffic state per edge per time tick for replay/analysis."""

    simulation = models.ForeignKey(
        SimulationResult, on_delete=models.CASCADE, related_name="traffic_snapshots"
    )
    edge = models.ForeignKey("maps.Edge", on_delete=models.CASCADE)
    time_tick = models.PositiveSmallIntegerField()  # Minutes from simulation start
    vehicle_count = models.PositiveIntegerField()
    speed_kmh = models.FloatField()  # Actual speed after congestion

    class Meta:
        unique_together = (("simulation", "edge", "time_tick"),)
        ordering = ("simulation", "time_tick", "edge")

    def __str__(self):
        return f"Traffic on edge {self.edge.id} at tick {self.time_tick}"


# =============================================================================
# Voting Models
# =============================================================================


class MapVersionVote(models.Model):
    """Records a player's vote for a map version between rounds."""

    game_round = models.ForeignKey(
        GameRound, on_delete=models.CASCADE, related_name="map_votes"
    )
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="map_votes"
    )
    map_version = models.ForeignKey(
        "maps.MapVersion",
        on_delete=models.CASCADE,
        null=True,
        blank=True,  # null = "Leave as it is"
    )
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("game_round", "player"),)
        ordering = ("game_round", "voted_at")

    def __str__(self):
        version_name = self.map_version.name if self.map_version else "Leave as is"
        return f"Vote by {self.player} in round {self.game_round.round_number}: {version_name}"


class StalemateVote(models.Model):
    """Records a player's vote on whether to revote after a stalemate."""

    game_round = models.ForeignKey(
        GameRound, on_delete=models.CASCADE, related_name="stalemate_votes"
    )
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="stalemate_votes"
    )
    want_revote = models.BooleanField()
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("game_round", "player"),)
        ordering = ("game_round", "voted_at")

    def __str__(self):
        choice = "revote" if self.want_revote else "leave as is"
        return f"Stalemate vote by {self.player} in round {self.game_round.round_number}: {choice}"
