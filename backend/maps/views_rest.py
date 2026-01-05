from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication

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
)
from maps.mixins import MapScopedQuerysetMixin


# GameMap Views
class GameMapListView(ListCreateAPIView):
    """List all game maps or create a new one."""

    queryset = GameMap.objects.all()
    serializer_class = GameMapSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def perform_create(self, serializer):
        """Set the author when creating a new map."""
        serializer.save(author=self.request.user, updated_by=self.request.user)


class GameMapDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific game map."""

    queryset = GameMap.objects.all()
    serializer_class = GameMapSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    lookup_field = "pk"

    def perform_update(self, serializer):
        """Set updated_by when updating a map."""
        serializer.save(updated_by=self.request.user)


# MapVersion Views
class MapVersionListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all map versions for a specific map or create a new one."""

    serializer_class = MapVersionSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Filter map versions by the specific map."""
        map_id = self.get_map_id()
        return MapVersion.objects.filter(game_map_id=map_id)


class MapVersionDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific map version."""

    queryset = MapVersion.objects.all()
    serializer_class = MapVersionSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    lookup_field = "pk"
    lookup_url_kwarg = "version_pk"


# NodeType Views
class NodeTypeListView(ListCreateAPIView):
    """List all node types or create a new one."""

    queryset = NodeType.objects.all()
    serializer_class = NodeTypeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)


class NodeTypeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific node type."""

    queryset = NodeType.objects.all()
    serializer_class = NodeTypeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    lookup_field = "pk"
    lookup_url_kwarg = "nodetype_pk"


# Node Views
class NodeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all nodes for a specific map or create a new one."""

    serializer_class = NodeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Filter nodes by the specific map."""
        map_id = self.get_map_id()
        return Node.objects.filter(game_map_id=map_id)


class NodeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific node."""

    queryset = Node.objects.all()
    serializer_class = NodeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    lookup_field = "pk"
    lookup_url_kwarg = "node_pk"


# Edge Views
class EdgeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all edges for a specific map or create a new one."""

    serializer_class = EdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Filter edges by the specific map."""
        map_id = self.get_map_id()
        return Edge.objects.filter(game_map_id=map_id)


class EdgeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific edge."""

    queryset = Edge.objects.all()
    serializer_class = EdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    lookup_field = "pk"
    lookup_url_kwarg = "edge_pk"


# StreetEdge Views
class StreetEdgeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all street edges for a specific map or create a new one."""

    serializer_class = StreetEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

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
    permission_classes = (IsAuthenticated,)
    lookup_field = "pk"
    lookup_url_kwarg = "streetedge_pk"


# BusLine Views
class BusLineListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all bus lines for a specific map or create a new one."""

    serializer_class = BusLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Filter bus lines by the specific map."""
        map_id = self.get_map_id()
        return BusLine.objects.filter(game_map_id=map_id)


class BusLineDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific bus line."""

    queryset = BusLine.objects.all()
    serializer_class = BusLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    lookup_field = "pk"
    lookup_url_kwarg = "busline_pk"


# TrainEdge Views
class TrainEdgeListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all train edges for a specific map or create a new one."""

    serializer_class = TrainEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Filter train edges by the specific map."""
        map_id = self.get_map_id()
        return TrainEdge.objects.filter(edge__game_map_id=map_id).select_related("edge")


class TrainEdgeDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific train edge."""

    queryset = TrainEdge.objects.all()
    serializer_class = TrainEdgeSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    lookup_field = "pk"
    lookup_url_kwarg = "trainedge_pk"


# TrainLine Views
class TrainLineListView(MapScopedQuerysetMixin, ListCreateAPIView):
    """List all train lines for a specific map or create a new one."""

    serializer_class = TrainLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Filter train lines by the specific map."""
        map_id = self.get_map_id()
        return TrainLine.objects.filter(game_map_id=map_id)


class TrainLineDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific train line."""

    queryset = TrainLine.objects.all()
    serializer_class = TrainLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    lookup_field = "pk"
    lookup_url_kwarg = "trainline_pk"
