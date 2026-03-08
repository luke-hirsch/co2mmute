from itertools import combinations

from django.contrib import admin
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


@admin.register(GameMap)
class GameMapAdmin(admin.ModelAdmin):
    list_display = ("name", "x_dim", "y_dim", "scale", "author", "created")
    search_fields = ("name", "author__username", "author__email")
    list_filter = ("created", "author")
    ordering = ("name",)


def _generate_combination_versions(modeladmin, request, queryset):
    """
    Auto-generate combination MapVersions for the selected atomic (non-base) versions.

    For N selected versions (A, B, C, …) this creates all 2-element and larger
    subsets (AB, AC, BC, ABC, …), wires up their compatible_versions to form
    the correct lattice, and copies node/edge map_versions memberships.
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

    game_map = atomic_versions[0].game_map
    base_version = MapVersion.objects.filter(
        game_map=game_map, base_version=True
    ).first()

    with transaction.atomic():
        # Build a dict: frozenset(version_ids) → MapVersion for all existing + new versions
        existing: dict[frozenset, MapVersion] = {}
        for v in atomic_versions:
            existing[frozenset([v.pk])] = v

        # All combination subsets of size >= 2
        n = len(atomic_versions)
        all_subsets: list[frozenset] = []
        for size in range(2, n + 1):
            for combo in combinations(atomic_versions, size):
                all_subsets.append(frozenset(v.pk for v in combo))

        # Create combination MapVersion objects
        created_count = 0
        for subset in all_subsets:
            if subset in existing:
                continue
            members = [v for v in atomic_versions if v.pk in subset]
            members.sort(key=lambda v: v.name)
            combo_name = " + ".join(v.name for v in members)
            combo_poll_text = "Apply changes: " + ", ".join(v.name for v in members)
            combo_version = MapVersion.objects.create(
                game_map=game_map,
                name=combo_name,
                poll_text=combo_poll_text,
                revert_poll_text=f"Revert changes: {combo_name}",
                base_version=False,
            )
            existing[subset] = combo_version
            created_count += 1

            # Copy map_versions memberships: include any element whose version
            # belongs to any member of this subset
            member_versions = [existing[frozenset([pk])] for pk in subset]
            for node in Node.objects.filter(
                map_versions__in=member_versions
            ).distinct():
                node.map_versions.add(combo_version)
            for edge in Edge.objects.filter(
                map_versions__in=member_versions
            ).distinct():
                edge.map_versions.add(combo_version)
            for street_edge in StreetEdge.objects.filter(
                map_versions__in=member_versions
            ).distinct():
                street_edge.map_versions.add(combo_version)
            for train_edge in TrainEdge.objects.filter(
                map_versions__in=member_versions
            ).distinct():
                train_edge.map_versions.add(combo_version)
            for bus_line in BusLine.objects.filter(
                map_versions__in=member_versions
            ).distinct():
                bus_line.map_versions.add(combo_version)

        # Set compatible_versions for all versions in the lattice
        # A version with subset S is compatible with:
        #   - All subsets of size |S|+1 that are supersets of S (forward moves)
        #   - All subsets of size |S|-1 that are subsets of S (rollback moves)
        #   - For size-1 subsets (atomic), also the base version (ultimate rollback)
        all_entries = {**existing}  # frozenset(pks) → MapVersion

        for subset, version in all_entries.items():
            neighbours: list[MapVersion] = []
            size = len(subset)

            # Forward: supersets of size+1
            for other_subset, other_version in all_entries.items():
                if len(other_subset) == size + 1 and subset.issubset(other_subset):
                    neighbours.append(other_version)

            # Backward: subsets of size-1
            for other_subset, other_version in all_entries.items():
                if len(other_subset) == size - 1 and other_subset.issubset(subset):
                    neighbours.append(other_version)

            # Atomic versions can roll back to base
            if size == 1 and base_version:
                neighbours.append(base_version)

            version.compatible_versions.set(neighbours)

        # Also update the base version's compatible_versions to include atomic versions
        if base_version:
            existing_base_compat = list(base_version.compatible_versions.all())
            new_atomics = [v for v in atomic_versions if v not in existing_base_compat]
            if new_atomics:
                base_version.compatible_versions.add(*new_atomics)

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
