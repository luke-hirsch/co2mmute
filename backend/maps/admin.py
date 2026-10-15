from django.contrib import admin, messages
from django.db import transaction

from .models import (
    BusLine,
    Edge,
    GameMap,
    MapVersion,
    Node,
    NodeType,
    StreetEdge,
    TrainEdge,
    TrainLine,
)
from .versions import (
    MapDeleteRefused,
    VersionDeleteRefused,
    delete_map,
    delete_version,
    deletion_preview,
    describe_goes,
    generate_combinations,
    map_deletion_refusal,
)


@admin.register(GameMap)
class GameMapAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "calibrated",
        "timetable_factor",
        "x_dim",
        "y_dim",
        "scale",
        "author",
        "created",
    )
    search_fields = ("name", "author__username", "author__email")
    list_filter = ("created", "author")
    ordering = ("name",)

    # Deleting goes through `maps.versions.delete_map`, like the map page's
    # delete: a map a game was on stays, both from its delete page and from the
    # list's "delete selected".

    def get_deleted_objects(self, objs, request):
        """A refusal is "protected", so Django deletes nothing."""
        deleted, counts, perms_needed, protected = super().get_deleted_objects(
            objs, request
        )
        protected = list(protected)
        for game_map in objs:
            refusal = map_deletion_refusal(game_map)
            if refusal is not None:
                protected.append(f"{game_map.name}: {refusal.detail}")
        return deleted, counts, perms_needed, protected

    def delete_model(self, request, obj):
        self._delete(request, [obj])

    def delete_queryset(self, request, queryset):
        self._delete(request, queryset)

    def _delete(self, request, game_maps):
        for game_map in game_maps:
            try:
                delete_map(game_map)
            except MapDeleteRefused as refusal:
                # Refused between the confirmation page and the click.
                self.message_user(
                    request, f"{game_map.name}: {refusal.detail}", messages.ERROR
                )


def _generate_combination_versions(modeladmin, request, queryset):
    """The editor's combinations (`maps.versions.generate_combinations`) for the
    selected changes: every combination of two or more, wired into the ballot.
    """
    atomic_versions = list(queryset)

    # Validate: all on the same map, none are base versions
    game_maps = {v.game_map_id for v in atomic_versions}
    if len(game_maps) != 1:
        modeladmin.message_user(
            request, "All selected versions must belong to the same map.", level="error"
        )
        return
    if any(v.base_version for v in atomic_versions):
        modeladmin.message_user(
            request, "Do not include base versions in the selection.", level="error"
        )
        return
    if len(atomic_versions) < 2:
        modeladmin.message_user(
            request, "Select at least 2 atomic versions.", level="error"
        )
        return

    with transaction.atomic():
        created_count = generate_combinations(
            atomic_versions[0].game_map, atomic_versions
        )

    modeladmin.message_user(
        request,
        f"Created {created_count} combination version(s) and updated compatible_versions for all.",
    )


_generate_combination_versions.short_description = (
    "Generate combination versions from selected atomics"
)


@admin.register(MapVersion)
class MapVersionAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = (
        "game_map__name",
        "name",
        "game_map__author__username",
        "game_map__author__email",
    )
    list_filter = ("created", "game_map")
    actions = [_generate_combination_versions]

    ordering = ("name",)

    # Deleting goes through `maps.versions.delete_version`, the editor's
    # cleanup. The admin's own delete removed the bare row and left every
    # node, edge and line that was only in it in no version — that is where the
    # stray rows in the box's 2026-10-02 export came from. Both doors: the
    # delete page and the list's "delete selected", which share these hooks.

    def get_deleted_objects(self, objs, request):
        """Name what goes; a refusal is "protected", so Django deletes nothing."""
        deleted, counts, perms_needed, protected = super().get_deleted_objects(
            objs, request
        )
        protected = list(protected)
        for version in objs:
            preview = deletion_preview(version)
            if preview["refusal"]:
                protected.append(f"{version.name}: {preview['refusal']['detail']}")
            else:
                deleted.append(f"{version.name}: {describe_goes(preview['goes'])}")
        return deleted, counts, perms_needed, protected

    def delete_model(self, request, obj):
        self._delete(request, [obj])

    def delete_queryset(self, request, queryset):
        self._delete(request, queryset)

    def _delete(self, request, versions):
        for version in versions:
            try:
                delete_version(version)
            except VersionDeleteRefused as refusal:
                # Refused between the confirmation page and the click.
                self.message_user(
                    request, f"{version.name}: {refusal.detail}", messages.ERROR
                )


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
    list_display = ("edge", "speed_limit", "lanes", "dedicated_bus_lane", "tram_track")
    search_fields = (
        "edge__name",
        "edge__game_map__name",
    )
    list_filter = ("dedicated_bus_lane", "tram_track")
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
    list_display = ("name", "game_map", "kind", "intervall", "train_capacity")
    search_fields = ("name", "game_map__name")
    list_filter = ("game_map", "kind")
    ordering = ("game_map", "name")
