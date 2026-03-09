import logging

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from maps.mixins import MapScopedQuerysetMixin
from maps.models import (
    BusLine,
    BusLineEdge,
    Edge,
    GameMap,
    MapVersion,
    Node,
    NodeType,
    StreetEdge,
    TrainEdge,
    TrainLine,
    TrainLineEdge,
)
from maps.permissions import IsStaffOrReadOnly
from maps.serializer import (
    BusLineSerializer,
    EdgeSerializer,
    GameMapSerializer,
    MapVersionSerializer,
    NodeSerializer,
    NodeTypeSerializer,
    StreetEdgeSerializer,
    TrainEdgeSerializer,
    TrainLineSerializer,
    VersionDiffInputSerializer,
    serialize_bus_line_for_graph,
    serialize_train_line_for_graph,
)

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
        _invalidate_map_cache(self.kwargs["pk"])


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
    parser_classes = (MultiPartParser, FormParser)
    lookup_field = "pk"
    lookup_url_kwarg = "version_pk"


class GenerateCombinationsView(GenericAPIView):
    """Generate combination MapVersions from a list of atomic version IDs."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    @transaction.atomic
    def post(self, request, pk):
        from itertools import combinations as _combinations

        game_map = get_object_or_404(GameMap, pk=pk)
        version_ids = request.data.get("version_ids", [])
        if len(version_ids) < 2:
            return Response(
                {"error": "Provide at least 2 version IDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        atomic_versions = list(MapVersion.objects.filter(pk__in=version_ids, game_map=game_map))
        if len(atomic_versions) != len(version_ids):
            return Response(
                {"error": "One or more versions not found for this map."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if any(v.base_version for v in atomic_versions):
            return Response(
                {"error": "Do not include base versions."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_version = MapVersion.objects.filter(game_map=game_map, base_version=True).first()

        existing: dict = {}
        for v in atomic_versions:
            existing[frozenset([v.pk])] = v

        n = len(atomic_versions)
        all_subsets = []
        for size in range(2, n + 1):
            for combo in _combinations(atomic_versions, size):
                all_subsets.append(frozenset(v.pk for v in combo))

        created_count = 0
        for subset in all_subsets:
            if subset in existing:
                continue
            members = sorted([v for v in atomic_versions if v.pk in subset], key=lambda v: v.name)
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

            member_versions = [existing[frozenset([p])] for p in subset]
            for node in Node.objects.filter(map_versions__in=member_versions).distinct():
                node.map_versions.add(combo_version)
            for edge in Edge.objects.filter(map_versions__in=member_versions).distinct():
                edge.map_versions.add(combo_version)
            for se in StreetEdge.objects.filter(map_versions__in=member_versions).distinct():
                se.map_versions.add(combo_version)
            for te in TrainEdge.objects.filter(map_versions__in=member_versions).distinct():
                te.map_versions.add(combo_version)
            for bl in BusLine.objects.filter(map_versions__in=member_versions).distinct():
                bl.map_versions.add(combo_version)

        all_entries = {**existing}
        for subset, version in all_entries.items():
            neighbours = []
            size = len(subset)
            for other_subset, other_version in all_entries.items():
                if len(other_subset) == size + 1 and subset.issubset(other_subset):
                    neighbours.append(other_version)
            for other_subset, other_version in all_entries.items():
                if len(other_subset) == size - 1 and other_subset.issubset(subset):
                    neighbours.append(other_version)
            if size == 1 and base_version:
                neighbours.append(base_version)
            version.compatible_versions.set(neighbours)

        if base_version:
            existing_base_compat = list(base_version.compatible_versions.all())
            new_atomics = [v for v in atomic_versions if v not in existing_base_compat]
            if new_atomics:
                base_version.compatible_versions.add(*new_atomics)

        return Response({"created": created_count}, status=status.HTTP_201_CREATED)


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

    @transaction.atomic
    def perform_create(self, serializer):
        """Create edge, and optionally the reverse edge if bidirectional."""
        bidirectional = serializer.validated_data.pop("bidirectional", False)
        edge = serializer.save()

        if bidirectional:
            reverse_edge = Edge.objects.create(
                game_map=edge.game_map,
                name=edge.name,
                start_node=edge.end_node,
                end_node=edge.start_node,
                biking=edge.biking,
                walking=edge.walking,
                max_lanes=edge.max_lanes,
            )
            reverse_edge.map_versions.set(edge.map_versions.all())

        _invalidate_map_cache(self.kwargs["pk"])


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

    def perform_create(self, serializer):
        instance = serializer.save()
        edge_ids = self.request.data.get("edges", [])
        if edge_ids:
            se_by_pk = {se.pk: se for se in StreetEdge.objects.filter(pk__in=edge_ids)}
            BusLineEdge.objects.bulk_create([
                BusLineEdge(bus_line=instance, street_edge=se_by_pk[eid], order=idx)
                for idx, eid in enumerate(edge_ids)
                if eid in se_by_pk
            ])
        _invalidate_map_cache(self.kwargs["pk"])


class BusLineDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific bus line."""

    queryset = BusLine.objects.all()
    serializer_class = BusLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "busline_pk"

    def perform_update(self, serializer):
        serializer.save()
        _invalidate_map_cache(self.kwargs["pk"])

    def perform_destroy(self, instance):
        map_pk = self.kwargs["pk"]
        instance.delete()
        _invalidate_map_cache(map_pk)


