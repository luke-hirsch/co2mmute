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

    # What a game on this map is played against. Both belong here rather than
    # in code because both are properties of THIS graph: how much traffic its
    # corridors carry, and what a playable round costs on its distances and
    # its timetable. Another city is another pair. `game/calibration.py` has
    # the measurements the shipped defaults come from — they are
    # Berlin_Mitte-West's, and a smaller map wants smaller ones.
    district_commuters = models.PositiveIntegerField(
        default=6400,
        help_text=(
            "Pendler, die die Straßen dieser Karte im Berufsverkehr "
            "verkraften. Wird auf die Fahrgäste aufgeteilt, damit auf der "
            "Karte gleich viel Verkehr ist, egal wie viele mitspielen."
        ),
    )
    co2_budget_kg_per_round = models.PositiveIntegerField(
        default=8000,
        help_text=(
            "Vorschlag für das CO₂-Budget, pro Runde in kg. Genug, wenn die "
            "Klasse umsteigt, zu wenig, wenn alle mit dem Auto fahren."
        ),
    )

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

    def offers_map_changes(self, from_version=None) -> bool:
        """Whether a game on this map can ever reach a ballot.

        `vote_options()` answers the same question for a finished round. This
        one answers it before the first round — for the map select and the
        lobby, where a host can still choose a different map. A map whose
        active version reaches no compatible version removes the discussion
        and the vote from the game silently: `_advance_from_stats` is
        "discussion if there is a ballot, else the next round".

        `from_version` defaults to the base version, because
        `active_map_version` is only set when the game starts.
        """
        version = (
            from_version
            or MapVersion.objects.filter(game_map=self, base_version=True).first()
        )
        if version is None:
            return False
        return version.compatible_versions.exists()


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
        return f"{self.game_map} -  {'base' if self.base_version else {self.name}}"

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


class EdgeQuerySet(models.QuerySet):
    def rail_only(self):
        """Edges that carry rail and no street: a railway, not a street.

        The set the 0005 data pass clears `biking` and `walking` on. Written
        here rather than inline in the migration so it can be tested without
        importing a module whose name starts with a digit, and so the next
        caller has one definition to use. Same shape as
        `Player.objects.playing()`.
        """
        return self.filter(trainedge__isnull=False, streetedge__isnull=True).distinct()


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
    bike_lane = models.BooleanField(default=False)
    walking = models.BooleanField(default=True)
    max_lanes = models.PositiveSmallIntegerField(default=1)

    objects = EdgeQuerySet.as_manager()

    def euclidean_2d_distance(self):
        dx = self.end_node.x_position - self.start_node.x_position
        dy = self.end_node.y_position - self.start_node.y_position
        return math.sqrt((dx * dx) + (dy * dy))

    def clean(self) -> None:
        if self.bike_lane and not self.biking:
            raise ValidationError(
                {
                    "bike_lane": (
                        "Eine Kante mit Radweg muss auch fuer Raeder freigegeben sein."
                    )
                }
            )
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
    bus_capacity = models.PositiveSmallIntegerField(default=85)
    bus_speed_kmh = models.PositiveSmallIntegerField(default=30)
    edges = models.ManyToManyField(StreetEdge, through="BusLineEdge")

    def clean(self) -> None:
        game_map_clean(self.map_versions.all(), self.game_map)
        return super().clean()

    class Meta:
        ordering = ("game_map", "name", "pk")


class BusLineEdge(models.Model):
    """One link of a bus line's chain, in the versions that run it.

    The chain is version-scoped like every other element of the graph, because
    a version that changes a street clones it and the line has to run over the
    clone *there* while the other versions keep running over the original. Two
    rows of the same line therefore legitimately share an `order` — one per
    version — which is why there is no `unique_together` on it any more; a
    reader filters by version first and gets one row per order back.

    A row that names no version is in no version. The only paths that create
    one are the importer, the two line endpoints and the version builders, and
    each of them says which versions the row belongs to.
    """

    bus_line = models.ForeignKey(BusLine, on_delete=models.CASCADE)
    street_edge = models.ForeignKey(StreetEdge, on_delete=models.CASCADE)
    map_versions = models.ManyToManyField(MapVersion)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ("order",)


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
    train_capacity = models.PositiveIntegerField(default=1000)
    train_speed_kmh = models.PositiveSmallIntegerField(default=40)
    edges = models.ManyToManyField(TrainEdge, through="TrainLineEdge")

    def clean(self) -> None:
        game_map_clean(self.map_versions.all(), self.game_map)
        return super().clean()

    class Meta:
        ordering = ("game_map", "name", "pk")


class TrainLineEdge(models.Model):
    """One link of a train line's chain, in the versions that run it.

    Same shape and the same reason as `BusLineEdge` — and it is not only the
    bus lines that need it: a `"type": "both"` edge carries a rail alignment
    too, so a version drawn over a street moved `U2`'s chain as well.
    """

    train_line = models.ForeignKey(TrainLine, on_delete=models.CASCADE)
    train_edge = models.ForeignKey(TrainEdge, on_delete=models.CASCADE)
    map_versions = models.ManyToManyField(MapVersion)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ("order",)
