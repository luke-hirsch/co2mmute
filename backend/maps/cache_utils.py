"""Cache utilities for maps app."""

from django.core.cache import cache


def get_graph_cache_key(map_pk: int, version_pk: int) -> str:
    """Generate cache key for a map version graph."""
    return f"map_graph:{map_pk}:{version_pk}"


def invalidate_map_version_graphs(map_pk: int) -> None:
    """
    Invalidate all cached graphs for a specific map.

    This should be called when nodes, edges, or other map data is modified.

    Args:
        map_pk: The GameMap primary key
    """
    # Get all cached keys pattern and delete those matching our map
    # Since we can't easily pattern-match in all cache backends,
    # we'll use a tracking approach with a set of version keys
    versions_key = f"map_versions:{map_pk}"
    cached_versions = cache.get(versions_key, set())

    # Clear all graph caches for this map's versions
    for version_pk in cached_versions:
        cache_key = get_graph_cache_key(map_pk, version_pk)
        cache.delete(cache_key)

    # Clear the versions tracker
    cache.delete(versions_key)


def track_cached_version(map_pk: int, version_pk: int) -> None:
    """
    Track a cached graph so we can invalidate it later.

    Args:
        map_pk: The GameMap primary key
        version_pk: The MapVersion primary key
    """
    versions_key = f"map_versions:{map_pk}"
    cached_versions = cache.get(versions_key, set())
    cached_versions.add(version_pk)
    cache.set(versions_key, cached_versions, timeout=None)  # Keep indefinitely