class BusLineEdgesView(GenericAPIView):
    """Replace all edges for a bus line."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def put(self, request, pk, busline_pk):
        bus_line = get_object_or_404(BusLine, pk=busline_pk, game_map_id=pk)
        edge_ids = request.data.get("edges", [])
        BusLineEdge.objects.filter(bus_line=bus_line).delete()
        if edge_ids:
            se_by_pk = {se.pk: se for se in StreetEdge.objects.filter(pk__in=edge_ids)}
            BusLineEdge.objects.bulk_create([
                BusLineEdge(bus_line=bus_line, street_edge=se_by_pk[eid], order=idx)
                for idx, eid in enumerate(edge_ids)
                if eid in se_by_pk
            ])
        _invalidate_map_cache(pk)
        return Response(
            BusLineSerializer(bus_line).data,
            status=status.HTTP_200_OK,
        )


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

    def perform_create(self, serializer):
        instance = serializer.save()
        edge_ids = self.request.data.get("edges", [])
        if edge_ids:
            te_by_pk = {te.pk: te for te in TrainEdge.objects.filter(pk__in=edge_ids)}
            TrainLineEdge.objects.bulk_create([
                TrainLineEdge(train_line=instance, train_edge=te_by_pk[eid], order=idx)
                for idx, eid in enumerate(edge_ids)
                if eid in te_by_pk
            ])
        _invalidate_map_cache(self.kwargs["pk"])


class TrainLineDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific train line."""

    queryset = TrainLine.objects.all()
    serializer_class = TrainLineSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    lookup_field = "pk"
    lookup_url_kwarg = "trainline_pk"

    def perform_update(self, serializer):
        serializer.save()
        _invalidate_map_cache(self.kwargs["pk"])

    def perform_destroy(self, instance):
        map_pk = self.kwargs["pk"]
        instance.delete()
        _invalidate_map_cache(map_pk)


