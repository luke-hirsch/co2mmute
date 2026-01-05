"""Signals for maps app."""

from django.db.models.signals import post_save, post_delete
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
