"""Signals for maps app."""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache

from maps.models import Node, Edge, MapVersion


def invalidate_map_version_graphs(map_pk: int) -> None:
    """
    Invalidate all cached graphs for a specific map.

    This should be called when nodes, edges, or other map data is modified.

    Args:
        map_pk: The GameMap primary key
    """
    # Get all versions for this map and clear their caches
    versions = MapVersion.objects.filter(game_map_id=map_pk)

    for version in versions:
        cache_key = f"map_graph:{map_pk}:{version.pk}"
        cache.delete(cache_key)
    cache.delete(f"map_graph:{map_pk}:None")


@receiver(pre_save, sender=MapVersion)
def ensure_single_base_version(sender, instance, **kwargs):
    """
    Ensure only one base version per map.

    If setting this version as base, unset all other base versions for this map.
    If unsetting the only base version, force this one to stay as base.
    """
    if instance.pk:  # Only on update, not on create
        # Get current state from database
        try:
            current = MapVersion.objects.get(pk=instance.pk)
            was_base = current.base_version
        except MapVersion.DoesNotExist:
            was_base = False
    else:
        was_base = False

    # Case 1: Setting this version as base when one already exists
    if instance.base_version:
        # Unset all other base versions for this map using bulk_update
        # This is more efficient than individual saves
        other_bases = MapVersion.objects.filter(
            game_map=instance.game_map, base_version=True
        )
        if instance.pk:
            other_bases = other_bases.exclude(pk=instance.pk)

        if other_bases.exists():
            other_bases.update(base_version=False)

    # Case 2: Trying to unset base when it's the only base version
    elif not instance.base_version and was_base:
        other_bases = MapVersion.objects.filter(
            game_map=instance.game_map, base_version=True
        ).exclude(pk=instance.pk)

        if not other_bases.exists():
            # This is the only base version, force it to stay as base
            instance.base_version = True


@receiver(post_delete, sender=MapVersion)
def ensure_base_version_on_delete(sender, instance, **kwargs):
    """If deleted version was base, make another one base."""
    if instance.base_version:
        remaining = MapVersion.objects.filter(game_map=instance.game_map).first()

        if remaining:
            remaining.base_version = True
            remaining.save()


@receiver(post_save, sender=Node)
def clear_cache_on_node_save(sender, instance, **kwargs):
    """Clear graph cache when a node is saved."""
    invalidate_map_version_graphs(instance.game_map_id)


@receiver(post_delete, sender=Node)
def clear_cache_on_node_delete(sender, instance, **kwargs):
    """Clear graph cache when a node is deleted."""
    invalidate_map_version_graphs(instance.game_map_id)


@receiver(post_save, sender=Edge)
def clear_cache_on_edge_save(sender, instance, **kwargs):
    """Clear graph cache when an edge is saved."""
    invalidate_map_version_graphs(instance.game_map_id)


@receiver(post_delete, sender=Edge)
def clear_cache_on_edge_delete(sender, instance, **kwargs):
    """Clear graph cache when an edge is deleted."""
    invalidate_map_version_graphs(instance.game_map_id)