class TrainLineEdgesView(GenericAPIView):
    """Replace all edges for a train line."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def put(self, request, pk, trainline_pk):
        train_line = get_object_or_404(TrainLine, pk=trainline_pk, game_map_id=pk)
        edge_ids = request.data.get("edges", [])
        TrainLineEdge.objects.filter(train_line=train_line).delete()
        if edge_ids:
            te_by_pk = {te.pk: te for te in TrainEdge.objects.filter(pk__in=edge_ids)}
            TrainLineEdge.objects.bulk_create([
                TrainLineEdge(train_line=train_line, train_edge=te_by_pk[eid], order=idx)
                for idx, eid in enumerate(edge_ids)
                if eid in te_by_pk
            ])
        _invalidate_map_cache(pk)
        return Response(
            TrainLineSerializer(train_line).data,
            status=status.HTTP_200_OK,
        )


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

            # Get PT lines for this map version (ordered by through table)
            from django.db.models import Prefetch

            bus_lines = BusLine.objects.filter(
                game_map=map_obj, map_versions=version
            ).prefetch_related(
                Prefetch(
                    "edges",
                    queryset=StreetEdge.objects.select_related("edge").order_by(
                        "buslineedge__order"
                    ),
                )
            )
            train_lines = TrainLine.objects.filter(
                game_map=map_obj, map_versions=version
            ).prefetch_related(
                Prefetch(
                    "edges",
                    queryset=TrainEdge.objects.select_related("edge").order_by(
                        "trainlineedge__order"
                    ),
                )
            )

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
                "x_dim": map_obj.x_dim,
                "y_dim": map_obj.y_dim,
                "background_image_url": (
                    request.build_absolute_uri(map_obj.background_image.url)
                    if map_obj.background_image
                    else None
                ),
                "image_offset_x": map_obj.image_offset_x,
                "image_offset_y": map_obj.image_offset_y,
                "image_scale": map_obj.image_scale,
                "image_crop_top": map_obj.image_crop_top,
                "image_crop_right": map_obj.image_crop_right,
                "image_crop_bottom": map_obj.image_crop_bottom,
                "image_crop_left": map_obj.image_crop_left,
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


class MapExportView(MapScopedQuerysetMixin, GenericAPIView):
    """Export a map version as upload-compatible JSON."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    def get(self, request, *args, **kwargs):
        map_pk = self.get_map_id()
        version_pk = kwargs.get("version_pk")

        game_map = get_object_or_404(GameMap, pk=map_pk)

        # Resolve version
        if version_pk:
            version = get_object_or_404(
                MapVersion, pk=version_pk, game_map=game_map
            )
        else:
            version = MapVersion.objects.filter(
                game_map=game_map, base_version=True
            ).first()
            if not version:
                version = MapVersion.objects.filter(game_map=game_map).first()
            if not version:
                return Response(
                    {"error": "No map version found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Gather data
        nodes = Node.objects.filter(
            game_map=game_map, map_versions=version
        ).prefetch_related("node_type")

        edges = (
            Edge.objects.filter(game_map=game_map, map_versions=version)
            .select_related("start_node", "end_node")
            .prefetch_related("streetedge_set", "trainedge_set")
        )

        # Build edge index mapping (edge pk -> index in list)
        edge_list = list(edges)
        edge_pk_to_idx = {e.pk: idx for idx, e in enumerate(edge_list)}

        # Pre-fetch street/train edges for this version
        edge_pks = [e.pk for e in edge_list]
        street_edges_map = {
            se.edge_id: se
            for se in StreetEdge.objects.filter(
                edge_id__in=edge_pks, map_versions=version
            )
        }
        train_edges_map = {
            te.edge_id: te
            for te in TrainEdge.objects.filter(
                edge_id__in=edge_pks, map_versions=version
            )
        }

        # Build node id mapping (node pk -> stable string id)
        node_id_map = {n.pk: str(n.pk) for n in nodes}

        # Serialize nodes
        nodes_data = []
        for node in nodes:
            node_entry = {
                "id": str(node.pk),
                "name": node.name,
                "x": float(node.x_position),
                "y": float(node.y_position),
            }
            types = [nt.name for nt in node.node_type.all()]
            if types:
                node_entry["types"] = types
            nodes_data.append(node_entry)

        # Serialize edges
        edges_data = []
        for edge in edge_list:
            has_street = edge.pk in street_edges_map
            has_train = edge.pk in train_edges_map

            if has_street and has_train:
                edge_type = "both"
            elif has_train:
                edge_type = "train"
            else:
                edge_type = "street"

            edge_entry = {
                "start_node": node_id_map[edge.start_node_id],
                "end_node": node_id_map[edge.end_node_id],
                "name": edge.name,
                "type": edge_type,
                "biking": edge.biking,
                "walking": edge.walking,
                "max_lanes": edge.max_lanes,
            }

            if has_street:
                se = street_edges_map[edge.pk]
                edge_entry["speed_limit"] = se.speed_limit
                edge_entry["lanes"] = se.lanes
                edge_entry["dedicated_bus_lane"] = se.dedicated_bus_lane

            edges_data.append(edge_entry)

        # Serialize bus lines
        bus_lines = BusLine.objects.filter(
            game_map=game_map, map_versions=version
        )
        bus_lines_data = []
        for bl in bus_lines:
            ble_qs = BusLineEdge.objects.filter(bus_line=bl).order_by("order")
            edge_indices = []
            for ble in ble_qs:
                se = ble.street_edge
                idx = edge_pk_to_idx.get(se.edge_id)
                if idx is not None:
                    edge_indices.append(idx)
            bus_lines_data.append({
                "name": bl.name,
                "interval": bl.intervall,
                "capacity": bl.bus_capacity,
                "speed_kmh": bl.bus_speed_kmh,
                "edges": edge_indices,
            })

        # Serialize train lines
        train_lines = TrainLine.objects.filter(
            game_map=game_map, map_versions=version
        )
        train_lines_data = []
        for tl in train_lines:
            tle_qs = TrainLineEdge.objects.filter(train_line=tl).order_by("order")
            edge_indices = []
            for tle in tle_qs:
                te = tle.train_edge
                idx = edge_pk_to_idx.get(te.edge_id)
                if idx is not None:
                    edge_indices.append(idx)
            train_lines_data.append({
                "name": tl.name,
                "interval": tl.intervall,
                "capacity": tl.train_capacity,
                "speed_kmh": tl.train_speed_kmh,
                "edges": edge_indices,
            })

        export_data = {
            "scale": float(game_map.scale),
            "nodes": nodes_data,
            "edges": edges_data,
            "bus_lines": bus_lines_data,
            "train_lines": train_lines_data,
        }

        return Response(export_data, status=status.HTTP_200_OK)


def _invalidate_map_cache(map_pk):
    """Invalidate graph cache for all versions of a map."""
    for version in MapVersion.objects.filter(game_map_id=map_pk):
        cache.delete(f"map_graph:{map_pk}:{version.pk}")
    cache.delete(f"map_graph:{map_pk}:None")


class GameMapImageUploadView(GenericAPIView):
    """Upload a background image for a game map."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, pk):
        game_map = get_object_or_404(GameMap, pk=pk)
        image = request.FILES.get("image")
        if not image:
            return Response(
                {"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST
            )
        game_map.background_image = image
        game_map.updated_by = request.user
        game_map.save()
        _invalidate_map_cache(pk)
        serializer = GameMapSerializer(game_map, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        game_map = get_object_or_404(GameMap, pk=pk)
        if game_map.background_image:
            game_map.background_image.delete(save=False)
            game_map.background_image = None
            game_map.updated_by = request.user
            game_map.save()
        _invalidate_map_cache(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VersionDiffCreateView(GenericAPIView):
    """Create a new map version from a source version + changeset."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsStaffOrReadOnly,)

    @transaction.atomic
    def post(self, request, pk):
        game_map = get_object_or_404(GameMap, pk=pk)
        serializer = VersionDiffInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not isinstance(data, dict):
            return Response(
                {"error": "Cannot create empty version diff."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Get source version
        try:
            source = MapVersion.objects.get(
                pk=data["source_version_id"], game_map=game_map
            )
        except MapVersion.DoesNotExist:
            return Response(
                {"error": "Source version not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Unset other base versions if this will be base
        if data.get("is_base_version"):
            MapVersion.objects.filter(game_map=game_map, base_version=True).update(
                base_version=False
            )

        # 1. Create new MapVersion
        new_version = MapVersion.objects.create(
            game_map=game_map,
            name=data["version_name"],
            description=data.get("description", ""),
            poll_text=data.get("poll_text", "Die Karte soll ... "),
            revert_poll_text=data.get("revert_poll_text", "Die Karte soll ... "),
            base_version=data.get("is_base_version", False),
            source_version=source,
        )

        # 2. Clone all M2M from source version
        for node in Node.objects.filter(map_versions=source):
            node.map_versions.add(new_version)
        for edge in Edge.objects.filter(map_versions=source):
            edge.map_versions.add(new_version)
        for se in StreetEdge.objects.filter(map_versions=source):
            se.map_versions.add(new_version)
        for te in TrainEdge.objects.filter(map_versions=source):
            te.map_versions.add(new_version)
        for bl in BusLine.objects.filter(map_versions=source):
            bl.map_versions.add(new_version)
        for tl in TrainLine.objects.filter(map_versions=source):
            tl.map_versions.add(new_version)

        # 3. Apply edge changes (clone approach)
        for change in data.get("edge_changes", []):
            try:
                original_edge = Edge.objects.get(
                    pk=change["edge_id"], game_map=game_map
                )
            except Edge.DoesNotExist:
                continue

            # Remove original edge from new version
            original_edge.map_versions.remove(new_version)

            # Create cloned edge with modified properties
            cloned_edge = Edge.objects.create(
                game_map=game_map,
                name=original_edge.name,
                start_node=original_edge.start_node,
                end_node=original_edge.end_node,
                biking=change.get("biking", original_edge.biking),
                walking=change.get("walking", original_edge.walking),
                max_lanes=change.get("max_lanes", original_edge.max_lanes),
            )
            cloned_edge.map_versions.add(new_version)

            # Clone StreetEdge if original had one
            original_se = StreetEdge.objects.filter(
                edge=original_edge, map_versions=source
            ).first()
            if original_se:
                original_se.map_versions.remove(new_version)
                cloned_se = StreetEdge.objects.create(
                    edge=cloned_edge,
                    speed_limit=change.get("speed_limit", original_se.speed_limit),
                    lanes=change.get("lanes", original_se.lanes),
                    dedicated_bus_lane=change.get(
                        "dedicated_bus_lane", original_se.dedicated_bus_lane
                    ),
                )
                cloned_se.map_versions.add(new_version)

                # Update BusLines that referenced the original StreetEdge
                for bl in BusLine.objects.filter(
                    edges=original_se, map_versions=new_version
                ):
                    through_row = BusLineEdge.objects.get(
                        bus_line=bl, street_edge=original_se
                    )
                    preserved_order = through_row.order
                    through_row.delete()
                    BusLineEdge.objects.create(
                        bus_line=bl, street_edge=cloned_se, order=preserved_order
                    )

            # Clone TrainEdge if original had one
            original_te = TrainEdge.objects.filter(
                edge=original_edge, map_versions=source
            ).first()
            if original_te:
                original_te.map_versions.remove(new_version)
                cloned_te = TrainEdge.objects.create(edge=cloned_edge)
                cloned_te.map_versions.add(new_version)

                # Update TrainLines that referenced the original TrainEdge
                for tl in TrainLine.objects.filter(
                    edges=original_te, map_versions=new_version
                ):
                    through_row = TrainLineEdge.objects.get(
                        train_line=tl, train_edge=original_te
                    )
                    preserved_order = through_row.order
                    through_row.delete()
                    TrainLineEdge.objects.create(
                        train_line=tl, train_edge=cloned_te, order=preserved_order
                    )

        # 4. Apply PT line changes
        try:
            pt_line_changes = data.get("pt_line_changes", [])
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        for pt_change in pt_line_changes:
            action = pt_change["action"]
            line_type = pt_change["line_type"]

            if action == "add":
                if line_type == "bus":
                    bl = BusLine.objects.create(
                        game_map=game_map,
                        name=pt_change.get("name", "New Bus Line"),
                        intervall=pt_change.get("interval", 5),
                        bus_capacity=pt_change.get("capacity", 60),
                        bus_speed_kmh=pt_change.get("speed_kmh", 30),
                    )
                    bl.map_versions.add(new_version)
                    if pt_change.get("edge_ids"):
                        edge_ids = pt_change["edge_ids"]
                        se_by_pk = {
                            se.pk: se
                            for se in StreetEdge.objects.filter(pk__in=edge_ids)
                        }
                        BusLineEdge.objects.bulk_create([
                            BusLineEdge(bus_line=bl, street_edge=se_by_pk[eid], order=idx)
                            for idx, eid in enumerate(edge_ids)
                            if eid in se_by_pk
                        ])
                else:
                    tl = TrainLine.objects.create(
                        game_map=game_map,
                        name=pt_change.get("name", "New Train Line"),
                        intervall=pt_change.get("interval", 10),
                        train_capacity=pt_change.get("capacity", 500),
                        train_speed_kmh=pt_change.get("speed_kmh", 40),
                    )
                    tl.map_versions.add(new_version)
                    if pt_change.get("edge_ids"):
                        edge_ids = pt_change["edge_ids"]
                        te_by_pk = {
                            te.pk: te
                            for te in TrainEdge.objects.filter(pk__in=edge_ids)
                        }
                        TrainLineEdge.objects.bulk_create([
                            TrainLineEdge(train_line=tl, train_edge=te_by_pk[eid], order=idx)
                            for idx, eid in enumerate(edge_ids)
                            if eid in te_by_pk
                        ])

            elif action == "remove" and pt_change.get("id"):
                if line_type == "bus":
                    bl = BusLine.objects.filter(pk=pt_change["id"]).first()
                    if bl:
                        bl.map_versions.remove(new_version)
                else:
                    tl = TrainLine.objects.filter(pk=pt_change["id"]).first()
                    if tl:
                        tl.map_versions.remove(new_version)

            elif action == "modify" and pt_change.get("id"):
                # Clone the line for the new version
                if line_type == "bus":
                    original = BusLine.objects.filter(pk=pt_change["id"]).first()
                    if original:
                        original.map_versions.remove(new_version)
                        cloned = BusLine.objects.create(
                            game_map=game_map,
                            name=pt_change.get("name", original.name),
                            intervall=pt_change.get("interval", original.intervall),
                            bus_capacity=pt_change.get(
                                "capacity", original.bus_capacity
                            ),
                            bus_speed_kmh=pt_change.get(
                                "speed_kmh", original.bus_speed_kmh
                            ),
                        )
                        cloned.map_versions.add(new_version)
                        if pt_change.get("edge_ids"):
                            edge_ids = pt_change["edge_ids"]
                            se_by_pk = {
                                se.pk: se
                                for se in StreetEdge.objects.filter(pk__in=edge_ids)
                            }
                            BusLineEdge.objects.bulk_create([
                                BusLineEdge(bus_line=cloned, street_edge=se_by_pk[eid], order=idx)
                                for idx, eid in enumerate(edge_ids)
                                if eid in se_by_pk
                            ])
                        else:
                            BusLineEdge.objects.bulk_create([
                                BusLineEdge(bus_line=cloned, street_edge=t.street_edge, order=t.order)
                                for t in BusLineEdge.objects.filter(bus_line=original).order_by("order")
                            ])
                else:
                    original = TrainLine.objects.filter(pk=pt_change["id"]).first()
                    if original:
                        original.map_versions.remove(new_version)
                        cloned = TrainLine.objects.create(
                            game_map=game_map,
                            name=pt_change.get("name", original.name),
                            intervall=pt_change.get("interval", original.intervall),
                            train_capacity=pt_change.get(
                                "capacity", original.train_capacity
                            ),
                            train_speed_kmh=pt_change.get(
                                "speed_kmh", original.train_speed_kmh
                            ),
                        )
                        cloned.map_versions.add(new_version)
                        if pt_change.get("edge_ids"):
                            edge_ids = pt_change["edge_ids"]
                            te_by_pk = {
                                te.pk: te
                                for te in TrainEdge.objects.filter(pk__in=edge_ids)
                            }
                            TrainLineEdge.objects.bulk_create([
                                TrainLineEdge(train_line=cloned, train_edge=te_by_pk[eid], order=idx)
                                for idx, eid in enumerate(edge_ids)
                                if eid in te_by_pk
                            ])
                        else:
                            TrainLineEdge.objects.bulk_create([
                                TrainLineEdge(train_line=cloned, train_edge=t.train_edge, order=t.order)
                                for t in TrainLineEdge.objects.filter(train_line=original).order_by("order")
                            ])

        # 5. Apply structural deletions
        deleted_node_ids = data.get("deleted_node_ids", [])
        for node_id in deleted_node_ids:
            node = Node.objects.filter(
                pk=node_id, game_map=game_map, map_versions=new_version
            ).first()
            if not node:
                continue
            node.map_versions.remove(new_version)
            # Cascade: remove all edges connected to this node from the version
            for edge in Edge.objects.filter(
                map_versions=new_version
            ).filter(
                Q(start_node=node) | Q(end_node=node)
            ):
                edge.map_versions.remove(new_version)
                for se in StreetEdge.objects.filter(edge=edge, map_versions=new_version):
                    se.map_versions.remove(new_version)
                for te in TrainEdge.objects.filter(edge=edge, map_versions=new_version):
                    te.map_versions.remove(new_version)

        deleted_edge_ids = data.get("deleted_edge_ids", [])
        for edge_id in deleted_edge_ids:
            edge = Edge.objects.filter(
                pk=edge_id, game_map=game_map, map_versions=new_version
            ).first()
            if not edge:
                continue
            edge.map_versions.remove(new_version)
            for se in StreetEdge.objects.filter(edge=edge, map_versions=new_version):
                se.map_versions.remove(new_version)
            for te in TrainEdge.objects.filter(edge=edge, map_versions=new_version):
                te.map_versions.remove(new_version)

        # 6. Apply structural additions
        temp_node_map = {}
        for node_data in data.get("new_nodes", []):
            new_node = Node.objects.create(
                game_map=game_map,
                x_position=node_data["x_position"],
                y_position=node_data["y_position"],
            )
            new_node.map_versions.add(new_version)
            temp_node_map[node_data["temp_id"]] = new_node

        for edge_data in data.get("new_edges", []):
            start_raw = edge_data["temp_start_node"]
            end_raw = edge_data["temp_end_node"]

            # Resolve start node: temp ID or real node ID
            if start_raw in temp_node_map:
                start_node = temp_node_map[start_raw]
            else:
                try:
                    start_node = Node.objects.get(pk=int(start_raw), game_map=game_map)
                except (Node.DoesNotExist, ValueError):
                    continue

            # Resolve end node: temp ID or real node ID
            if end_raw in temp_node_map:
                end_node = temp_node_map[end_raw]
            else:
                try:
                    end_node = Node.objects.get(pk=int(end_raw), game_map=game_map)
                except (Node.DoesNotExist, ValueError):
                    continue

            has_street = edge_data.get("speed_limit") is not None or edge_data.get("lanes") is not None

            def _create_directed_edge(s_node, e_node):
                new_edge = Edge.objects.create(
                    game_map=game_map,
                    start_node=s_node,
                    end_node=e_node,
                    biking=edge_data.get("biking", False),
                    walking=edge_data.get("walking", False),
                    max_lanes=edge_data.get("max_lanes", 1),
                )
                new_edge.map_versions.add(new_version)
                if has_street:
                    se = StreetEdge.objects.create(
                        edge=new_edge,
                        speed_limit=edge_data.get("speed_limit", 50),
                        lanes=edge_data.get("lanes", 1),
                        dedicated_bus_lane=False,
                    )
                    se.map_versions.add(new_version)

            _create_directed_edge(start_node, end_node)
            if edge_data.get("bidirectional"):
                _create_directed_edge(end_node, start_node)

        # 7. Invalidate cache
        _invalidate_map_cache(pk)

        return Response(
            MapVersionSerializer(new_version).data,
            status=status.HTTP_201_CREATED,
        )
