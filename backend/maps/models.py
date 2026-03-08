# from django.core.exceptions import ValidationError
import logging
import math

from co2mmute.utils import game_map_clean
from django.core.exceptions import ValidationError
from django.db import models
from game.models import GameRound

logger = logging.getLogger(__name__)


class GameMap(models.Model):
    # add default value ASAP
    name = models.CharField(max_length=100)
    x_dim = models.PositiveSmallIntegerField(default=10)
    y_dim = models.PositiveSmallIntegerField(default=10)
    scale = models.FloatField(default=1.0)

    # Background image and transform parameters
    background_image = models.ImageField(
        upload_to="map_backgrounds/", null=True, blank=True
    )
    image_offset_x = models.FloatField(default=0.0)
    image_offset_y = models.FloatField(default=0.0)
    image_scale = models.FloatField(default=1.0)
    image_crop_top = models.FloatField(default=0.0)
    image_crop_right = models.FloatField(default=0.0)
    image_crop_bottom = models.FloatField(default=0.0)
    image_crop_left = models.FloatField(default=0.0)

    max_player = models.PositiveSmallIntegerField(default=4)

    # Default speed settings for different transport modes (km/h)
    walk_speed_kmh = models.PositiveSmallIntegerField(default=5)
    bike_speed_kmh = models.PositiveSmallIntegerField(default=20)
    default_car_speed_kmh = models.PositiveSmallIntegerField(default=50)

    created = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="author",
    )
    updated = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operator",
    )

    def __str__(self):
        return f"{self.pk} - {self.name} - ({self.max_player} Players)"

    class Meta:
        ordering = ("name", "pk")


class MapVersion(models.Model):
    game_map = models.ForeignKey(GameMap, on_delete=models.CASCADE)
    compatible_versions = models.ManyToManyField("self")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    base_version = models.BooleanField(default=False)
    poll_text = models.TextField(default="Die Karte soll ... ")
    revert_poll_text = models.TextField(default="Die Karte soll ... ")
    source_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_versions",
    )
    created = models.DateTimeField(auto_now_add=True)
    change_img = models.ImageField(upload_to="maps/", null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({'base' if self.base_version else 'version'}) - {self.game_map}"

    class Meta:
        ordering = ("game_map", "-base_version", "-pk")


class NodeType(models.Model):
    name = models.CharField(max_length=50)
    short = models.CharField(max_length=2)

    def __str__(self) -> str:
        return f"Nodetype {self.name}"

    class Meta:
        ordering = ("name", "short")


class Node(models.Model):
    game_map = models.ForeignKey(GameMap, on_delete=models.CASCADE)
    map_versions = models.ManyToManyField(MapVersion)

    name = models.CharField(max_length=100, null=True, blank=True)
    x_position = models.FloatField()
    y_position = models.FloatField()
    node_type = models.ManyToManyField(NodeType)

    def __str__(self):
        return f"Node {self.pk} in Map {self.game_map}"

    def clean(self) -> None:
        game_map_clean(self.map_versions.all(), self.game_map)
        return super().clean()

    def save(self, *args, **kwargs):
        # validate coordinates, if they fit in dimensions of map
        if not 0 <= self.x_position <= self.game_map.x_dim:
            raise ValidationError("x-coordinates out of bound")
        if not 0 <= self.y_position <= self.game_map.y_dim:
            raise ValidationError("y-coordinates out of bound")

        super().save(*args, **kwargs)

    class Meta:
        ordering = ("game_map", "name", "pk")

    def node_degree(self, subgraph):
        pass

    def has_path(self, to_node, subgraph):
        pass


class Edge(models.Model):
    class Meta:
        ordering = ("game_map", "name", "pk")

    game_map = models.ForeignKey(GameMap, on_delete=models.CASCADE)
    map_versions = models.ManyToManyField(MapVersion)
    name = models.CharField(max_length=100, blank=True, null=True)
    start_node = models.ForeignKey(
        Node, on_delete=models.CASCADE, related_name="start_node"
    )
    end_node = models.ForeignKey(
        Node, on_delete=models.CASCADE, related_name="end_node"
    )
    biking = models.BooleanField(default=True)
    walking = models.BooleanField(default=True)
    max_lanes = models.PositiveSmallIntegerField(default=1)

    def euclidean_2d_distance(self):
        dx = self.end_node.x_position - self.start_node.x_position
        dy = self.end_node.y_position - self.start_node.y_position
        return math.sqrt((dx * dx) + (dy * dy))

    def clean(self) -> None:
        game_map_clean(self.map_versions.all(), self.game_map)
        return super().clean()


class StreetEdge(models.Model):
    edge = models.ForeignKey(Edge, on_delete=models.CASCADE)
    map_versions = models.ManyToManyField(MapVersion)
    speed_limit = models.PositiveSmallIntegerField(default=50)
    lanes = models.PositiveSmallIntegerField(default=1)
    dedicated_bus_lane = models.BooleanField(default=False)

    def clean(self) -> None:
        game_map_clean(self.map_versions.all(), self.edge.game_map)
        return super().clean()

    class Meta:
        ordering = ("edge__game_map__name", "edge__name", "pk")


class StreetPerRound(models.Model):
    edge = models.ForeignKey(StreetEdge, on_delete=models.CASCADE)
    game_round = models.ForeignKey(GameRound, on_delete=models.CASCADE)
    speed_under_load = models.PositiveSmallIntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.speed_under_load and self.edge.speed_limit:
            self.speed_under_load = self.edge.speed_limit
        super().save(*args, **kwargs)


class BusLine(models.Model):
    game_map = models.ForeignKey(GameMap, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)
    map_versions = models.ManyToManyField(MapVersion)
    intervall = models.PositiveSmallIntegerField(default=5)
    bus_capacity = models.PositiveSmallIntegerField()
    bus_speed_kmh = models.PositiveSmallIntegerField(default=30)
    edges = models.ManyToManyField(StreetEdge, through="BusLineEdge")

    def clean(self) -> None:
        game_map_clean(self.map_versions.all(), self.game_map)
        return super().clean()

    class Meta:
        ordering = ("game_map", "name", "pk")


class BusLineEdge(models.Model):
    bus_line = models.ForeignKey(BusLine, on_delete=models.CASCADE)
    street_edge = models.ForeignKey(StreetEdge, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ("order",)
        unique_together = ("bus_line", "order")


class TrainEdge(models.Model):
    edge = models.ForeignKey(Edge, on_delete=models.CASCADE)
    map_versions = models.ManyToManyField(MapVersion)

    def clean(self) -> None:
        game_map_clean(self.map_versions.all(), self.edge.game_map)
        return super().clean()

    class Meta:
        ordering = ("edge__game_map__name", "edge__name", "pk")


class TrainLine(models.Model):
    game_map = models.ForeignKey(GameMap, on_delete=models.CASCADE)
    map_versions = models.ManyToManyField(MapVersion)
    name = models.CharField(max_length=20)
    intervall = models.PositiveSmallIntegerField(default=5)
    train_capacity = models.PositiveIntegerField()
    train_speed_kmh = models.PositiveSmallIntegerField(default=40)
    edges = models.ManyToManyField(TrainEdge, through="TrainLineEdge")

    def clean(self) -> None:
        game_map_clean(self.map_versions.all(), self.game_map)
        return super().clean()

    class Meta:
        ordering = ("game_map", "name", "pk")


class TrainLineEdge(models.Model):
    train_line = models.ForeignKey(TrainLine, on_delete=models.CASCADE)
    train_edge = models.ForeignKey(TrainEdge, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ("order",)
        unique_together = ("train_line", "order")
