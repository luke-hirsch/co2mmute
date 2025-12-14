from django.contrib import admin

from .models import (
    BusLine,
    Edge,
    GameMap,
    Node,
    NodeType,
    StreetEdge,
    TrainEdge,
    TrainLine,
)


@admin.register(GameMap)
class GameMapAdmin(admin.ModelAdmin):
    list_display = ("name", "x_dim", "y_dim", "scale", "author", "created")
    search_fields = ("name", "author__username", "author__email")
    list_filter = ("created", "author")
    ordering = ("name",)


@admin.register(NodeType)
class NodeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "short")
    search_fields = ("name", "short")
    ordering = ("name",)


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ("name", "game_map", "x_position", "y_position")
    search_fields = ("name", "game_map__name")
    list_filter = ("game_map",)
    ordering = ("game_map", "name")


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    list_display = ("name", "game_map", "start_node", "end_node")
    search_fields = ("name", "game_map__name", "start_node__name", "end_node__name")
    list_filter = ("game_map",)
    ordering = ("game_map", "name")


@admin.register(StreetEdge)
class StreetEdgeAdmin(admin.ModelAdmin):
    list_display = ("edge", "speed_limit", "lanes", "dedicated_bus_lane")
    search_fields = (
        "edge__name",
        "edge__game_map__name",
    )
    list_filter = ("dedicated_bus_lane",)
    ordering = ("edge__game_map__name", "edge__name")


@admin.register(TrainEdge)
class TrainEdgeAdmin(admin.ModelAdmin):
    list_display = ("edge",)
    search_fields = ("edge__name", "edge__game_map__name")
    ordering = ("edge__game_map__name", "edge__name")


@admin.register(BusLine)
class BusLineAdmin(admin.ModelAdmin):
    list_display = ("name", "game_map", "intervall", "bus_capacity")
    search_fields = ("name", "game_map__name")
    list_filter = ("game_map",)
    ordering = ("game_map", "name")


@admin.register(TrainLine)
class TrainLineAdmin(admin.ModelAdmin):
    list_display = ("name", "game_map", "intervall", "train_capacity")
    search_fields = ("name", "game_map__name")
    list_filter = ("game_map",)
    ordering = ("game_map", "name")
