# from django.core.exceptions import ValidationError
from django.db import models
import logging
import math
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class GameMap(models.Model):
    # add default value ASAP
    name = models.CharField(max_length=100)
    x_dim = models.PositiveSmallIntegerField(default=10)
    y_dim = models.PositiveSmallIntegerField(default=10)
    scale = models.FloatField(default=1.0)

    created = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    updated = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.pk} - {self.name}"


class NodeType(models.Model):
    name = models.CharField(max_length=50)
    short = models.CharField(max_length=2)

    def __str__(self) -> str:
        return f"Nodetype {self.name}"


class Node(models.Model):
    game_map = models.ForeignKey(GameMap, on_delete=models.CASCADE)
    name = models.CharField(max_length=20, null=True, blank=True)
    x_position = models.FloatField()
    y_position = models.FloatField()
    node_type = models.ManyToManyField(NodeType)

    def __str__(self):
        return f"Node {self.pk} in Map {self.game_map}"

    def save(self, *args, **kwargs):
        # validate coordinates, if they fit in dimensions of map
        if not 0 <= self.x_position <= self.game_map.x_dim:
            raise ValidationError("x-coordinates out of bound")
        if not 0 <= self.y_position <= self.game_map.y_dim:
            raise ValidationError("y-coordinates out of bound")

        super().save(*args, **kwargs)


class Edge(models.Model):
    class Meta:
        unique_together = ("start_node", "end_node")

    game_map = models.ForeignKey(GameMap, on_delete=models.CASCADE)
    name = models.CharField(max_length=20, blank=True, null=True)
    start_node = models.ForeignKey(Node, on_delete=models.CASCADE)
    end_node = models.ForeignKey(Node, on_delete=models.CASCADE)
    bike_speed = models.PositiveSmallIntegerField(default=15)  # 0 if blocked for bikes
    walk_speed = models.PositiveSmallIntegerField(
        default=4
    )  # 0 if blocked for pedestrians
    max_lanes = models.PositiveSmallIntegerField(default=2)

    def euclidean_2d_distance(self):
        dx = self.end_node.x_position - self.start_node.x_position
        dy = self.end_node.y_position - self.start_node.y_position
        return math.sqrt((dx * dx) + (dy * dy))


class StreetEdge(models.Model):
    edge = models.ForeignKey(Edge, on_delete=models.CASCADE)
    speed_limit = models.PositiveSmallIntegerField(default=50)
    lanes = models.PositiveSmallIntegerField(default=1)
    dedicated_bus_lane = models.BooleanField(default=False)


class BusLine(models.Model):
    game_map = models.ForeignKey(GameMap, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)
    frequency = models.FloatField()  # frequency per hour or intervall in minutes?
    bus_capacity = models.PositiveSmallIntegerField()
    edges = models.ManyToManyField(StreetEdge)


class TrainEdge(models.Model):
    edge = models.ForeignKey(Edge, on_delete=models.CASCADE)


class TrainLine(models.Model):
    game_map = models.ForeignKey(GameMap, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)
    frequency = models.FloatField()  # frequency per hour or intervall in minutes?
    train_capacity = models.PositiveIntegerField()
    edges = models.ManyToManyField(TrainEdge)


# # help text zu lang. bitte kuerzen. limit in km/h sollte reichen. es heist ja train speed. vielleicht nennst du es einfach train_speed_limit dann kann der hilfetext nur die einheit sein.
# # wegen daten: ueberleg mal, ob nicht integer reicht. macht es auch im frontend einfacher. oder decimal field mit 1 oder 2 nachkommastellen
# # default values erganzen oder null=true, blank=true setzen
# # speed limits und ahnliche attribute koennen ja pro edge gesetzt werden. warum hier doppelt. default values in edges vielleicht sinniger.


