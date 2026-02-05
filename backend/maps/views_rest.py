import logging

from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
    GenericAPIView,
)
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache

from maps.models import (
    GameMap,
    MapVersion,
    Node,
    Edge,
    NodeType,
    StreetEdge,
    BusLine,
    TrainEdge,
    TrainLine,
)
from maps.serializer import (
    GameMapSerializer,
    MapVersionSerializer,
    NodeSerializer,
    EdgeSerializer,
    NodeTypeSerializer,
    StreetEdgeSerializer,
    BusLineSerializer,
    TrainEdgeSerializer,
    TrainLineSerializer,
    serialize_bus_line_for_graph,
    serialize_train_line_for_graph,
)
from maps.mixins import MapScopedQuerysetMixin
from maps.permissions import IsStaffOrReadOnly

logger = logging.getLogger(__name__)


# GameMap Views
class GameMapListView(ListCreateAPIView):
    """List all game maps or create a new one."""

    queryset = GameMap.objects.all()
    serializer_class = GameMapSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def perform_create(self, serializer):
        """Set the author when creating a new map."""
        serializer.save(author=self.request.user, updated_by=self.request.user)


class GameMapDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific game map."""

    queryset = GameMap.objects.all()
    serializer_class = GameMapSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"

    def perform_update(self, serializer):
        """Set updated_by when updating a map."""
        serializer.save(updated_by=self.request.user)


# MapVersion Views
class MapVersionListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all map versions for a specific map or create a new one."""

    serializer_class = MapVersionSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter map versions by the specific map."""
        map_id = self.get_map_id()
        return MapVersion.objects.filter(game_map_id=map_id)


class MapVersionDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific map version."""

    queryset = MapVersion.objects.all()
    serializer_class = MapVersionSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "version_pk"


# NodeType Views
class NodeTypeListView(ListCreateAPIView):
    """List all node types or create a new one."""

    queryset = NodeType.objects.all()
    serializer_class = NodeTypeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)


class NodeTypeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific node type."""

    queryset = NodeType.objects.all()
    serializer_class = NodeTypeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "nodetype_pk"


# Node Views
class NodeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all nodes for a specific map or create a new one."""

    serializer_class = NodeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter nodes by the specific map."""
        map_id = self.get_map_id()
        return Node.objects.filter(game_map_id=map_id)


class NodeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific node."""

    queryset = Node.objects.all()
    serializer_class = NodeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "node_pk"


# Edge Views
class EdgeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all edges for a specific map or create a new one."""

    serializer_class = EdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter edges by the specific map."""
        map_id = self.get_map_id()
        return Edge.objects.filter(game_map_id=map_id)


class EdgeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific edge."""

    queryset = Edge.objects.all()
    serializer_class = EdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "edge_pk"


# StreetEdge Views
class StreetEdgeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all street edges for a specific map or create a new one."""

    serializer_class = StreetEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter street edges by the specific map."""
        map_id = self.get_map_id()
        return StreetEdge.objects.filter(edge__game_map_id=map_id).select_related(
            "edge"
        )


class StreetEdgeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific street edge."""

    queryset = StreetEdge.objects.all()
    serializer_class = StreetEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "streetedge_pk"


# BusLine Views
class BusLineListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all bus lines for a specific map or create a new one."""

    serializer_class = BusLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter bus lines by the specific map."""
        map_id = self.get_map_id()
        return BusLine.objects.filter(game_map_id=map_id)


class BusLineDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific bus line."""

    queryset = BusLine.objects.all()
    serializer_class = BusLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "busline_pk"


# TrainEdge Views
class TrainEdgeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all train edges for a specific map or create a new one."""

    serializer_class = TrainEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter train edges by the specific map."""
        map_id = self.get_map_id()
        return TrainEdge.objects.filter(edge__game_map_id=map_id).select_related("edge")


class TrainEdgeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific train edge."""

    queryset = TrainEdge.objects.all()
    serializer_class = TrainEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "trainedge_pk"


# TrainLine Views
class TrainLineListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all train lines for a specific map or create a new one."""

    serializer_class = TrainLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get_queryset(self):
        """Filter train lines by the specific map."""
        map_id = self.get_map_id()
        return TrainLine.objects.filter(game_map_id=map_id)


class TrainLineDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific train line."""

    queryset = TrainLine.objects.all()
    serializer_class = TrainLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "trainline_pk"


# Custom Graph View
class MapVersionGraphView(MapScopedQuerysetMixin, GenericAPIView):
    serializer_class = MapVersionSerializer
    authentication_classes = (SessionAuthentication,)

    def get(self, request, *args, **kwargs):
        map_pk = self.get_map_id()
        version_pk = kwargs.get("version_pk")

        try:
            map_obj = GameMap.objects.get(pk=map_pk)

        except GameMap.DoesNotExist:
            logger.error("map not found")
            return Response(
                {"error": "Map not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Build cache key
        cache_key = f"map_graph:{map_pk}:{version_pk}"

        # Try to get from cache first
        cached_graph = cache.get(cache_key)
        if cached_graph:
            return Response(cached_graph, status=status.HTTP_200_OK)

        # Get or determine version
        if not version_pk:
            version = MapVersion.objects.filter(game_map=map_obj).first()
            if not version:
                return Response(
                    {"error": "No map version found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            try:
                version = MapVersion.objects.get(pk=version_pk, game_map=map_obj)
            except MapVersion.DoesNotExist:
                logger.error(f"version {version_pk} not found for map {map_pk}")
                return Response(
                    {"error": "Map version not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            # Get all nodes for this map version
            nodes = Node.objects.filter(
                game_map=map_obj, map_versions=version
            ).prefetch_related("node_type")

            # Get all edges for this map version with street_edge and train_edge prefetch
            # StreetEdge and TrainEdge have ForeignKey to Edge, so we use prefetch_related
            edges = (
                Edge.objects.filter(game_map=map_obj, map_versions=version)
                .select_related("start_node", "end_node", "game_map")
                .prefetch_related("streetedge_set", "trainedge_set")
            )

            # Get PT lines for this map version
            bus_lines = BusLine.objects.filter(
                game_map=map_obj, map_versions=version
            ).prefetch_related("edges", "edges__edge")
            train_lines = TrainLine.objects.filter(
                game_map=map_obj, map_versions=version
            ).prefetch_related("edges", "edges__edge")

            # Serialize the data
            nodes_data = NodeSerializer(nodes, many=True).data
            edges_data = EdgeSerializer(edges, many=True).data

            # Serialize PT lines for graph/routing
            bus_lines_data = [
                serialize_bus_line_for_graph(bl, version) for bl in bus_lines
            ]
            train_lines_data = [
                serialize_train_line_for_graph(tl, version) for tl in train_lines
            ]

            graph_data = {
                "map_id": map_pk,
                "version_id": version_pk or version.pk,
                "version_name": version.name,
                "version_description": version.description,
                "nodes": nodes_data,
                "edges": edges_data,
                "node_count": len(nodes_data),
                "edge_count": len(edges_data),
                "bus_lines": bus_lines_data,
                "train_lines": train_lines_data,
                "scale": map_obj.scale,
            }

            # Cache the result for 1 hour (3600 seconds)
            cache.set(cache_key, graph_data, 3600)

            return Response(graph_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(
                f"Error building graph for map {map_pk} version {version_pk}:{str(e)}"
            )
            return Response(
                {"error": "Error building graph"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
