from rest_framework.exceptions import ValidationError
from maps.models import GameMap
from typing import Any, Mapping


class MapScopedQuerysetMixin:
    """
    Mixin to automatically scope querysets to a specific game map via URL parameter.

    This mixin filters all querysets by the `map_id` URL parameter, ensuring
    that only objects belonging to the specified map are returned.

    Subclasses should define their own `get_queryset()` method that calls
    this mixin's logic before returning.

    Usage:
        class NodeListView(MapScopedQuerysetMixin, ListCreateAPIView):
            # In get_queryset():
            queryset = Node.objects.filter(game_map_id=self.get_map_id())
    """

    kwargs: Mapping[str, Any]

    def get_map_id(self) -> int:
        """
        Extract and validate the map_id (pk) from URL kwargs.

        Returns:
            The map pk as an integer

        Raises:
            ValidationError: If map pk is missing or the map doesn't exist
        """
        map_pk = self.kwargs.get("pk")
        if not map_pk:
            raise ValidationError("map pk is required")

        # Verify the map exists
        try:
            GameMap.objects.get(pk=map_pk)
        except GameMap.DoesNotExist:
            raise ValidationError(f"GameMap with pk {map_pk} does not exist")

        return map_pk