# class GameMap(models.Model):
#     map_name = models.CharField(max_length=100)
#     map_file = models.FileField(upload_to="maps/")
#     description = models.TextField()
#     x_dim = models.PositiveIntegerField()
#     y_dim = models.PositiveIntegerField()
#     scale = models.FloatField(
#         help_text="Distance between grid center points in km"
#     )  # scale in km
#     train_speed = models.FloatField(help_text="Default train speed limit in km/h")
#     bike_speed = models.FloatField(help_text="Default bike speed in km/h")
#     pedestrian_speed = models.FloatField(help_text="Default pedestrian speed in km/h")
#     max_street_lanes = models.PositiveIntegerField(
#         help_text="Maximum number of street lanes including bus lane"
#     )
#     max_bus_capacity = models.PositiveIntegerField(
#         help_text="Maximum capacity of a bus line"
#     )
#     max_train_capacity = models.PositiveIntegerField(
#         help_text="Maximum capacity of a train line"
#     )
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"Map: {self.map_name} with xy-dimensions: ({self.x_dim}x{self.y_dim} at {self.scale} km scale)"

#     def load_map_file(self):
#         # method to load and parse the map file if needed
#         pass


# class PTLine(models.Model):
#     game_map = models.ForeignKey(
#         GameMap, on_delete=models.CASCADE, related_name="related_map"
#     )
#     frequency = models.PositiveIntegerField(
#         help_text="Frequency of the line in minutes"
#     )
#     line_number = models.PositiveIntegerField()
#     capacity = models.PositiveIntegerField(help_text="Maximum capacity of the line")

#     def __str__(self):
#         return f"PT Line: {self.line_number} of type on map {self.game_map}"

#     class Meta:
#         abstract = True


# class BusLine(PTLine):
#     def save(self, *args, **kwargs):
#         if self.capacity > self.game_map.max_bus_capacity:
#             raise ValidationError(
#                 f"Bus line capacity {self.capacity} exceeds maximum bus capacity {self.game_map.max_bus_capacity} for map {self.game_map}."
#             )
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"Bus Line: {self.line_number} on map {self.game_map}"


# class TrainLine(PTLine):
#     def save(self, *args, **kwargs):
#         if self.capacity > self.game_map.max_train_capacity:
#             raise ValidationError(
#                 f"Train line capacity {self.capacity} exceeds maximum train capacity {self.game_map.max_train_capacity} for map {self.game_map}."
#             )
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"Train Line: {self.line_number} on map {self.game_map}"


# class Node(models.Model):
#     game_map = models.ForeignKey(
#         GameMap, on_delete=models.CASCADE, related_name="related_map"
#     )
#     node_id = models.PositiveIntegerField()
#     x_coord = models.FloatField()
#     y_coord = models.FloatField()
#     nodetype_choices = [
#         ("H", "Household"),
#         ("W", "Workplace"),
#         ("TS", "Train Station"),
#         ("I", "Intersection"),
#         ("BS", "Bus Stop"),
#     ]
#     nodetype = models.CharField(max_length=2, choices=nodetype_choices)
#     node_name = models.CharField(
#         max_length=100, null=True, blank=True
#     )  # optional for map visualization

#     # methods for node
#     def clean(self):
#         if self.x_coord < 0 or self.x_coord > self.game_map.x_dim:
#             raise ValidationError(
#                 f"x_coord {self.x_coord} is out of bounds for map dimension {self.game_map.x_dim}"
#             )
#         if self.y_coord < 0 or self.y_coord > self.game_map.y_dim:
#             raise ValidationError(
#                 f"y_coord {self.y_coord} is out of bounds for map dimension {self.game_map.y_dim}"
#             )

#         # Ensure node_id is unique per game_map
#         if self.game_map is not None and self.node_id is not None:
#             qs = Node.objects.filter(game_map=self.game_map, node_id=self.node_id)
#             if self.pk:
#                 qs = qs.exclude(pk=self.pk)
#             if qs.exists():
#                 raise ValidationError(
#                     f"node_id {self.node_id} already exists for map {self.game_map}."
#                 )

#     def save(self, *args, **kwargs):
#         self.full_clean()  # call clean and validate the model fields
#         super().save(*args, **kwargs)

#     def __str__(self):
#         # zu lang. bitte kuerzen
#         return f"Node {self.pk} belonging to {self.game_map}. Node is of type {self.nodetype} located at ({self.x_coord}, {self.y_coord})."

#     class Meta:
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["game_map", "node_id"], name="unique_nodeid_per_map"
#             )
#         ]


# class Edge(models.Model):
#     game_map = models.ForeignKey(
#         GameMap, on_delete=models.CASCADE, related_name="related_map"
#     )
#     edge_id = models.PositiveIntegerField(verbose_name="Edge id for referencing")
#     node1 = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="from_node")
#     node2 = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="to_node")
#     edgetype_choices = [
#         ("S", "Street"),
#         ("BK", "Bike Path"),
#         ("T", "Train Track"),
#         ("PW", "Pedestrian Walkway"),
#     ]
#     edgetype = models.CharField(max_length=2, choices=edgetype_choices)
#     distance = models.FloatField(help_text="Distance of the edge in km", editable=False)
#     edge_name = models.CharField(
#         max_length=100, null=True, blank=True
#     )  # optional for map visualization

#     def clean(self):
#         if self.node1.game_map != self.game_map or self.node2.game_map != self.game_map:
#             raise ValidationError(
#                 "Start and end nodes must belong to the same game map as the edge."
#             )

#         # Ensure edge id is unique per game_map
#         if self.game_map is not None and self.edge_id is not None:
#             qs = Node.objects.filter(game_map=self.game_map, edge_id=self.edge_id)
#             if self.pk:
#                 qs = qs.exclude(pk=self.pk)
#             if qs.exists():
#                 raise ValidationError(
#                     f"edge_id {self.edge_id} already exists for map {self.game_map}."
#                 )

#     def save(self, *args, **kwargs):
#         # prevent creating plain edge without subtype
#         if self.__class__ == Edge:
#             raise ValidationError(
#                 "Cannot create an Edge instance directly. Please use a specific Edge subtype."
#             )

#         self.full_clean()  # call clean and validate the model fields

#         # calculate distance based on node coordinates and map scale
#         dx = self.node1.x_coord - self.node2.x_coord  # was is to_node? meinst du node2?
#         dy = self.node1.y_coord - self.node2.y_coord  # was is to_node? meinst du node2?
#         self.distance = (dx * dx + dy * dy) ** 0.5 * self.game_map.scale

#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"Edge belonging to {self.game_map}. Edge is of type {self.edgetype_choices} running from {self.node1} to {self.node2}"  # was is to_node? meinst du node2?

#     class Meta:
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["game_map", "edge_id"], name="unique_edgeid_per_map"
#             )
#         ]


# class StreetEdge(Edge):
#     speed_limit = models.FloatField(help_text="Speed limit in km/h")
#     number_of_lanes = models.PositiveIntegerField(
#         help_text="Number of lanes (including bus lane)"
#     )
#     bus_lane = models.BooleanField(
#         default=False, help_text="Indicates if there is a bus lane"
#     )
#     bus_lines = models.ManyToManyField(BusLine, blank=True)

#     def __str__(self):
#         return f"Street Edge from {self.node1} to {self.node2} with speed limit {self.speed_limit} km/h"


# class BikePathEdge(Edge):
#     def __str__(self):
#         return f"Bike Path Edge from {self.node1} to {self.node2}"


# class TrainTrackEdge(Edge):
#     train_lines = models.ManyToManyField(TrainLine, blank=True)

#     def __str__(self):
#         return f"Train Track Edge from {self.node1} to {self.node2} with  tracks"  # number of tracks fehlt im model


# class PedestrianWalkwayEdge(Edge):
#     def __str__(self):
#         return f"Pedestrian Walkway Edge from {self.node1} to {self.node2}"
